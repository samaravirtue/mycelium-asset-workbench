"""Verified ZIP backups. Standard library; run while other workspace writers are stopped."""
import argparse
import ctypes
import sys
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import tempfile
import zipfile

FORMAT = 1
MAX_FILES = 100000
MAX_BYTES = 20 * 1024**3
HEX = re.compile(r'[0-9a-f]{64}')
SIDECARS = {'catalog.sqlite3-wal', 'catalog.sqlite3-shm', 'catalog.sqlite3-journal'}

def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''): h.update(b)
    return h.hexdigest()

@contextmanager
def stage(parent=None):
    path = Path(tempfile.mkdtemp(prefix='.mycelium-stage-', dir=parent))
    try:
        yield path
    finally:
        if path.exists():
            try: shutil.rmtree(path)
            except OSError as exc:
                raise OSError(f'Cleanup failed; temporary data remains at {path}: {exc}') from exc

def safe_name(name):
    if (not isinstance(name, str) or not name or '\\' in name or ':' in name
        or name.startswith('/') or any(p in ('', '.', '..') for p in name.split('/'))
        or any(ord(c)<32 or c in '<>"|?*' for c in name)):
        raise ValueError('Unsafe archive path')
    for part in name.split('/'):
        if part.endswith((' ', '.')) or part.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)],*[f'{p}{i}' for p in ('COM','LPT') for i in '¹²³']}:
            raise ValueError('Unsafe Windows archive path')
    return name

def linked(path):
    if path.is_symlink(): return True
    try:
        return bool(getattr(path.lstat(),'st_file_attributes',0) & getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0x400))
    except FileNotFoundError: return False

def regular(path):
    if linked(path) or not path.is_file(): raise ValueError(f'Not a regular file: {path.name}')

def database_check(path, objects):
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1', uri=True)) as db:
        if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]: raise ValueError('Database integrity failed')
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if tables != {'assets','events','checks'}: raise ValueError('Unsupported catalog schema')
        for table, cols in {'assets':['id','name','domain','layer','status','tags','sha256','filename','source','note','created'], 'events':['seq','asset_id','action','detail','at'], 'checks':['asset_id','sha256','evidence','at']}.items():
            if [r[1] for r in db.execute(f'PRAGMA table_info({table})')] != cols: raise ValueError('Unsupported catalog schema')
        if db.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger','view')").fetchone(): raise ValueError('Unexpected database executable schema')
        for (value,) in db.execute('SELECT sha256 FROM assets UNION SELECT sha256 FROM checks'):
            if not isinstance(value,str) or not HEX.fullmatch(value) or 'objects/'+value not in objects:
                raise ValueError('Database references missing/invalid object')
        return db.execute('SELECT COUNT(*) FROM assets').fetchone()[0]

def validate_tree(root, files):
    if 'catalog.sqlite3' not in files: raise ValueError('Missing catalog')
    for name, record in files.items():
        safe_name(name)
        if name in SIDECARS or name == 'backup.json': raise ValueError('Reserved workspace filename')
        p = root/name
        regular(p)
        if not isinstance(record,dict) or set(record) != {'sha256','size'} or type(record['size']) is not int or record['size']<0 or not isinstance(record['sha256'],str) or not HEX.fullmatch(record['sha256']): raise ValueError('Invalid file manifest')
        if p.stat().st_size != record['size'] or sha(p) != record['sha256']: raise ValueError('File hash/size mismatch: '+name)
        if name.startswith('objects/') and (len(name.split('/')) != 2 or name[8:] != record['sha256']): raise ValueError('Invalid content-addressed object')
    return database_check(root/'catalog.sqlite3', files)

def backup(workspace, output_dir):
    root = Path(workspace).absolute()
    if linked(root): raise ValueError('Workspace symlink refused')
    root = root.resolve(strict=True)
    regular(root/'catalog.sqlite3')
    out = Path(output_dir).resolve()
    if out == root or root in out.parents: raise ValueError('Backups must be outside workspace')
    # Caller must stop mutations. Online backup gives a consistent SQLite snapshot;
    # objects/auxiliary files are not a multi-file transactional filesystem snapshot.
    out.mkdir(parents=True,exist_ok=True)
    with stage(out) as tmp:
        with closing(sqlite3.connect((root/'catalog.sqlite3').as_uri()+'?mode=ro',uri=True)) as src, closing(sqlite3.connect(tmp/'catalog.sqlite3')) as dest:
            src.backup(dest)
            dest.execute("PRAGMA journal_mode=DELETE")
        total = 0
        count=0
        for p in root.rglob('*'):
            count+=1
            if count>MAX_FILES: raise ValueError('Workspace entry count exceeds limit')
            if linked(p): raise ValueError('Workspace symlinks refused')
            if p.is_dir(): continue
            regular(p)
            name = p.relative_to(root).as_posix(); safe_name(name)
            if name == 'catalog.sqlite3' or name in SIDECARS: continue
            if name == 'backup.json': raise ValueError('Reserved workspace filename')
            total += p.stat().st_size
            if total>MAX_BYTES: raise ValueError('Workspace exceeds size limit')
            target = tmp/name; target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(p,target)
            if sha(p)!=sha(target): raise ValueError('Workspace changed during backup')
        files = {p.relative_to(tmp).as_posix():{'sha256':sha(p),'size':p.stat().st_size} for p in sorted(tmp.rglob('*')) if p.is_file()}
        if len(files)>MAX_FILES or sum(r['size'] for r in files.values())>MAX_BYTES: raise ValueError('Backup limit exceeded')
        assets = validate_tree(tmp,files)
        manifest = {'format_version':FORMAT,'catalog_schema_version':1,'created_utc':datetime.now(timezone.utc).isoformat(),'files':files}
        (tmp/'backup.json').write_text(json.dumps(manifest,sort_keys=True,indent=2),encoding='utf8')
        out.mkdir(parents=True,exist_ok=True)
        # Exclusive creation: never truncate an existing archive, including on collision.
        stem = 'mycelium-backup-'+datetime.now(timezone.utc).strftime('%Y-%m-%dT%H%M%SZ')
        i=0
        while True:
            archive=out/(stem+(f'-{i}' if i else '')+'.zip')
            try: handle=open(archive,'xb'); break
            except FileExistsError: i+=1
        try:
            with handle, zipfile.ZipFile(handle,'w',zipfile.ZIP_DEFLATED) as z:
                for name in ['backup.json',*files]: z.write(tmp/name,name)
            verify(archive)
        except BaseException:
            try: archive.unlink()
            except OSError as exc: raise OSError(f'Failed archive cleanup; partial file remains at {archive}') from exc
            raise
        return {'archive':str(archive),'assets':assets,'files':len(files)}

def unpack_verified(archive, tmp):
    regular(Path(archive))
    with zipfile.ZipFile(archive) as z:
        entries=z.infolist()
        if len(entries)>MAX_FILES+1 or sum(i.file_size for i in entries)>MAX_BYTES: raise ValueError('Archive exceeds limits')
        names=set(); folded=set(); components={}
        for i in entries:
            safe_name(i.filename)
            mode=i.external_attr>>16
            if i.is_dir() or (stat.S_IFMT(mode) not in (0,stat.S_IFREG)) or i.flag_bits & 1: raise ValueError('Non-regular/encrypted archive entry')
            if i.filename in names or i.filename.casefold() in folded: raise ValueError('Duplicate/case-colliding archive path')
            for n in range(1,len(i.filename.split('/'))+1):
                component='/'.join(i.filename.split('/')[:n]); key=component.casefold()
                if key in components and components[key]!=component: raise ValueError('Case-colliding archive path component')
                components[key]=component
            names.add(i.filename); folded.add(i.filename.casefold())
        if 'backup.json' not in names or z.getinfo('backup.json').file_size>32*1024**2: raise ValueError('Missing/oversize backup manifest')
        def unique(pairs):
            d={}
            for k,v in pairs:
                if k in d: raise ValueError('Duplicate manifest key')
                d[k]=v
            return d
        m=json.loads(z.read('backup.json'),object_pairs_hook=unique)
        if not isinstance(m,dict): raise ValueError('Backup manifest must be an object')
        if type(m.get('format_version')) is not int or m.get('format_version')!=FORMAT or type(m.get('catalog_schema_version')) is not int or m.get('catalog_schema_version')!=1 or not isinstance(m.get('files'),dict): raise ValueError('Unsupported backup format/schema')
        if names != set(m['files'])|{'backup.json'}: raise ValueError('Archive inventory mismatch')
        for name in m['files']:
            safe_name(name)
            p=tmp/name; p.parent.mkdir(parents=True,exist_ok=True)
            with z.open(name) as src, open(p,'xb') as dest: shutil.copyfileobj(src,dest)
        (tmp/'objects').mkdir(exist_ok=True)
        assets=validate_tree(tmp,m['files'])
        return {'assets':assets,'files':len(m['files']),'integrity':'verified; not proof of authenticity'}

def verify(archive):
    with stage() as tmp: return unpack_verified(archive,tmp)

def publish_directory(source, destination):
    """Atomic no-replace publication, not check-then-overwriting rename."""
    if os.name == 'nt':
        os.rename(source, destination)  # Windows refuses any existing destination.
    elif sys.platform.startswith('linux'):
        libc=ctypes.CDLL(None,use_errno=True)
        fn=getattr(libc,'renameat2',None)
        if fn is None: raise OSError('Atomic no-replace rename unavailable on this platform')
        fn.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]
        fn.restype=ctypes.c_int
        if fn(-100,os.fsencode(source),-100,os.fsencode(destination),1):
            e=ctypes.get_errno(); raise OSError(e,os.strerror(e),str(destination))
    else:
        raise OSError('Restore publication supports Windows/Linux only in this draft')

def restore(archive, destination):
    dest=Path(destination).absolute()
    if linked(dest) or (dest.exists() and (not dest.is_dir() or any(dest.iterdir()))): raise ValueError('Restore requires new/empty destination')
    if not dest.parent.is_dir(): raise ValueError('Destination parent must already exist')
    # Staging is a sibling for same-filesystem rename. No live workspace is overwritten.
    with stage(dest.parent) as tmp:
        result=unpack_verified(archive,tmp)
        if linked(dest) or (dest.exists() and (not dest.is_dir() or any(dest.iterdir()))): raise ValueError('Destination changed during verification')
        existed=dest.exists()
        if existed: dest.rmdir()
        try: publish_directory(tmp,dest)
        except BaseException:
            if existed and not dest.exists(): dest.mkdir()
            raise
        return {**result,'destination':str(dest)}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    b=sub.add_parser('backup'); b.add_argument('workspace'); b.add_argument('output_dir')
    v=sub.add_parser('verify'); v.add_argument('archive')
    r=sub.add_parser('restore'); r.add_argument('archive'); r.add_argument('destination')
    a=p.parse_args()
    try:
        result=backup(a.workspace,a.output_dir) if a.command=='backup' else verify(a.archive) if a.command=='verify' else restore(a.archive,a.destination)
        print(json.dumps(result,indent=2)); return 0
    except (ValueError,OSError,sqlite3.Error,zipfile.BadZipFile,KeyError,TypeError,NotImplementedError,RuntimeError) as exc: p.exit(2,str(exc)+'\n')

if __name__=='__main__': raise SystemExit(main())
