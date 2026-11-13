import json
from pathlib import Path
import tempfile
import unittest
from workbench import Catalog, digest, atomic_json

class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.file=self.root/'original.txt';self.file.write_text('synthetic demo only')
        self.c=Catalog(self.root/'catalog')
    def tearDown(self):self.c.close();self.tmp.cleanup()
    def add(self,key='demo',**kw):
        return self.c.ingest(self.file,key,kw.pop('name','Winter sample'),kw.pop('domain','unseelie'),kw.pop('layer','water'),['winter'],source='synthetic:test',**kw)
    def test_original_preserved(self):
        before=digest(self.file);self.add();self.assertEqual(digest(self.file),before)
    def test_dedup(self):
        self.add();self.add('second');self.assertEqual(len(list(self.c.objects.iterdir())),1);self.assertEqual(len(self.c.rows()),2)
    def test_duplicate_id_rejected(self):
        self.add()
        with self.assertRaises(ValueError):self.add()
    def test_path_traversal(self):
        with self.assertRaises(ValueError):self.add('../escape')
    def test_bad_domain(self):
        with self.assertRaises(ValueError):self.add(domain='../winter')
    def test_invalid_layer(self):
        with self.assertRaises(ValueError):self.add(layer='banana')
    def test_initial_tested_rejected(self):
        with self.assertRaises(ValueError):self.add(status='tested')
    def test_search_alias(self):
        self.add();self.assertEqual(len(self.c.rows('winter',domain='unseelie')),1);self.assertEqual(self.c.rows('summer'),[])
    def test_search_terms_and(self):
        self.add();self.assertEqual(len(self.c.rows('winter water')),1);self.assertEqual(self.c.rows('winter sky'),[])
    def test_status_requires_evidence(self):
        self.add()
        with self.assertRaises(ValueError):self.c.set_status('demo','tested')
    def test_evidence_and_export(self):
        self.add();self.c.set_status('demo','tested','synthetic check: file text inspected');m=self.c.manifest(ready_only=True);self.assertEqual(len(m['assets']),1);self.assertEqual(len(m['checks']),1)
    def test_reference_not_ready(self):
        self.add(status='reference');self.assertEqual(self.c.manifest(ready_only=True)['assets'],[])
    def test_superseded_excluded(self):
        self.add();self.c.set_status('demo','superseded');self.assertEqual(self.c.manifest(ready_only=True)['assets'],[])
    def test_corruption(self):
        h=self.add();(self.c.objects/h).write_text('bad');self.assertFalse(self.c.verify()[0]['ok'])
        with self.assertRaises(ValueError):self.c.manifest()
    def test_corrupt_promotion(self):
        h=self.add();(self.c.objects/h).unlink()
        with self.assertRaises(ValueError):self.c.set_status('demo','tested','claimed test')
    def test_corrupt_dedup(self):
        h=self.add();(self.c.objects/h).write_text('bad')
        with self.assertRaises(ValueError):self.add('second')
    def test_symlink(self):
        link=self.root/'link'
        try: link.symlink_to(self.file)
        except OSError as exc: self.skipTest('Symlink creation unavailable on this operating-system account')
        with self.assertRaises(ValueError):self.c.ingest(link,'link','Link','wilds','flora',source='test')
    def test_html_escaping(self):
        self.add(name='<script>alert(1)</script>');out=self.root/'report.html';self.c.report(out);text=out.read_text();self.assertIn('&lt;script&gt;',text);self.assertNotIn('<script>alert(1)',text)
    def test_audit(self):
        self.add();self.c.set_status('demo','artifact');self.assertEqual(self.c.db.execute('select count(*) from events').fetchone()[0],2)
    def test_persistence(self):
        self.add();other=Catalog(self.root/'catalog');self.assertEqual(len(other.rows()),1);other.close()
    def test_domain_export(self):
        self.add();self.add('leaf',domain='seelie');self.assertEqual(len(self.c.manifest(domain='seelie')['assets']),1)
    def test_atomic_json(self):
        out=self.root/'sub'/'out.json';atomic_json(out,{'version':1});atomic_json(out,{'version':2});self.assertEqual(json.loads(out.read_text()),{'version':2})
    def test_unknown_status(self):
        self.add()
        with self.assertRaises(ValueError):self.c.set_status('demo','complete')
    def test_missing_source(self):
        with self.assertRaises(ValueError):self.c.ingest(self.file,'test','Test','wilds','flora')

if __name__=='__main__':unittest.main()


