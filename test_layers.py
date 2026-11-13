import tempfile
from pathlib import Path
import os
import json
import unittest
import demo
from workbench import Catalog
class LayeredDemoTests(unittest.TestCase):
    def test_layers_connections_and_provenance(self):
        with tempfile.TemporaryDirectory() as t:
            previous=Path.cwd()
            try:
                os.chdir(t);demo.run();c=Catalog('layered_demo/catalog')
                self.assertEqual(len(c.rows()),24)
                self.assertEqual(len(c.rows('winter')),6)
                self.assertEqual(len(c.rows(layer='underground')),4)
                self.assertTrue(all(x['ok'] for x in c.verify()))
                self.assertEqual(c.manifest(ready_only=True)['assets'],[])
                ids={r['id'] for r in c.rows()};c.close()
                plan=json.loads(Path('layered_demo/scene_plan.json').read_text())
                self.assertEqual(len(plan['connections']),11)
                self.assertTrue(all(e['from'] in ids and e['to'] in ids for e in plan['connections']))
                index=json.loads(Path('layered_demo/project_index.json').read_text());self.assertEqual(len(index['projects']),3);self.assertTrue(all(set(p['asset_ids']) <= ids for p in index['projects']));self.assertFalse(index['exhaustive_inventory'])
                demo.run();c=Catalog('layered_demo/catalog');self.assertEqual(len(c.rows()),24);c.close()
            finally:os.chdir(previous)
