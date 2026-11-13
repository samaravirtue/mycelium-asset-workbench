"""Copy-only manifest import: read-only preview, then explicit all-or-nothing apply."""
import argparse
from collections import Counter
from contextlib import closing
import json
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
from workbench import Catalog, LAYERS, STATES, slug, digest, now


def snapshot(workspace):
    """Read destination without creating directories, SQLite files, or migrations."""
    root = Path(workspace).absolute()
    if root.is_symlink() or (root / 'objects').is_symlink():
        raise ValueError('Unsafe destination workspace')
    db_path = root / 'catalog.sqlite3'
    if db_path.is_symlink():
        raise ValueError('Unsafe destination database')
    if not db_path.exists():
        return root, {}
    # Refuse live/recovery journals rather than create sidecars or read stale WAL data.
    if any(Path(str(db_path) + suffix).exists() for suffix in ('-wal', '-shm', '-journal')):
        raise ValueError('Destination has SQLite sidecars; close its writer before preview')
    with closing(sqlite3.connect(db_path.as_uri() + '?mode=ro&immutable=1', uri=True)) as db:
        db.row_factory = sqlite3.Row
        rows = {r['id']: dict(r) for r in db.execute('SELECT * FROM assets')}
    return root, rows


def validate(record, root, destination):
    if not isinstance(record, dict):
        raise ValueError('Asset must be an object')
    row = dict(record)
    slug(row.get('id')); slug(row.get('domain'))
    if row.get('layer') not in LAYERS or row.get('status') not in STATES:
        raise ValueError('Invalid layer or status')
    for field in ('name', 'source', 'note', 'filename'):
        if not isinstance(row.get(field), str):
            raise ValueError('Invalid ' + field)
    if not row['name'].strip() or not row['source'].strip():
        raise ValueError('Missing provenance/name')
    if (not row['filename'] or row['filename'] in ('.', '..') or
            Path(row['filename']).name != row['filename'] or
            '/' in row['filename'] or '\\' in row['filename']):
        raise ValueError('Unsafe filename')
    tags = row.get('tags')
    if not isinstance(tags, list) or any(not isinstance(t, str) or len(t) > 80 for t in tags):
        raise ValueError('Invalid tags')
    checksum = row.get('sha256', '')
    if not isinstance(checksum, str) or not re.fullmatch(r'[0-9a-f]{64}', checksum):
        raise ValueError('Invalid hash')
    if row.get('object_path') != 'objects/' + checksum:
        raise ValueError('Unsafe object path')
    path = root / 'objects' / checksum
    if (root.is_symlink() or (root / 'objects').is_symlink() or path.is_symlink()
            or not path.is_file() or not path.resolve().is_relative_to(root.resolve())):
        raise ValueError('Unsafe/missing source object')
    if digest(path) != checksum:
        raise ValueError('Source checksum mismatch')
    target = destination / 'objects' / checksum
    if target.is_symlink() or (target.exists() and (not target.is_file() or digest(target) != checksum)):
        raise ValueError('Corrupt/unsafe destination object')
    row['imported_status'] = row['status']
    if row['status'] == 'tested':
        row['status'] = 'unverified'
    return row, path


def prepare(workspace, manifest, object_root):
    data = json.loads(Path(manifest).read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('schema_version') != 1 or not isinstance(data.get('assets'), list):
        raise ValueError('Unsupported manifest schema')
    destination, existing = snapshot(workspace)
    root = Path(object_root).absolute()
    counts = Counter(r.get('id') for r in data['assets'] if isinstance(r, dict) and isinstance(r.get('id'), str))
    verdicts, pending = [], []
    for index, record in enumerate(data['assets']):
        result = {'index': index, 'id': record.get('id') if isinstance(record, dict) else None}
        try:
            row, path = validate(record, root, destination)
            key = row['id']
            result.update(status=row['status'], source_status=row['imported_status'])
            if counts[key] > 1:
                result.update(verdict='conflict', reason='Duplicate asset ID in manifest')
            elif key in existing:
                if existing[key]['sha256'] != row['sha256']:
                    result.update(verdict='conflict', reason='Same ID with different bytes')
                else:
                    target = destination / 'objects' / row['sha256']
                    if not target.is_file():
                        raise ValueError('Missing destination object for existing asset')
                    result.update(verdict='skip-identical', reason='Same ID and verified bytes; existing metadata retained')
            else:
                result.update(verdict='add', reason='Validated new asset')
                pending.append((row, path))
        except (ValueError, OSError, KeyError, TypeError) as error:
            result.update(verdict='invalid', reason=str(error))
        verdicts.append(result)
    summary = {v: sum(r['verdict'] == v for r in verdicts) for v in ('add', 'skip-identical', 'conflict', 'invalid')}
    return {'mode': 'preview', 'count': len(verdicts), 'summary': summary,
            'can_apply': not (summary['conflict'] or summary['invalid']), 'assets': verdicts}, pending


def import_manifest(catalog, manifest, object_root, apply=False):
    """Accept a workspace path or existing Catalog (legacy callers own its lifecycle)."""
    workspace = catalog.root if isinstance(catalog, Catalog) else catalog
    report, pending = prepare(workspace, manifest, object_root)
    if not apply:
        return report
    if not report['can_apply']:
        raise ValueError('Import refused: conflict/invalid entries; run preview for all verdicts')
    report['mode'] = 'apply'
    if not pending:
        return report  # Identical re-import: no DB/events/object writes.
    owned = not isinstance(catalog, Catalog)
    c = Catalog(workspace) if owned else catalog
    try:
        with tempfile.TemporaryDirectory(dir=c.root) as stage:
            for row, path in pending:
                staged = Path(stage) / row['sha256']
                shutil.copyfile(path, staged)
                if digest(staged) != row['sha256']:
                    raise ValueError('Source changed while staging')
            # Recheck IDs after acquiring the write lock. No replace/overwrite path.
            c.db.execute('BEGIN IMMEDIATE')
            try:
                for row, path in pending:
                    if c.db.execute('SELECT 1 FROM assets WHERE id=?', (row['id'],)).fetchone():
                        raise ValueError('Destination changed after preview; preview again')
                for row, path in pending:
                    target = c.objects / row['sha256']
                    if target.is_symlink():
                        raise ValueError('Unsafe destination object')
                    if not target.exists():
                        shutil.copyfile(Path(stage) / row['sha256'], target)
                    if digest(target) != row['sha256']:
                        raise ValueError('Destination verification failed')
                    c.db.execute('INSERT INTO assets VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                        (row['id'], row['name'], row['domain'], row['layer'], row['status'],
                         json.dumps(sorted(set(row['tags']))), row['sha256'], row['filename'],
                         row['source'], row['note'], now()))
                    c.event(row['id'], 'manifest_import', json.dumps({'source_status': row['imported_status'],
                        'sha256': row['sha256'], 'note': 'Copied validated object; imported tested claims downgraded'}))
                c.db.commit()
            except Exception:
                c.db.rollback()
                raise
    finally:
        if owned:
            c.close()
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest'); p.add_argument('--objects-root', required=True)
    p.add_argument('--workspace', required=True); p.add_argument('--apply', action='store_true')
    a = p.parse_args()
    try:
        report = import_manifest(a.workspace, a.manifest, a.objects_root, a.apply)
        print(json.dumps(report, indent=2))
        if not report['can_apply']:
            p.exit(2)
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error) as error:
        p.exit(2, str(error) + '\n')

if __name__ == '__main__':
    main()
