"""Flow boundary tests. No integration, API calls or persistent job writes."""
import sys,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'simulation'),str(ROOT/'simulation/deps')]
import model_mc as mc
from pyrocast_lite.montecarlo import make_samples
class WorkflowTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.sha=mc.sim.fingerprint('parkmarine');_,score=mc.sim.prepared('parkmarine','5F',cls.sha)
  cls.winner=next(r['room'] for r in score['ranked'] if r['origin_budget']['Q_origin_peak_kW']>0)
 def body(self,**kw):return dict(room=self.winner,floor='5F',samples=2,duration_s=1800,seed=20261025,selection_mode='score_first',**kw)
 def test_top_room_and_two_distinct_samples(self):
  request,model=mc.prepare_request('parkmarine',self.body())
  self.assertEqual(model['cad']['fire_key'],self.winner);self.assertNotIn('fixed_openings',model)
  samples=make_samples(model,count=2,seed=request['seed'])
  self.assertEqual([s['kind'] for s in samples],['all_fire_doors_open','all_openings_closed'])
  self.assertNotEqual(samples[0]['openings'],samples[1]['openings'])
  self.assertTrue(all(s['scenario']['cad']['fire_key']==self.winner for s in samples))
 def test_invalid_and_stale_selection(self):
  for key,value in [('room','CAD_5F_R99'),('floor','6F'),('floor',None),('samples',1),('samples',True),('duration_s',60),('seed',-1)]:
   body=self.body();body[key]=value
   with self.assertRaises(ValueError):mc.prepare_request('parkmarine',body)
  with self.assertRaises(ValueError):mc.folder_for('parkmarine','../../escape')
 def test_same_worker_lock(self):
  with patch.object(mc.sim,'_active','other'):
   with self.assertRaises(RuntimeError):mc.start('parkmarine',self.body())
 def test_runner_command_and_release(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'app/tests') as tmp:
   folder=Path(tmp);mc.atomic_json(folder/'progress.json',{'state':'completed'})
   with patch.object(mc.sim,'_active','test'),patch.object(mc.subprocess,'run') as run:
    mc.compute(folder);self.assertIsNone(mc.sim._active)
    cmd=run.call_args.args[0];self.assertIn(str(ROOT/'tools/run_lite_mc.py'),cmd);self.assertIn('--request',cmd)
 def test_apply_uses_building_scoped_config(self):
  job='mc-123-abcd';fixed={'sample_id':'S01','states':{'D':{'open':False}}}
  with patch.object(mc.sim,'_active',None),patch.object(mc,'apply_worst',return_value=fixed) as apply:
   value=mc.apply('parkmarine',{'job_id':job})
   self.assertEqual(value['case_id'],'modelmc-'+job+'-S01')
   self.assertEqual(apply.call_args.args[2],mc.config_path('parkmarine'))
   self.assertEqual(apply.call_args.args[3],mc.JOBS/'parkmarine')
 def test_evidence_path_allowed(self):
  from execution_evidence import _inputs
  with self.assertRaisesRegex(ValueError,'Missing job provenance'):_inputs(mc.JOBS/'parkmarine'/'mc-0-abcd'/'S00')
 def test_saved_winner_roundtrip_without_simulation(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'app/tests') as tmp:
   jobs=Path(tmp);folder=jobs/'parkmarine'/'mc-123-abcd'
   mc.atomic_json(folder/'request.json',dict(building_sha256=self.sha,room=self.winner,floor='5F'))
   mc.atomic_json(folder/'progress.json',{'state':'completed'})
   mc.atomic_json(folder/'mc-summary.json',{'source_room':self.winner,'rows':[{'complete':True},{'complete':True}]})
   for i,opened in enumerate([True,False]):
    path=folder/f'S{i:02d}';state=dict(id='D',a='A',b='OUTSIDE',open=opened,effective_fraction=1. if opened else .01)
    sample=dict(openings=[state],scenario=dict(cad={'building_sha256':self.sha},openings=[dict(id='D',a='A',b='OUTSIDE',schedule=[[0.,state['effective_fraction']]])]))
    mc.atomic_json(path/'sample.json',sample)
    mc.atomic_json(path/'summary.json',dict(complete=True,burning_original_rooms=['A'] if i==0 else ['A','B'],phenomena={'FO':{'first_s':100}}))
    mc.atomic_json(path/'playback.json',dict(building_sha256=self.sha,fire_key=self.winner))
   config=jobs/'fixed.json'
   with patch.object(mc,'JOBS',jobs),patch.object(mc.sim,'_active',None),patch.object(mc,'config_path',return_value=config),patch('export_ui_attention.result_index',return_value=dict(complete=True,unknown_rooms=[],attention_room_count=2)):
    summary=mc.summary('parkmarine',self.winner);self.assertEqual(summary['worst']['sample_id'],'S01')
    applied=mc.apply('parkmarine',{'job_id':folder.name})
    self.assertEqual(applied['case_id'],summary['worst']['case_id'])
    pb=mc.playback('parkmarine',applied['case_id'])
    self.assertFalse(pb['display_opening_state']['states']['D']['open'])
    self.assertFalse(mc.read(config)['fixed_state']['states']['D']['open'])
    self.assertEqual(len(mc.cases('parkmarine')),2)
if __name__=='__main__':unittest.main()
