"""Night batch must retain schedules and never transplant another building's state."""
import unittest
from copy import deepcopy
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
from run_overnight_floors import freeze_openings

class OpeningSnapshots(unittest.TestCase):
    def setUp(self):
        self.raw={'cad':{'building_sha256':'A'},'openings':[
            {'id':'D1','a':'R1','b':'R2','schedule':[[0,0],[1800,1]]},
            {'id':'W1','a':'R1','b':'OUTSIDE','schedule':[[0,.5]]}]}
        self.data=deepcopy(self.raw);self.data['screening_source']={}
        self.data['openings'][0]['schedule']=[[0,1]]
    def test_original_schedule_not_extreme(self):
        self.assertEqual(freeze_openings(self.data,self.raw,{}),'input_default')
        self.assertEqual(self.data['openings'][0]['schedule'],[[0,0],[1800,1]])
        self.assertFalse(self.data['overnight_openings']['worst_case_claim'])
    def test_other_floor_not_extrapolated(self):
        cfg={'fixed_state':{'building_sha256':'A','states':{'D_OTHER':{'effective_fraction':1}}}}
        self.assertEqual(freeze_openings(self.data,self.raw,cfg),'input_default')
    def test_confirmation_matches_both_endpoints(self):
        cfg={'fixed_state':{'building_sha256':'A','states':{'D1':{'a':'R1','b':'R2','effective_fraction':.001,'open':False}}}}
        freeze_openings(self.data,self.raw,cfg)
        self.assertEqual(self.data['openings'][0]['schedule'],[[0,.001]])
        self.assertEqual(self.data['openings'][1]['schedule'],[[0,.5]])
        self.assertFalse(self.data['screening_source']['opening_states'][0]['open'])
        cfg['fixed_state']['states']['D1']['b']='R9'
        with self.assertRaisesRegex(ValueError,'endpoints'):freeze_openings(self.data,self.raw,cfg)
    def test_cross_building_rejected(self):
        with self.assertRaisesRegex(ValueError,'another building'):
            freeze_openings(self.data,self.raw,{'fixed_state':{'building_sha256':'B','states':{}}})

if __name__=='__main__':unittest.main()
