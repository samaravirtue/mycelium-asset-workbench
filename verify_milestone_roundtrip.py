"""Synthetic-only final review exercise, never opens the real image collection."""
import json, tempfile, sqlite3
from pathlib import Path
from contextlib import closing
from workbench import Catalog
from workspace_backup import backup, verify, restore, sha

with tempfile.TemporaryDirectory(prefix='aligner-review-') as tmp:
    root=Path(tmp)
    source=root/'synthetic.txt'
    source.write_text('Fictional layer reference for portfolio testing.',encoding='utf8')
    c=Catalog(root/'workspace')
    try:
        object_hash=c.ingest(source,'layer-one','Fictional terrain','sample','terrain',source='synthetic:roundtrip')
    finally: c.close()
    original=sha(source)
    result=backup(root/'workspace',root/'backups')
    checked=verify(result['archive'])
    restored=restore(result['archive'],root/'restored')
    assert sha(root/'restored'/'objects'/object_hash)==object_hash
    assert sha(source)==original
    with closing(sqlite3.connect(root/'restored'/'catalog.sqlite3')) as db:
        assert db.execute('select id from assets').fetchall()==[('layer-one',)]
    try: restore(result['archive'],root/'workspace')
    except ValueError: refused=True
    else: raise AssertionError('Live workspace overwrite was not refused')
    print(json.dumps({'synthetic_only':True,'backup_created':True,'integrity':checked['integrity'],'restored_assets':restored['assets'],'original_unchanged':True,'nonempty_destination_refused':refused,'real_collection_accessed':False},indent=2))
