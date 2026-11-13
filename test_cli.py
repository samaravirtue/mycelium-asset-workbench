import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

APP=Path(__file__).resolve().parent/'workbench.py'
class CLITests(unittest.TestCase):
    def test_round_trip_and_corrupt_exit(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);f=root/'sample.txt';f.write_text('synthetic')
            cmd=[sys.executable,str(APP),'--workspace',str(root/'store')]
            def run(*args):return subprocess.run(cmd+list(args),capture_output=True,text=True)
            r=run('ingest',str(f),'--id','sample','--name','Demo','--domain','wilds','--layer','flora','--source','synthetic','--tags','green')
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertEqual(len(json.loads(run('search','green').stdout)),1)
            self.assertEqual(run('verify').returncode,0)
            self.assertEqual(run('export',str(root/'m.json')).returncode,0)
            self.assertTrue((root/'m.json').is_file())
            h=r.stdout.strip();(root/'store'/'objects'/h).write_text('corrupt')
            self.assertEqual(run('verify').returncode,1)
            self.assertEqual(run('export',str(root/'bad.json')).returncode,2)
            self.assertFalse((root/'bad.json').exists())
    def test_invalid_intake_returns_failure(self):
        with tempfile.TemporaryDirectory() as t:
            r=subprocess.run([sys.executable,str(APP),'--workspace',t,'ingest','missing','--id','../bad','--name','Bad','--domain','wilds','--layer','flora','--source','synthetic'],capture_output=True)
            self.assertEqual(r.returncode,2)

