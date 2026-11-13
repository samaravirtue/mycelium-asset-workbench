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
        with self.assertRaises(ValueError):self.run_import(True)
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
        for apply in (False,True):
            with self.assertRaisesRegex(ValueError,'Conflicting asset ID'):self.run_import(apply)
        self.assertEqual(self.dest.rows()[0]['sha256'],before);self.assertEqual(len(self.dest.rows()),1);self.assertTrue(self.dest.verify()[0]['ok'])
    def test_missing_object_blocks_preview_and_apply(self):
        (self.source.objects/self.data['assets'][0]['sha256']).unlink()
        for apply in (False,True):
            with self.assertRaisesRegex(ValueError,'missing source object'):self.run_import(apply)
        self.assertEqual(self.dest.rows(),[]);self.assertEqual(list(self.dest.objects.iterdir()),[])
