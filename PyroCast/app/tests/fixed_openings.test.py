"""C-5: input persistence and ranking; no numerical integration."""
import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'simulation'),str(ROOT/'simulation/deps')]
from lite_fixed_openings import classifications,apply_fixed,apply_worst,clear,ranked_samples,sample_fixed_states
from result_catalog import atomic_json,read
from pyrocast_lite.screening_v8_approved import score,scenario
from lite_manual_origin import manual_scenario
import lite_mc_service as service


class FixedOpenings(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.raw=read(ROOT/'simulation/results/room_rule_r8_20261025/source-scenario.json')
  cls.sha=cls.raw['cad']['building_sha256'];cls.scored=score(cls.raw,8)

 def test_manual_mc_only_explicit(self):
  for manual in (True,False):
   body=dict(room='CAD_3F_R11',samples=2,duration_s=1800,manual=manual)
   if manual:
    req,model=service.prepare_request(body,self.sha)
    self.assertTrue(req['manual']);self.assertEqual(model['duration_s'],1800)
    self.assertEqual(model['cad']['fire_key'],'CAD_3F_R11')
   else:
    with self.assertRaises(ValueError):service.prepare_request(body,self.sha)
  self.assertNotIn('CAD_3F_R11',{r['room'] for r in self.scored['ranked']})

 def test_extremes_and_manual_fixed_priority(self):
  from pyrocast_lite.montecarlo import make_samples
  model=scenario(self.scored,'CAD_3F_R3','open_except_confirmed')
  sample=make_samples(model,count=2)[0]
  fixed=dict(building_sha256=self.sha,states={r['id']:{k:r[k] for k in ('a','b','open','effective_fraction')} for r in sample['openings']})
  config={'fixed_state':fixed,'DOOR_TEST':'ordinary'}
  self.assertEqual(classifications(config),{'DOOR_TEST':'ordinary'})
  for manual in (True,False):
   for state in ('open_except_confirmed','closed'):
    d=(manual_scenario if manual else scenario)(self.scored,'CAD_3F_R3',state)
    apply_fixed(d,config)
    self.assertEqual({v['id']:v['schedule'][0][1] for v in d['openings']},{k:v['effective_fraction'] for k,v in fixed['states'].items()})
    for s in make_samples(d,count=2,fixed_states=sample_fixed_states(d)):
     self.assertEqual([v['schedule'] for v in s['scenario']['openings']],[v['schedule'] for v in d['openings']])
  bad=deepcopy(config);bad['fixed_state']['building_sha256']='wrong'
  with self.assertRaises(ValueError):apply_fixed(model,bad)

 def test_worst_persistence_and_release(self):
  from pyrocast_lite.montecarlo import make_samples
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);job=root/'mc-123-abcdef';job.mkdir();cfg=root/'doors.json'
   atomic_json(cfg,{'a':'ordinary'})
   atomic_json(job/'request.json',{'building_sha256':self.sha,'room':'CAD_3F_R3'})
   atomic_json(job/'progress.json',{'state':'completed'})
   samples=make_samples(scenario(self.scored,'CAD_3F_R3','closed'),count=2)
   for sample in samples:
    p=job/sample['id'];p.mkdir();atomic_json(p/'sample.json',sample)
    atomic_json(p/'summary.json',{'complete':True,'burning_original_rooms':['R1'],'phenomena':{'FO':{'first_s':200 if sample['id']=='S00' else 100}}})
   def ix(path):return dict(complete=True,unknown_rooms=[],attention_room_count=2 if path.parent.name=='S00' else 1)
   with patch('export_ui_attention.result_index',side_effect=ix):
    fixed=apply_worst(job.name,self.sha,cfg,root)
    self.assertEqual(fixed['sample_id'],'S00')
    self.assertEqual(read(cfg)['a'],'ordinary')
    with patch('export_ui_attention.result_index',return_value=dict(complete=True,unknown_rooms=[],attention_room_count=2)):
     self.assertEqual(ranked_samples(job,self.sha)[0]['sample_id'],'S01')
   clear(cfg);self.assertEqual(read(cfg),{'a':'ordinary'})
   for value in ('../escape','mc-123-../bad'):
    with self.assertRaises(ValueError):apply_worst(value,self.sha,cfg,root)

 def test_screening_cli_delivers_fixed_inputs_to_both_paths(self):
  import run_lite_screening_v8_approved as batch
  from pyrocast_lite.montecarlo import make_samples
  sample=make_samples(scenario(self.scored,'CAD_3F_R3','closed'),count=2)[0]
  fixed=dict(building_sha256=self.sha,states={r['id']:{k:r[k] for k in ('a','b','open','effective_fraction')} for r in sample['openings']})
  original_read=batch.read;captured=[]
  def read_input(path):
   return {'fixed_state':fixed} if path.name=='lite-door-overrides.json' else original_read(path)
  def capture(data,folder):
   captured.append(deepcopy(data))
   raise RuntimeError('test boundary: no integrator invocation')
  for rooms in (None,['CAD_3F_R11']):
   with tempfile.TemporaryDirectory(dir=ROOT/'simulation/results',prefix='c5-input-test-') as tmp:
    with patch.object(batch,'read',side_effect=read_input),patch.object(batch,'execute',side_effect=capture),patch.object(Path,'exists',autospec=True) as exists:
     # The production config need not exist before the first UI application.
     real_exists=__import__('os').path.exists
     exists.side_effect=lambda p:p.name=='lite-door-overrides.json' or real_exists(p)
     batch.run_batch(1,Path(tmp),rooms)
  self.assertEqual(len(captured),2) # One fixed state per request; no duplicate open/closed calculation.
  for data in captured:
   self.assertEqual({v['id']:v['schedule'][0][1] for v in data['openings']},{k:v['effective_fraction'] for k,v in fixed['states'].items()})

if __name__=='__main__':unittest.main()
