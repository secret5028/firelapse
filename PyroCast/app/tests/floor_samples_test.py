import sys,unittest
from copy import deepcopy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
from recalculate_floor_samples import apply_openings,registered_digest,BUILDINGS

class FloorOpeningTests(unittest.TestCase):
 def test_bundled_floor_models_match_registered_identity(self):
  from model_library import entries,model_path
  for entry in entries():
   if entry['id'] in BUILDINGS:
    self.assertEqual(registered_digest(model_path(entry),entry),entry['sha256'])
 def test_model_identity_mismatch_fails_before_calculation(self):
  with self.assertRaisesRegex(ValueError,'registered building'):
   registered_digest(Path(__file__),dict(id='test',sha256='wrong'))
 def data(self):
  return {'cad':{'building_sha256':'building'},'screening_source':{'state':'open_except_confirmed'},
   'openings':[{'id':'W','a':'R','b':'OUTSIDE','schedule':[[0,.5]]}]}
 def fixed(self,room='R'):
  return dict(building_sha256='building',source_room=room,job_id='previous',sample_id='S01',
   states={'W':dict(a='R',b='OUTSIDE',open=False,effective_fraction=0)})
 def test_no_confirmation_keeps_app_window_default(self):
  data=self.data();before=deepcopy(data)
  self.assertEqual(apply_openings(data,{},'R'),'open_except_confirmed');self.assertEqual(data,before)
 def test_other_room_confirmation_does_not_leak(self):
  data=self.data();before=deepcopy(data)
  self.assertEqual(apply_openings(data,{'fixed_state':self.fixed('Other')},'R'),'open_except_confirmed')
  self.assertEqual(data,before)
 def test_matching_room_snapshot_is_applied(self):
  data=self.data();self.assertEqual(apply_openings(data,{'fixed_by_room':{'R':self.fixed()}},'R'),'saved_room_openings')
  self.assertEqual(data['openings'][0]['schedule'],[[0.,0]])
  self.assertEqual(data['sample_opening_provenance']['source_room'],'R')
 def test_mismatched_endpoint_is_rejected(self):
  fixed=self.fixed();fixed['states']['W']['b']='Wrong'
  with self.assertRaisesRegex(ValueError,'endpoints'):apply_openings(self.data(),{'fixed_state':fixed},'R')

if __name__=='__main__':unittest.main()
