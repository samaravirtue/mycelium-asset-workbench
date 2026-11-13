"""Local-only, copy-on-intake asset catalog. Python 3.10+, standard library."""
import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone

LAYERS = ('underground', 'terrain', 'water', 'flora', 'structures', 'interiors', 'sky', 'reference')
STATES = ('reference', 'proposal', 'unverified', 'artifact', 'tested', 'superseded')
SAFE = re.compile(r'^[a-z0-9][a-z0-9_-]{0,79}$')

def now():
    return datetime.now(timezone.utc).isoformat()

def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def slug(value):
    if not isinstance(value, str) or not SAFE.fullmatch(value):
        raise ValueError('IDs/domains must be lowercase letters, numbers, hyphens or underscores (1-80)')
    return value

def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf8', dir=path.parent, delete=False) as f:
        temporary = Path(f.name)
        json.dump(value, f, indent=2, ensure_ascii=False)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)

class Catalog:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.objects = self.root / 'objects'
        self.objects.mkdir(exist_ok=True)
        self.db = sqlite3.connect(self.root / 'catalog.sqlite3')
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS assets (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, domain TEXT NOT NULL,
          layer TEXT NOT NULL, status TEXT NOT NULL, tags TEXT NOT NULL,
          sha256 TEXT NOT NULL, filename TEXT NOT NULL, source TEXT NOT NULL,
          note TEXT NOT NULL, created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events (
          seq INTEGER PRIMARY KEY, asset_id TEXT NOT NULL, action TEXT NOT NULL,
          detail TEXT NOT NULL, at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS checks (
          asset_id TEXT NOT NULL, sha256 TEXT NOT NULL, evidence TEXT NOT NULL,
          at TEXT NOT NULL);
        ''')
    def close(self):
        self.db.close()
    def event(self, key, action, detail):
        self.db.execute('INSERT INTO events(asset_id,action,detail,at) VALUES(?,?,?,?)',
                        (key, action, detail, now()))
    def ingest(self, path, key, name, domain, layer, tags=(), source='', note='', status='unverified'):
        slug(key); slug(domain)
        if layer not in LAYERS or status not in STATES or status == 'tested':
            raise ValueError('Invalid layer or initial status; tested requires explicit evidence recording')
        if not name.strip() or not source.strip():
            raise ValueError('name and provenance source are required')
        if not isinstance(tags, (list, tuple)) or any(not isinstance(t, str) or len(t)>80 for t in tags):
            raise ValueError('tags must be short strings')
        path = Path(path)
        if path.is_symlink() or not path.is_file():
            raise ValueError('Input must be a regular file, not a symlink')
        if self.db.execute('SELECT 1 FROM assets WHERE id=?', (key,)).fetchone():
            raise ValueError('Asset ID exists; preserve it and choose a new version ID')
        checksum = digest(path)
        target = self.objects / checksum
        if target.exists() and digest(target) != checksum:
            raise ValueError('Existing object corrupted; stop intake and restore from original')
        if not target.exists():
            fd, tmp = tempfile.mkstemp(dir=self.objects)
            os.close(fd)
            try:
                shutil.copyfile(path, tmp)
                if digest(tmp) != checksum:
                    raise ValueError('Source changed during copy')
                os.replace(tmp, target)
            finally:
                Path(tmp).unlink(missing_ok=True)
        with self.db:
            self.db.execute('INSERT INTO assets VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (key, name, domain, layer, status, json.dumps(sorted(set(tags))), checksum,
                 path.name, source, note, now()))
            self.event(key, 'intake', 'Copied and hashed; no originals moved or renamed')
        return checksum
    def rows(self, query='', domain='', layer=''):
        rows = [dict(r) for r in self.db.execute('SELECT * FROM assets ORDER BY domain,layer,id')]
        for r in rows:
            r['tags'] = json.loads(r['tags'])
        terms = query.casefold().split()
        return [r for r in rows if (not domain or r['domain']==domain) and
            (not layer or r['layer']==layer) and all(t in ' '.join([r['name'],r['id'],r['domain'],r['layer'],r['note'],*r['tags']]).casefold() for t in terms)]
    def verify(self):
        return [{'id':r['id'], 'ok': (self.objects/r['sha256']).is_file() and
                 digest(self.objects/r['sha256'])==r['sha256']} for r in self.rows()]
    def set_status(self, key, status, evidence=''):
        if status not in STATES:
            raise ValueError('Unknown status')
        row = self.db.execute('SELECT * FROM assets WHERE id=?',(key,)).fetchone()
        if row is None:
            raise ValueError('Unknown asset')
        if status == 'tested':
            if not evidence.strip():
                raise ValueError('A test description/result reference is required')
            obj = self.objects / row['sha256']
            if not obj.is_file() or digest(obj) != row['sha256']:
                raise ValueError('Integrity check failed')
        with self.db:
            if status == 'tested':
                self.db.execute('INSERT INTO checks VALUES(?,?,?,?)',(key,row['sha256'],evidence,now()))
            self.db.execute('UPDATE assets SET status=? WHERE id=?',(status,key))
            self.event(key,'status',json.dumps({'from':row['status'],'to':status,'evidence':evidence}))
    def manifest(self, domain='', ready_only=False):
        rows = self.rows(domain=domain)
        if ready_only:
            rows = [r for r in rows if r['status']=='tested']
        integrity = {r['id']:r['ok'] for r in self.verify()}
        if any(not integrity[r['id']] for r in rows):
            raise ValueError('Export stopped: missing or corrupt object')
        return {'schema_version':1,'generated_at':now(),
                'warning':'Tested is a user-declared workflow label, not independent verification or production readiness.',
                'assets':[{**r,'object_path':'objects/'+r['sha256']} for r in rows],
                'checks':[dict(r) for r in self.db.execute('SELECT * FROM checks ORDER BY at') if r['asset_id'] in {a['id'] for a in rows}]}
    def report(self, output):
        cards=[]
        for r in self.rows():
            values = [r['domain'], r['layer'], r['status'], *r['tags']]
            cards.append('<article><h2>'+html.escape(r['name'])+'</h2><p>'+html.escape(' · '.join(values))+'</p><p>'+html.escape(r['note'])+'</p><small>'+html.escape(r['id']+' | '+r['source'])+'</small></article>')
        page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Mycelium Asset Workbench</title><style>body{background:#102323;color:#edf7ef;font:17px system-ui;margin:40px auto;max-width:1000px;padding:20px}h1{color:#b6e5ad}input{width:95%;padding:15px;font:inherit}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:18px;margin-top:24px}article{background:#203837;padding:22px;border-radius:12px}small{overflow-wrap:anywhere;color:#bdd5cf}</style><h1>Mycelium Asset Workbench</h1><p>Local catalog · Domain → layer → asset. References are not production meshes.</p><label for="q">Search names, domains, layers and tags</label><input id="q" placeholder="Try winter, water, or prototype"><p id="count" role="status"></p><main>'''+''.join(cards)+'''</main><script>const q=document.querySelector('#q');function filter(){let n=0;for(const a of document.querySelectorAll('article')){a.hidden=!q.value.toLowerCase().split(/\\s+/).every(t=>a.textContent.toLowerCase().includes(t));a.style.display=a.hidden?'none':'';if(!a.hidden)n++}document.querySelector('#count').textContent=n+' matching assets'}q.addEventListener('input',filter);filter()</script></html>'''
        Path(output).write_text(page,encoding='utf8')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',default='local_catalog')
    sub=p.add_subparsers(dest='command',required=True)
    i=sub.add_parser('ingest'); i.add_argument('file'); i.add_argument('--id',required=True);i.add_argument('--name',required=True);i.add_argument('--domain',required=True);i.add_argument('--layer',choices=LAYERS,required=True);i.add_argument('--source',required=True);i.add_argument('--tags',default='');i.add_argument('--note',default='');i.add_argument('--status',default='unverified',choices=STATES)
    s=sub.add_parser('search');s.add_argument('query',nargs='?',default='');s.add_argument('--domain',default='');s.add_argument('--layer',default='')
    sub.add_parser('verify')
    e=sub.add_parser('export');e.add_argument('output');e.add_argument('--domain',default='');e.add_argument('--ready-only',action='store_true')
    r=sub.add_parser('report');r.add_argument('output')
    st=sub.add_parser('status');st.add_argument('id');st.add_argument('status',choices=STATES);st.add_argument('--evidence',default='')
    sub.add_parser('audit')
    a=p.parse_args();c=Catalog(a.workspace)
    try:
        if a.command=='ingest': print(c.ingest(a.file,a.id,a.name,a.domain,a.layer,[t.strip() for t in a.tags.split(',') if t.strip()],a.source,a.note,a.status))
        elif a.command=='search':print(json.dumps(c.rows(a.query,a.domain,a.layer),indent=2))
        elif a.command=='verify':
            results=c.verify();print(json.dumps(results,indent=2))
            return 0 if all(r['ok'] for r in results) else 1
        elif a.command=='export':atomic_json(a.output,c.manifest(a.domain,a.ready_only))
        elif a.command=='report':c.report(a.output)
        elif a.command=='status':c.set_status(a.id,a.status,a.evidence)
        elif a.command=='audit':print(json.dumps([dict(r) for r in c.db.execute('SELECT * FROM events ORDER BY seq')],indent=2))
        return 0
    except (ValueError,OSError,sqlite3.Error) as e:
        p.exit(2,str(e)+'\n')
    finally:c.close()

if __name__=='__main__':raise SystemExit(main())
