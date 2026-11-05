import json,unittest
from pathlib import Path
import numpy as np
from pyrocast_cfbt.conditions import screening_scores,fo_required_hrr,screening_lfl
from pyrocast_lite.door_classification import classify_doors
from pyrocast_lite.montecarlo import make_samples

class SharedConditionsTests(unittest.TestCase):
    def test_three_ratios_and_limiting_factor(self):
        s=screening_scores(([900.],600.,False),([2000.],1000.,False),([18.],12.,False),1,[True])
        self.assertEqual(s['degree'],[1.5]);self.assertEqual(s['strongest'],['fuel']);self.assertEqual(s['all_met'],[True])
    def test_inverse_oxygen_zero_and_unknown(self):
        s=screening_scores(([600.],300.,False),([.2],.1,False),([0.],10.,True),1,[True])
        self.assertEqual(s['degree'],[2.]);self.assertFalse(s['unbounded_factors']['oxygen'][0])
        self.assertTrue(s['oxygen_numeric_guard']['applied'][0])
        u=screening_scores(([600.],300.,False),None,([0.],10.,True),1,[True])
        self.assertIsNone(u['degree'][0]);self.assertIsNone(u['all_met'][0])
    def test_inverse_oxygen_crossing_zero_retains_fuel_limited_score(self):
        oxygen=[8.45693459910182e-7,-2.440107326563614e-6,0.,1e-300,None,float('nan')]
        before=oxygen.copy()
        s=screening_scores(([614.1]*6,300.,False),([.1073785]*6,.1,False),(oxygen,10.,True),6)
        np.testing.assert_allclose(s['degree'][:4],[1.073785]*4)
        self.assertEqual(s['degree'][4:],[None,None])
        self.assertEqual(s['oxygen_numeric_guard']['applied'],[False,True,True,True,False,False])
        self.assertTrue(all(np.isfinite(v) for v in s['factors']['oxygen'][:4]))
        self.assertEqual(oxygen[:5],before[:5])
    def test_positive_oxygen_and_other_factors_unchanged(self):
        s=screening_scores(([600.]*3,300.,False),([.2]*3,.1,False),([5.,10.,20.],10.,True),3)
        self.assertEqual(s['degree'],[2.,1.,.5])
        self.assertEqual(s['oxygen_numeric_guard']['applied'],[False]*3)
        direct=screening_scores(([600.],300.,False),([.2],.1,False),([0.],10.,False),1)
        self.assertEqual(direct['degree'],[0.])
    def test_thomas_opening_fraction_and_virtual_exclusion(self):
        room={'id':'R','size_m':[5,5,3]}
        vent={'id':'D','a':'R','b':'OUTSIDE','width_m':1.,'top_m':2.,'schedule':[[0,0],[10,1]]}
        model={'openings':[vent,{**vent,'id':'CELL','virtual_cell_boundary':True,'width_m':100}]}
        q=fo_required_hrr(model,{'time_s':[0,10]},room,np.array([0.,10.]))
        self.assertAlmostEqual(q[0],7.8*110);self.assertAlmostEqual(q[1],7.8*108+378*2*np.sqrt(2))
    def test_score_and_context_are_separate(self):
        s=screening_scores(([600.],600.,False),([2.],1.,False),([12.],12.,False),1,[False])
        self.assertEqual(s['all_met'],[True]);self.assertEqual(s['legacy_context_met'],[False])
    def test_shared_lfl_matches_legacy_and_unknown_mixed_hoc(self):
        m={'fuel_groups':[{'heat_of_combustion_kJ_kg':20000.}]}
        np.testing.assert_allclose(screening_lfl(m,np.array([19.85,669.85])),[.07,.035])
        m['fuel_groups'].append({'heat_of_combustion_kJ_kg':30000.})
        self.assertEqual(screening_lfl(m,[300.]),[None])

class DoorTests(unittest.TestCase):
    def test_rules_and_override_priority(self):
        rooms=[{'id':'A','name':'T.P.S','size_m':[5,5,3]},{'id':'B','name':'일반실','size_m':[5,5,3]}]
        raw={'duration_s':3600,'rooms':rooms,'openings':[{'id':'D','a':'A','b':'B','kind':'door'}]}
        m,d=classify_doors(raw);self.assertEqual(d['rows'][0]['rule'],3)
        self.assertEqual(d['rows'][0]['probability'],.35);self.assertFalse('fire_door' in raw['openings'][0])
        m,d=classify_doors(raw,{'D':'ordinary'});self.assertFalse(m['openings'][0]['fire_door'])
        raw['openings'][0]['block_name']='FD-90';_,d=classify_doors(raw);self.assertEqual(d['rows'][0]['rule'],1)
    def test_inferred_probability_and_passage_preservation(self):
        raw={'duration_s':3600,'openings':[{'id':'D','a':'A','b':'B','kind':'door','fire_door':True,'door_class_confidence':'inferred'},
                                        {'id':'P','a':'A','b':'B','kind':'open_passage'}]}
        s=make_samples(raw);self.assertEqual(s[2]['openings'][0]['probability'],.35)
        self.assertTrue(s[1]['openings'][1]['open'])
if __name__=='__main__':unittest.main()
