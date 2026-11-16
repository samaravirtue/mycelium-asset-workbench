"""Independent recovery coverage for the published backup draft; synthetic only."""
import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import workspace_backup as b
from workbench import Catalog

class BackupMilestoneTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.root = Path(self.t.name)
        self.ws = self.root / 'workspace'
        source = self.root / 'fictional.txt'
        source.write_text('Fictional test asset, not a manuscript', encoding='utf8')
        c = Catalog(self.ws)
        self.h = c.ingest(source, 'sample', 'Sample', 'sample', 'terrain', source='synthetic:test')
        c.close()
        self.archive = Path(b.backup(self.ws, self.root / 'backups')['archive'])
    def tearDown(self):
        self.t.cleanup()
    def changed_zip(self, change):
        with zipfile.ZipFile(self.archive) as z:
            files = {n: z.read(n) for n in z.namelist()}
        change(files)
        target = self.root / 'changed.zip'
        with zipfile.ZipFile(target, 'w') as z:
            for n, data in files.items(): z.writestr(n, data)
        return target
    def test_roundtrip_preserves_catalog_and_object(self):
        dest = self.root / 'restored'
        self.assertEqual(b.restore(self.archive, dest)['assets'], 1)
        self.assertEqual((dest/'objects'/self.h).read_bytes(), (self.ws/'objects'/self.h).read_bytes())
        with closing(sqlite3.connect(dest/'catalog.sqlite3')) as db:
            self.assertEqual(db.execute('select id from assets').fetchall(), [('sample',)])
    def test_restore_empty_destination(self):
        dest = self.root/'empty'; dest.mkdir()
        b.restore(self.archive, dest)
        self.assertTrue((dest/'catalog.sqlite3').is_file())
    def test_verify_does_not_modify_archive(self):
        before = self.archive.read_bytes(), self.archive.stat().st_mtime_ns
        self.assertEqual(b.verify(self.archive)['assets'], 1)
        self.assertEqual(before, (self.archive.read_bytes(), self.archive.stat().st_mtime_ns))
    def test_existing_workspace_not_overwritten(self):
        before = b.sha(self.ws/'catalog.sqlite3')
        with self.assertRaises(ValueError): b.restore(self.archive, self.ws)
        self.assertEqual(before, b.sha(self.ws/'catalog.sqlite3'))
    def test_corruption_never_publishes_destination(self):
        bad = self.changed_zip(lambda f: f.__setitem__('objects/'+self.h, b'corrupt'))
        dest = self.root/'never-created'
        with self.assertRaises(ValueError): b.restore(bad, dest)
        self.assertFalse(dest.exists())
        self.assertEqual(list(self.root.glob('.mycelium-stage-*')), [])
    def test_missing_object_rejected(self):
        bad = self.changed_zip(lambda f: f.pop('objects/'+self.h))
        with self.assertRaises(ValueError): b.verify(bad)
    def test_unsafe_path_rejected(self):
        bad = self.changed_zip(lambda f: f.__setitem__('../escaped.txt', b'bad'))
        with self.assertRaises(ValueError): b.verify(bad)
        self.assertFalse((self.root/'escaped.txt').exists())
    def test_case_collision_rejected(self):
        bad = self.changed_zip(lambda f: f.__setitem__('CATALOG.sqlite3', f['catalog.sqlite3']))
        with self.assertRaises(ValueError): b.verify(bad)
    def test_future_version_rejected(self):
        def change(files):
            m=json.loads(files['backup.json']); m['format_version']=2
            files['backup.json']=json.dumps(m).encode()
        with self.assertRaises(ValueError): b.verify(self.changed_zip(change))
    def test_output_inside_workspace_refused(self):
        with self.assertRaises(ValueError): b.backup(self.ws, self.ws/'backups')
        self.assertFalse((self.ws/'backups').exists())
    def test_archive_collision_does_not_overwrite(self):
        old=self.archive.read_bytes()
        second=Path(b.backup(self.ws, self.root/'backups')['archive'])
        self.assertNotEqual(second, self.archive)
        self.assertEqual(self.archive.read_bytes(), old)
    def test_destination_created_during_publication_preserved(self):
        dest=self.root/'raced'
        original=b.publish_directory
        def race(src, dst):
            dst.mkdir(); (dst/'other-writer.txt').write_text('preserve')
            original(src, dst)
        with patch.object(b, 'publish_directory', side_effect=race):
            with self.assertRaises(OSError): b.restore(self.archive, dest)
        self.assertEqual((dest/'other-writer.txt').read_text(), 'preserve')
        self.assertFalse((dest/'catalog.sqlite3').exists())
    def test_failed_publication_restores_empty_destination(self):
        dest=self.root/'empty'; dest.mkdir()
        with patch.object(b, 'publish_directory', side_effect=OSError('injected failure')):
            with self.assertRaises(OSError): b.restore(self.archive, dest)
        self.assertTrue(dest.is_dir()); self.assertEqual(list(dest.iterdir()), [])
    def test_cleanup_failure_names_remaining_data(self):
        with patch.object(b.shutil, 'rmtree', side_effect=OSError('injected failure')):
            with self.assertRaisesRegex(OSError, 'temporary data remains at'):
                with b.stage(self.root): pass
    def test_wal_snapshot_includes_committed_rows(self):
        c=Catalog(self.ws)
        try:
            c.db.execute('pragma journal_mode=WAL')
            c.db.execute("update assets set name='Committed WAL name'"); c.db.commit()
            archive=Path(b.backup(self.ws,self.root/'backups')['archive'])
            dest=self.root/'wal-restored'; b.restore(archive,dest)
            with closing(sqlite3.connect(dest/'catalog.sqlite3')) as db:
                self.assertEqual(db.execute('select name from assets').fetchone()[0], 'Committed WAL name')
        finally: c.close()

if __name__=='__main__': unittest.main()
