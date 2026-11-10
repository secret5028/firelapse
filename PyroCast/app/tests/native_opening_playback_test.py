"""Replay-only conditional vents: no solver or physical changes."""
import copy,sys,unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'simulation')]
from fixed_native_playback import native_opening_states
class NativeOpeningPlayback(unittest.TestCase):
 def fixture(self, values, enabled=True, kind='window'):
  model=dict(window_breakage=dict(enabled=enabled),openings=[dict(id='W1',a='R1',b='OUTSIDE',kind=kind,schedule=[[0.,.5]])])
  native=dict(native_vents={'Time':np.arange(len(values))*5.,'WF_1':np.array(values,dtype=float)},native_vents_ids={'WF_1':'W1'})
  return model,native
 def test_conditional_window_preserves_actual_values_and_inputs(self):
  model,native=self.fixture([.5,.5,1,1]);before=copy.deepcopy(model)
  states=native_opening_states(model,native)
  self.assertIs(states['W1']['fraction'],native['native_vents']['WF_1']);self.assertEqual(model,before)
  np.testing.assert_array_equal(states['W1']['fraction'],[.5,.5,1,1])
 def test_fixed_or_door_transition_remains_rejected(self):
  for enabled,kind in [(False,'window'),(True,'door')]:
   with self.subTest(enabled=enabled,kind=kind),self.assertRaisesRegex(ValueError,'fixed opening'):
    native_opening_states(*self.fixture([.5,1],enabled,kind))
 def test_wrong_conditional_values_and_closing_are_rejected(self):
  for series in ([.5,.75,1],[.5,1,.5],[.5,float('nan')],[.5,1.1]):
   with self.subTest(series=series),self.assertRaisesRegex(ValueError,'conditional opening'):
    native_opening_states(*self.fixture(series))
 def test_fixed_values_preserved_and_id_ambiguity_rejected(self):
  model,native=self.fixture([.5,.5],False);self.assertEqual(len(native_opening_states(model,native)),1)
  native['native_vents']['WF_2']=np.array([.5,.5]);native['native_vents_ids']['WF_2']='W1'
  with self.assertRaisesRegex(ValueError,'ambiguous'):native_opening_states(model,native)
if __name__=='__main__':unittest.main()
