import unittest
from types import SimpleNamespace
from copy import deepcopy
import numpy as np
from pyrocast_lite.montecarlo import make_samples,aggregate,condition_summary,intervals

class MCTests(unittest.TestCase):
    def setUp(self):
        self.raw={'duration_s':3600,'openings':[
            {'id':'F','kind':'door','fire_door':True,'a':'R1','b':'R2'},
            {'id':'D','kind':'door','a':'R1','b':'R2'},
            {'id':'W','kind':'window','a':'R1','b':'OUTSIDE'},
            {'id':'X','kind':'window','fixed_window':True,'a':'R2','b':'OUTSIDE'},
            {'id':'P','kind':'open_passage','a':'R1','b':'R2'}]}
    def test_reproducible_and_no_mutation(self):
        original=deepcopy(self.raw);a=make_samples(self.raw);b=make_samples(self.raw)
        self.assertEqual(a,b);self.assertEqual(self.raw,original)
        self.assertEqual(sum(s['kind']=='random' for s in a),18)
    def test_mandatory_and_effective_area(self):
        a=make_samples(self.raw,probabilities={'operable_window':1})
        states=lambda s:{o['id']:o for o in s['openings']}
        self.assertTrue(states(a[0])['F']['open'])
        self.assertTrue(states(a[1])['P']['open'])
        self.assertFalse(any(o['open'] for o in a[1]['openings'] if o['id']!='P'))
        self.assertEqual(states(a[2])['W']['effective_fraction'],.5)
        self.assertEqual(states(a[2])['D']['effective_fraction'],int(states(a[2])['D']['open']))
        self.assertFalse(states(a[2])['X']['open']);self.assertTrue(states(a[2])['P']['open'])
    def test_fixed_count_and_fixed_user_state(self):
        self.raw['openings']=[{'id':str(i),'kind':'door','a':'R1','b':'R2'} for i in range(10)]
        samples=make_samples(self.raw,mode='fixed_count',probabilities={'ordinary_door':.7})
        self.assertTrue(all(sum(o['open'] for o in s['openings'])==7 for s in samples[2:]))
        locked=make_samples(self.raw,mode='fixed_count',probabilities={'ordinary_door':.7},fixed_states={'0':False,'1':True})
        self.assertTrue(all(sum(o['open'] for o in s['openings'])==7 for s in locked[2:]))
        with self.assertRaises(ValueError):make_samples(self.raw,mode='fixed_count',probabilities={'ordinary_door':0},fixed_states={'1':True})
        fixed=make_samples(self.raw,fixed_states={'0':True,'1':False})
        for s in fixed:
            d={o['id']:o['open'] for o in s['openings']};self.assertTrue(d['0']);self.assertFalse(d['1'])
    def test_invalid_parameters(self):
        for kwargs in ({'probabilities':{'ordinary_door':1.1}},{'count':1},{'fixed_states':{'missing':True}}):
            with self.assertRaises(ValueError):make_samples(self.raw,**kwargs)
    def test_intervals_do_not_merge_gaps(self):
        r=intervals([False,True,True,False,True],[0,10,20,30,40])
        self.assertEqual([(x['start_sample_s'],x['end_sample_s']) for x in r],[(10,20),(40,40)])
    def test_boundary_original_room_not_cell_count(self):
        n=3;model=SimpleNamespace(N=n,sol=SimpleNamespace(t=np.array([0,10]),y=np.zeros((25,2))),
            manifest={'rule_settings':{'values':{'temperature_C':600}}})
        result={'ok':True,'flags':{k:np.zeros((3,2),bool).tolist() for k in ('flash','fgi','backdraft','unten')},
            'room_summary':[{'cell':'A0','original_room':'A','upper_max_C':580,'actual_peak_kW':0},
                            {'cell':'A1','original_room':'A','upper_max_C':700,'actual_peak_kW':0},
                            {'cell':'B','original_room':'B','upper_max_C':630,'actual_peak_kW':0}]}
        s=condition_summary(model,result,{'id':'s','kind':'random'})
        self.assertEqual(s['boundary_room_count'],1);self.assertEqual(s['boundary_cell_count'],2)
    def test_forced_and_failed_excluded_from_probability_denominator(self):
        def s(i,kind,hit):
            return {'sample_id':i,'kind':kind,'complete':True,'boundary_room_count':1,'original_room_count':2,
                'phenomena':{k:{'ever_room_count':int(hit),'first_s':10 if hit else None} for k in ('FO','FGI','backdraft','untenable')}}
        a=aggregate([s('a','random',True),s('b','random',False),s('c','all_openings_closed',True),
                     {'sample_id':'d','kind':'random','complete':False}])
        self.assertEqual(a['condition_sample_rates_random_only']['FO']['fraction'],.5)
        self.assertEqual(a['failure_fraction'],.25);self.assertIsNone(a['condition_sample_rates_random_only']['rollover']['fraction'])

if __name__=='__main__':unittest.main()
