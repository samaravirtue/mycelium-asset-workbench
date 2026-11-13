import json
from pathlib import Path
import tempfile
import unittest
from workbench import Catalog, atomic_json
from manifest_import import import_manifest

class ImportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.source=Catalog(self.root/'source');self.dest=Catalog(self.root/'dest')
        f=self.root/'sample.txt';f.write_text('synthetic sample')
        self.source.ingest(f,'sample-v1','Synthetic module','demo','terrain',source='synthetic fixture',status='reference')
        self.file=self.root/'manifest.json';self.data=self.source.manifest();self.save()
    def save(self):atomic_json(self.file,self.data)
    def run_import(self,apply=False):return import_manifest(self.dest,self.file,self.source.root,apply)
    def tearDown(self):self.source.close();self.dest.close();self.temp.cleanup()
    def test_preview_no_rows_or_objects(self):
        self.assertEqual(self.run_import()['count'],1);self.assertEqual(self.dest.rows(),[]);self.assertEqual(list(self.dest.objects.iterdir()),[])
    def test_apply_copies_and_audits(self):
        self.run_import(True);self.assertEqual(len(self.dest.rows()),1);self.assertTrue(self.dest.verify()[0]['ok']);self.assertEqual(self.dest.db.execute('select action from events').fetchone()[0],'manifest_import');self.assertTrue(self.source.verify()[0]['ok'])
    def test_duplicate_conflict_no_mutation(self):
        self.run_import(True)
        result=self.run_import(True)
        self.assertEqual(result['summary']['skip-identical'],1)
        self.assertEqual(len(self.dest.rows()),1)
    def test_batch_duplicate_rejected_before_copy(self):
        self.data['assets']*=2;self.save()
        with self.assertRaises(ValueError):self.run_import(True)
        self.assertEqual(self.dest.rows(),[]);self.assertEqual(list(self.dest.objects.iterdir()),[])
    def test_traversal_and_hash_rejected(self):
        self.data['assets'][0]['object_path']='../secret';self.save()
        with self.assertRaises(ValueError):self.run_import(True)
        self.assertEqual(self.dest.rows(),[])
    def test_corrupt_object_rejected(self):
        (self.source.objects/self.data['assets'][0]['sha256']).write_text('tampered')
        with self.assertRaises(ValueError):self.run_import(True)
        self.assertEqual(self.dest.rows(),[])
    def test_tested_is_downgraded(self):
        self.source.set_status('sample-v1','tested','fictional manual assertion');self.data=self.source.manifest();self.save();self.run_import(True)
        self.assertEqual(self.dest.rows()[0]['status'],'unverified');self.assertEqual(self.dest.manifest(ready_only=True)['assets'],[])
    def test_schema_rejected(self):
        self.data['schema_version']=99;self.save()
        with self.assertRaises(ValueError):self.run_import(True)

    def test_same_id_different_bytes_blocks_preview_and_apply(self):
        f=self.root/'different.txt';f.write_text('different synthetic bytes')
        self.dest.ingest(f,'sample-v1','Existing module','demo','terrain',source='synthetic destination',status='reference')
        before=self.dest.rows()[0]['sha256']
        self.assertEqual(self.run_import()['assets'][0]['verdict'],'conflict')
        with self.assertRaises(ValueError):self.run_import(True)
        self.assertEqual(self.dest.rows()[0]['sha256'],before);self.assertEqual(len(self.dest.rows()),1);self.assertTrue(self.dest.verify()[0]['ok'])
    def test_missing_object_blocks_preview_and_apply(self):
        (self.source.objects/self.data['assets'][0]['sha256']).unlink()
        self.assertEqual(self.run_import()['assets'][0]['verdict'],'invalid')
        with self.assertRaises(ValueError):self.run_import(True)
        self.assertEqual(self.dest.rows(),[]);self.assertEqual(list(self.dest.objects.iterdir()),[])

    def test_absent_workspace_preview_no_artifacts(self):
        dest=self.root/'absent'/'nested'
        result=import_manifest(dest,self.file,self.source.root)
        self.assertEqual(result['summary']['add'],1)
        self.assertFalse((self.root/'absent').exists())

    def test_existing_preview_and_skip_preserve_every_byte(self):
        self.run_import(True)
        def state():return {str(p.relative_to(self.dest.root)):(p.read_bytes(),p.stat().st_mtime_ns) for p in self.dest.root.rglob('*') if p.is_file()}
        before=state()
        self.run_import();self.run_import(True)
        self.assertEqual(state(),before)

    def test_all_verdicts_and_no_partial_apply(self):
        self.run_import(True)
        extra=self.root/'extra.txt';extra.write_text('new bytes')
        self.source.ingest(extra,'second','Second','demo','water',source='synthetic')
        self.data=self.source.manifest()
        bad=dict(self.data['assets'][0]);bad['id']='invalid-row';bad['sha256']='bad'
        self.data['assets'].append(bad)
        conflict=dict(self.data['assets'][1]);conflict['id']='conflict-row'
        self.dest.ingest(self.root/'sample.txt','conflict-row','Conflict','demo','water',source='synthetic')
        self.data['assets'].append(conflict);self.save()
        result=self.run_import()
        self.assertEqual(result['summary'],{'add':1,'skip-identical':1,'conflict':1,'invalid':1})
        with self.assertRaises(ValueError):self.run_import(True)
        self.assertEqual(len(self.dest.rows()),2)

    def test_duplicate_marks_both_rows(self):
        self.data['assets']*=2;self.save()
        self.assertEqual(self.run_import()['summary']['conflict'],2)

    def test_cli_preview_absent_workspace(self):
        import subprocess,sys
        dest=self.root/'no-create'
        result=subprocess.run([sys.executable,'manifest_import.py',str(self.file),'--objects-root',str(self.source.root),'--workspace',str(dest)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertFalse(dest.exists())
        self.assertEqual(json.loads(result.stdout)['summary']['add'],1)

    def test_skip_keeps_local_test_status_and_metadata(self):
        self.run_import(True)
        self.dest.set_status('sample-v1','tested','local synthetic test claim')
        before=self.dest.rows()
        self.run_import(True)
        self.assertEqual(self.dest.rows(),before)

    def test_source_missing_directory_reports_every_row(self):
        self.data['assets'].append(dict(self.data['assets'][0],id='second'));self.save()
        result=import_manifest(self.root/'not-created',self.file,self.root/'missing')
        self.assertEqual(result['summary']['invalid'],2)
        self.assertFalse((self.root/'not-created').exists())


class SnapshotConnectionTests(unittest.TestCase):
    def test_snapshot_closes_connection_on_success_and_error(self):
        from unittest.mock import MagicMock, patch
        from manifest_import import snapshot
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'catalog.sqlite3').touch()
            for fail in (False, True):
                with self.subTest(query_failure=fail):
                    db = MagicMock()
                    db.execute.return_value = []
                    if fail:
                        db.execute.side_effect = RuntimeError('synthetic query failure')
                    with patch('manifest_import.sqlite3.connect', return_value=db):
                        if fail:
                            with self.assertRaises(RuntimeError): snapshot(root)
                        else:
                            self.assertEqual(snapshot(root)[1], {})
                    db.close.assert_called_once_with()
