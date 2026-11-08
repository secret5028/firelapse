import json,unittest
from copy import deepcopy
from pathlib import Path
import numpy as np
from building_rules import usage_class
from pyrocast_cfbt.room_rule import ventilation_cap,supply_curve
from pyrocast_cfbt.room_rule_r8 import prepare_native
from pyrocast_cfbt.input_basis import growth_for,describe
from pyrocast_lite.screening_v8_approved import origin_budgets,scenario
from pyrocast_lite import screening_v7
ROOT=Path(__file__).resolve().parents[2]

class InputDefaults(unittest.TestCase):
    def raw(self):return json.loads((ROOT/'fixtures/room_rule_benchmark_3room.json').read_text('utf8'))

    def test_closed_external_does_not_mask_open_internal(self):
        raw=self.raw();rid='R2'
        raw['openings']=[dict(id='door',a='R1',b=rid,width_m=1,top_m=2,schedule=[[0,1]]),
                         dict(id='window',a=rid,b='OUTSIDE',width_m=2,top_m=2,schedule=[[0,0]])]
        before=deepcopy(raw);cap=ventilation_cap(raw,rid,1,True)
        self.assertEqual(cap['opening']['opening_id'],'door');self.assertGreater(cap['cap_kW'],0)
        self.assertEqual(raw,before)

    def test_sealed_room_retains_fuel_budget(self):
        raw=self.raw();raw['openings']=[]
        g=deepcopy(raw['fuel_groups'][1]);g['room_vent_cap']=ventilation_cap(raw,g['room'],1,True)
        curve=supply_curve(g,20,dict(ramp_s=60,decay_energy_fraction=.3,vent_cap_enabled=True))
        self.assertGreater(max(curve['q']),0)
        self.assertAlmostEqual(np.trapezoid(curve['q'],curve['t'])/1000,g['energy_MJ'])

    def test_mixed_labels_do_not_omit_fuel_as_toilet(self):
        cls,evidence=usage_class(['화장실','복도','휴게음식점'],'retail')
        self.assertEqual(cls,'default');self.assertTrue(evidence['review_required'])
        self.assertEqual(usage_class(['여자 화장실'],'factory')[0],'toilet')
        self.assertEqual(usage_class(['DA'],'warehouse')[0],'shaft_room')

    def test_growth_classes_differ_and_energy_is_conserved(self):
        from pyrocast_cfbt.deck import fire_curve
        from unittest.mock import patch
        raw=self.raw();raw['approved_input']={'room_uses':{r['id']:{'usage_class':'hotel_room'} for r in raw['rooms']}}
        budgets=origin_budgets(raw)
        self.assertAlmostEqual(budgets['R1']['growth_kW_s2'],1000/300**2)
        self.assertNotEqual(growth_for({'class':'hotel_room'})['growth_kW_s2'],growth_for({'class':'shopping'})['growth_kW_s2'])
        prepared=deepcopy(raw);prepared['room_rule_r8']={};prepared['screening_source']={}
        with patch.object(screening_v7,'scenario',return_value=prepared):
            out=scenario({'origin_budgets':budgets},'R1','closed')
        group=next(g for g in out['fuel_groups'] if g['room']=='R1')
        t,q,_=fire_curve(group,20)
        self.assertAlmostEqual(group['growth_kW_s2'],1000/300**2)
        self.assertAlmostEqual(np.trapezoid(q,t)/1000,group['energy_MJ'])

    def test_closed_native_standby_curves_nonzero(self):
        raw=self.raw()
        for v in raw['openings']:v['schedule']=[[0,0]]
        model,targets,manifest=prepare_native(raw)
        for g in model['fuel_groups']:
            self.assertGreater(max(g['room_rule_curve']['q']),0)
            self.assertAlmostEqual(np.trapezoid(g['room_rule_curve']['q'],g['room_rule_curve']['t'])/1000,g['energy_MJ'],places=6)

    def test_unknown_fan_is_distinct_from_explicit_off(self):
        raw=self.raw();raw['approved_input']={'room_uses':{'R1':dict(load_MJ_m2=500,table_basis=None,classification_basis={'review_required':True,'reason':'mixed'})}}
        before=deepcopy(raw);info=describe(raw)
        self.assertIn('미입력',info['ventilation']);self.assertEqual(len(info['review_rooms']),2)
        self.assertEqual(raw,before)
        raw['ventilation_assumptions']={'R1':dict(ach=0,mode='off')}
        self.assertIn('0 ACH',describe(raw)['ventilation'])

    def test_monte_carlo_preserves_class_growth_and_nonzero_standby(self):
        from pyrocast_lite.montecarlo import make_samples
        raw=self.raw();raw['duration_s']=1800
        for vent in raw['openings']:vent.setdefault('kind','door')
        first=next(g for g in raw['fuel_groups'] if 'initial_time_s' in g)
        first['growth_kW_s2']=growth_for({'class':'hotel_room'})['growth_kW_s2']
        for sample in make_samples(raw,seed=37,count=4):
            copied=next(g for g in sample['scenario']['fuel_groups'] if 'initial_time_s' in g)
            self.assertEqual(copied['growth_kW_s2'],first['growth_kW_s2'])
            model,_,_=prepare_native(sample['scenario'])
            self.assertTrue(all(max(g['room_rule_curve']['q'])>0 for g in model['fuel_groups']))

if __name__=='__main__':unittest.main()
