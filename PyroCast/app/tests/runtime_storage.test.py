import importlib.util,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import runtime_storage as storage
import storage_cleanup as cleanup
from result_catalog import atomic_json,CombinedResultCatalog
from export_ui_attention import result_index

class StorageTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name);self.new=self.base/'data/results';self.old=self.base/'app/simulation/results'
  self.patches=[patch.object(storage,'RESULTS',self.new),patch.object(storage,'LEGACY_RESULTS',self.old),patch.object(cleanup,'DATA_ROOT',self.base/'data')]
  for p in self.patches:p.start()
  self.addCleanup(self.temp.cleanup)
  for p in self.patches:self.addCleanup(p.stop)
 def case(self,root=None,name='model-library/hotel/a'):
  d=(root or self.new)/name
  atomic_json(d/'input.json',{'fuel':'preserve','openings':[.5]})
  atomic_json(d/'status.json',{'state':'complete'})
  atomic_json(d/'playback.json',{'schema':'pyrocast-cad-playback-1','building_sha256':'abc','engine_kind':'pyrocast_lite','complete':True,'time_s':[0,10],'rooms':[{'key':'R1'}]})
  atomic_json(d/'result.json',{'ok':True,'t':[0,10],'room_summary':[{'original_room':'R1','cell':'R1'}],'shared_conditions':{'rooms':{'R1':{k:{'scores':{'degree':[0,1.2]}} for k in ('FO','FGI','backdraft')}}}})
  (d/'state.npz').write_bytes(b'12345');(d/'console.txt').write_text('log');(d/'notes.txt').write_text('keep')
  return d
 def test_cleanup_preserves_replay_input_and_index(self):
  d=self.case();pb=(d/'playback.json').read_bytes();inp=(d/'input.json').read_bytes();before=result_index(d/'result.json')
  preview=cleanup.preview();self.assertEqual(preview['files'],3);self.assertTrue((d/'result.json').exists())
  result=cleanup.cleanup(preview['token']);self.assertEqual(result['files'],3);self.assertEqual(result['errors'],[])
  self.assertEqual((d/'playback.json').read_bytes(),pb);self.assertEqual((d/'input.json').read_bytes(),inp);self.assertEqual(result_index(d/'result.json'),before);self.assertTrue((d/'notes.txt').exists())
  self.assertEqual(cleanup.preview()['files'],0)
 def test_running_parent_excluded(self):
  d=self.case(name='lite_mc_jobs/models/hotel/mc-1-a/S00');atomic_json(d.parent/'progress.json',{'state':'running'})
  self.assertEqual(cleanup.preview()['files'],0);self.assertTrue((d/'result.json').exists())
 def test_state_changed_after_preview_blocks_all(self):
  d=self.case();p=cleanup.preview();atomic_json(d/'status.json',{'state':'running'})
  with self.assertRaises(ValueError):cleanup.cleanup(p['token'])
  self.assertTrue((d/'state.npz').exists())
 def test_input_changed_after_preview_blocks_all(self):
  d=self.case();p=cleanup.preview();atomic_json(d/'input.json',{'fuel':'changed'})
  with self.assertRaises(ValueError):cleanup.cleanup(p['token'])
  self.assertTrue((d/'result.json').exists())
 def test_invalid_token_and_expiry(self):
  self.case()
  with self.assertRaises(ValueError):cleanup.cleanup('../../etc')
  p=cleanup.preview();stamp,rows=cleanup._PLANS[p['token']];cleanup._PLANS[p['token']]=(stamp-601,rows)
  with self.assertRaises(ValueError):cleanup.cleanup(p['token'])
 def test_incomplete_and_unknown_archives_preserved(self):
  d=self.case();atomic_json(d/'playback.json',{'complete':False});self.case(name='private_archive/a')
  self.assertEqual(cleanup.preview()['files'],0)
 def test_both_result_roots_and_catalog(self):
  old=self.case(self.old);new=self.case(self.new,'model-library/hotel/b')
  self.assertEqual(storage.locate(self.new/'model-library/hotel/a'),old)
  self.assertEqual(len(storage.result_glob(self.new/'model-library/hotel','*/status.json')),2)
  self.assertTrue(storage.is_result_path(old));self.assertFalse(storage.is_result_path(self.base/'outside'))
  cat=CombinedResultCatalog(self.old,self.base/'aliases.json');cases=cat.cases('abc','lite');self.assertEqual(len(cases),2)
  self.assertEqual(cleanup.preview()['calculations'],2)
 def test_latest_mc_across_old_and_new_roots(self):
  import model_mc
  for root,name in ((self.old,'mc-100-aa'),(self.new,'mc-200-bb')):
   atomic_json(root/'lite_mc_jobs/models/hotel'/name/'request.json',{'building_sha256':'abc'})
  with patch.object(model_mc,'JOBS',self.new/'lite_mc_jobs/models'),patch.object(model_mc.sim,'fingerprint',return_value='abc'):
   self.assertEqual([p.name for p in model_mc.folders('hotel')],['mc-200-bb','mc-100-aa'])
 def test_unreadable_raw_is_not_deleted(self):
  d=self.case();(d/'result.json').write_text('{}');self.assertEqual(cleanup.preview()['files'],0)
 def test_mc_ranking_is_identical_after_cleanup(self):
  from lite_fixed_openings import ranked_samples
  d=self.case(name='lite_mc_jobs/models/hotel/mc-1-a/S00');job=d.parent
  atomic_json(job/'request.json',{'building_sha256':'abc'})
  atomic_json(job/'progress.json',{'state':'completed'})
  atomic_json(d/'summary.json',{'complete':True,'phenomena':{'FO':{'first_s':10}},'burning_original_rooms':['R1']})
  atomic_json(d/'sample.json',{'scenario':{'fuel':'keep'},'openings':[{'effective_fraction':.5}]})
  before=ranked_samples(job,'abc');p=cleanup.preview();cleanup.cleanup(p['token'])
  self.assertEqual(ranked_samples(job,'abc'),before);self.assertTrue((d/'sample.json').exists())
 def test_symlink_escape_is_rejected(self):
  outside=self.case(self.base/'outside');link=self.new/'model-library/link';link.parent.mkdir(parents=True)
  try:link.symlink_to(outside,target_is_directory=True)
  except OSError:self.skipTest('symlink creation unavailable')
  self.assertFalse(cleanup.plain(link,self.new));self.assertEqual(cleanup.preview()['files'],0)
 def test_http_rejects_foreign_origin(self):
  class H:
   headers={'Host':'127.0.0.1:8842','Origin':'https://evil.invalid'};client_address=('127.0.0.1',1)
   def json(self,value,status=200):self.status=status
  h=H();self.assertTrue(cleanup.handle(h,'/cfbt/storage/cleanup'));self.assertEqual(h.status,403)

if __name__=='__main__':unittest.main()
