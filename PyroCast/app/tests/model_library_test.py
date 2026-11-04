import json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from model_library import entries,model_path,catalog,execution_policy,RUN_PATHS

class ModelLibraryTest(unittest.TestCase):
 def test_all_registered_models_load(self):
  rows=entries();self.assertEqual(8,len(rows));self.assertEqual(len(rows),len({r['id'] for r in rows}))
  for row in rows:
   b=json.loads(model_path(row).read_text('utf8'));self.assertEqual(row['floor_count'],len(b['floors']))
 def test_scans_never_execute(self):
  scans=[e for e in entries() if e['source_kind']=='scan'];self.assertEqual(2,len(scans))
  for e in scans:
   b=json.loads(model_path(e).read_text('utf8'));self.assertFalse(execution_policy(b,model_path(e))['allowed'])
   # Renaming/copying the scan must not bypass provenance enforcement.
   with tempfile.TemporaryDirectory(dir=ROOT/'reviews',prefix='model-policy-test-') as d:
    p=Path(d)/'building.json';p.write_text(json.dumps(b),'utf8');self.assertFalse(execution_policy(b,p)['allowed'])
 def test_originals_preserved(self):
  import hashlib
  for e in entries():
   self.assertEqual(e['original_sha256'],hashlib.sha256(Path(e['source_path']).read_bytes()).hexdigest())
 def test_known_operating_cad_allowed(self):
  e=next(e for e in entries() if e['id']=='ganghwa');self.assertTrue(execution_policy(json.loads(model_path(e).read_text('utf8')),model_path(e))['allowed'])
 def test_unknown_not_silently_executable(self):self.assertFalse(execution_policy({})['allowed'])
 def test_catalog_links_and_no_filesystem_paths(self):
  for e in catalog()['models']:
   self.assertNotIn('path',e);self.assertNotIn('source_path',e);self.assertIn('/models/?id=',e['url'])
 def test_all_execution_endpoints_guarded(self):
  self.assertEqual(RUN_PATHS,{'/cfbt/run','/cfbt/ignite','/cfbt/r8/run','/cfbt/lite/screening','/cfbt/lite/mc'})
if __name__=='__main__':unittest.main()
