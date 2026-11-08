import unittest
from copy import deepcopy
from pyrocast_cfbt.leakage import apply_minimum_leakage


def sealed():
    return dict(rooms=[dict(id='Fire', size_m=[10,10,3], origin_m=[0,0,-3], below_grade=True),
                       dict(id='Stair', size_m=[3,3,3], origin_m=[20,0,-3], below_grade=True, core_kind='stair')],
                fuel_groups=[dict(id='Fuel',room='Fire',initial_time_s=0)],
                openings=[dict(id='Door',a='Fire',b='Stair',schedule=[[0,1]])])


class Leakage(unittest.TestCase):
    def test_closed_component_uses_stair_and_is_idempotent(self):
        m=sealed();apply_minimum_leakage(m)
        self.assertEqual(m['minimum_leakage'][0]['room'],'Stair')
        self.assertAlmostEqual(m['minimum_leakage'][0]['area_m2'],.02)
        before=deepcopy(m);apply_minimum_leakage(m);self.assertEqual(m,before)
        self.assertEqual(m['rooms'][0]['leak_area_ratio'],[0,0])

    def test_real_outdoor_path_is_preserved(self):
        m=sealed();m['openings'].append(dict(id='Exit',a='Stair',b='OUTSIDE',schedule=[[0,1]]))
        apply_minimum_leakage(m);self.assertEqual(m['minimum_leakage'],[])

    def test_closed_door_is_not_a_path_and_override_is_applied(self):
        m=sealed();m['openings'][0]['schedule']=[[0,0]]
        m['leakage_defaults']={'fallback_area_m2':.04}
        apply_minimum_leakage(m)
        self.assertEqual(m['minimum_leakage'][0]['room'],'Fire')
        self.assertAlmostEqual(m['minimum_leakage'][0]['area_m2'],.04)

    def test_numeric_grade_not_floor_spelling(self):
        for name in ('P1','B-1','Basement 1','-1F'):
            m=sealed();m['rooms'][0].pop('below_grade');m['rooms'][0]['cad_floor']=name
            apply_minimum_leakage(m);self.assertEqual(m['rooms'][0]['leak_area_ratio'],[0,0])

    def test_invalid_area_is_rejected(self):
        m=sealed();m['leakage_defaults']={'fallback_area_m2':0}
        with self.assertRaises(ValueError):apply_minimum_leakage(m)


class PhysicalValidation(unittest.TestCase):
    def test_pressure_fuel_and_combustion_failures_suppress_indices(self):
        import numpy as np
        from unittest.mock import patch
        from pyrocast_cfbt.validation import SPECIES, validate_native, protect_playback
        t=np.array([0.,1.]);mass={'Time':t};units={}
        for layer in ('UL','LL'):
            for species in SPECIES:
                k=f'{layer}M{species}_1';mass[k]=np.zeros(2);units[k]='kg'
        mass['ULMN2_1']=np.array([1.,1.]);mass['ULMTUHC_1']=np.array([0.,4.])
        c=dict(Time=t,PRS_1=np.array([0.,45000.]),HRR_1=np.array([0.,100.]),HRR_E1=np.array([0.,1000.]),PYROL_1=np.array([0.,8.]))
        model=dict(rooms=[dict(id='A',leak_area_ratio=[0,0])],openings=[])
        with patch('pyrocast_cfbt.native.read_native_csv',return_value=(mass,{},units)):
            v=validate_native(dict(compartments=c),model,'.')
        self.assertEqual(v['status'],'physically_invalid')
        self.assertEqual({r['check'] for r in v['reasons']},{'max_abs_pressure_Pa','max_upper_fuel_fraction','burned_fraction'})
        self.assertEqual(v['metrics']['mass_balance_error'],0)
        pb=dict(time_s=t.tolist(),solvers={'A':{'conditions':{'FO':{'scores':{'degree':[1,2]}}}}})
        protect_playback(pb,v)
        self.assertEqual(pb['solvers']['A']['conditions']['FO']['scores']['degree'],[None,None])

    def test_mass_ledger_missing_is_not_pass(self):
        import numpy as np
        from pyrocast_cfbt.validation import validate_native
        v=validate_native(dict(compartments={'Time':np.array([0,1]),'PRS_1':np.zeros(2)}),{},'nonexistent-p0-fixture')
        self.assertFalse(v['passed']);self.assertEqual(v['status'],'unverified')


class Ventilation(unittest.TestCase):
    def test_native_and_lite_use_same_explicit_flow(self):
        import json
        from pathlib import Path
        from pyrocast_lite.adapter import prepare
        from pyrocast_cfbt.deck import make_deck
        raw=json.loads((Path(__file__).resolve().parents[2]/'fixtures/room_rule_benchmark_3room.json').read_text('utf-8'))
        room=raw['rooms'][0]
        raw['mechanical_vents']=[dict(id='Supply',comp=room['id'],flow_m3_s=1.5,area=1.,height=.3)]
        model,_=prepare(raw)
        vents=model.input_model['mechanical_vents']
        self.assertAlmostEqual(sum(v['flow_m3_s'] for v in vents),1.5)
        self.assertEqual(len(model.mechanical_flows),len(vents))
        deck=make_deck(model.input_model,[],[])
        self.assertIn("TYPE='MECHANICAL'",deck)
        self.assertIn("ORIENTATIONS='VERTICAL','VERTICAL'",deck)
        self.assertIn('CUTOFFS=200,300',deck)
        from pyrocast_lite.runner import run
        run(model,10,5,30)
        self.assertTrue(model.integration['complete'])

    def test_bad_fan_cutoff_rejected(self):
        from pyrocast_cfbt.ventilation import validate_ventilation
        m=sealed();m['mechanical_vents']=[dict(id='Fan',comp='Fire',flow_m3_s=1,area=1,height=2,cutoffs=[300,200])]
        with self.assertRaises(ValueError):validate_ventilation(m)


class Criteria(unittest.TestCase):
    def evaluate(self,room='Fire',**kw):
        from pyrocast_cfbt.criteria import evaluate_cell
        model=sealed();model['fuel_groups'][0]['heat_of_combustion_kJ_kg']=18100
        values=dict(temperature=[35.],interface=[1.],oxygen=[3.],fuel=[.78],solid_kW=[0.])
        values.update(kw)
        return evaluate_cell(model,next(r for r in model['rooms'] if r['id']==room),[3300.],**values)

    def test_cold_rich_origin_has_bd_potential_but_not_fgi(self):
        r=self.evaluate()
        self.assertGreaterEqual(r['backdraft']['potential'][0],1)
        self.assertAlmostEqual(r['backdraft']['potential'][0],17.9/10.9)
        self.assertIsNone(r['FGI']['proximity'][0]);self.assertFalse(r['FGI']['gate'][0])
        self.assertFalse(r['backdraft']['occurred'][0])
        self.assertTrue(self.evaluate(opening_increased=[True])['backdraft']['occurred'][0])

    def test_shallow_layer_is_unassessed_even_if_rich(self):
        for key in ('FO','FGI','backdraft'):
            self.assertEqual(self.evaluate(interface=[2.94])[key]['proximity'],[None])

    def test_ambient_clean_room_has_zero_or_not_applicable(self):
        r=self.evaluate(room='Stair',temperature=[20],oxygen=[20.9],fuel=[0])
        for key in ('FO','FGI','backdraft'):self.assertIn(r[key]['proximity'][0],(None,0))

    def test_fo_uses_ambient_relative_temperature_or_flux(self):
        self.assertEqual(self.evaluate(temperature=[20],solid_kW=[100])['FO']['proximity'],[0])
        self.assertTrue(self.evaluate(temperature=[20],solid_kW=[100],flux_kW_m2=[21])['FO']['occurred'][0])
        self.assertAlmostEqual(self.evaluate(temperature=[310],solid_kW=[100])['FO']['proximity'][0],.5)

    def test_fgi_cold_adjacent_and_too_rich(self):
        r=self.evaluate(room='Stair',temperature=[25],oxygen=[20],fuel=[.1])
        self.assertGreaterEqual(r['FGI']['proximity'][0],1)
        self.assertTrue(r['FGI']['occurred'][0])
        rich=self.evaluate(room='Stair',temperature=[25],oxygen=[20],fuel=[.78])
        self.assertTrue(rich['FGI']['too_rich'][0]);self.assertEqual(rich['FGI']['proximity'][0],0)
        self.assertIsNone(self.evaluate(room='Stair',solid_kW=[1])['FGI']['proximity'][0])

    def test_rollover_is_independent_and_includes_origin(self):
        r=self.evaluate(bulk_kW=[10])
        self.assertTrue(r['rollover']['active'][0]);self.assertIsNone(r['FGI']['proximity'][0])
