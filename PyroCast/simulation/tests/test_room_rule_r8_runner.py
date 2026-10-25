import json,sys,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import run_room_rule_r8 as runner

class R8RunnerTests(unittest.TestCase):
 def test_incomplete_is_not_no_ignition(self):
  completed={'complete':True,'actual_burning_original_rooms':['R1'],
    'rows':[{'original_room':'R1','first_actual_positive_HRR_s':5}]}
  result=runner.ranges({'selected':completed,'aggressive':{'complete':False}})
  self.assertIsNone(result['burning_room_count_range'])
  row=result['room_first_actual_HRR']['R1']
  self.assertEqual(row['not_observed_in'],[])
  self.assertEqual(row['unevaluated_in'],['aggressive'])

 def test_single_default_or_exact_two_parallel_no_retry(self):
  raw=json.loads((ROOT/'fixtures/room_rule_benchmark_3room.json').read_text('utf-8'))
  for compare in (False,True):
   with self.subTest(compare=compare),tempfile.TemporaryDirectory(dir=runner.RESULTS) as temp:
    folder=Path(temp);calls=[];barrier=threading.Barrier(2) if compare else None
    def base(model,manifest):
     destination=folder/'baseline';destination.mkdir()
     (destination/'case.in').write_text(runner.make_deck(runner.baseline_input(model),[],[]),'ascii')
     return {'key':'test','folder':str(destination),'report':{'complete':True}}
    def case(destination,model,targets,manifest,**kwargs):
     calls.append(destination.name)
     if barrier:barrier.wait(timeout=5)
     return {'complete':True,'actual_burning_original_rooms':['R1'],'rows':[]}
    with patch.object(runner,'baseline',side_effect=base),patch.object(runner,'run_case',side_effect=case):
     result=runner.run_batch(raw,folder/'batch',compare=compare)
     self.assertCountEqual(calls,['selected','aggressive'] if compare else ['selected'])
     self.assertFalse(result['operating_playback_replaced'])
     if compare:self.assertEqual(result['settings']['aggressive']['parameters']['vent_cap_k']['source'],'comparison_shared')
     with self.assertRaisesRegex(ValueError,'already attempted'):
      runner.run_batch(raw,folder/'batch',compare=compare)
     self.assertEqual(len(calls),2 if compare else 1)

 def test_invalid_input_stops_before_baseline_or_native(self):
  with patch.object(runner,'baseline') as base,patch.object(runner,'run_case') as case:
   with self.assertRaisesRegex(ValueError,'450~700'):
    runner.run_batch({},runner.RESULTS/'invalid-unused',{'temperature_C':449})
   base.assert_not_called();case.assert_not_called()

if __name__=='__main__':unittest.main()
