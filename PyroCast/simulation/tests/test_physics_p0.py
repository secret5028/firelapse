import unittest
from copy import deepcopy
from pyrocast_cfbt.leakage import apply_minimum_leakage


def sealed():
    return dict(rooms=[dict(id='Fire', size_m=[10,10,3], origin_m=[0,0,-3], below_grade=True),
                       dict(id='Stair', size_m=[3,3,3], origin_m=[20,0,-3], below_grade=True, core_kind='stair')],
                fuel_groups=[dict(id='Fuel',room='Fire',initial_time_s=0)],
                openings=[dict(id='Door',a='Fire',b='Stair',schedule=[[0,1]])])


class Leakage(unittest.TestCase):
    def test_assumed_leaks_are_not_mc_openings_or_source_cap(self):
        from pyrocast_lite.montecarlo import make_samples
        from pyrocast_lite.screening_v8_approved import origin_budgets
        model=sealed();model['duration_s']=1800
        model['openings'][0].update(kind='door',width_m=1.,bottom_m=0,top_m=2.)
        model['fuel_groups'][0].update(energy_MJ=1000,hrrpua_kW_m2=250)
        model['approved_input']={'room_uses':{}}
        budgets=origin_budgets(model)
        apply_minimum_leakage(model)
        self.assertEqual(budgets,origin_budgets(model))
        samples=make_samples(model,count=2)
        self.assertTrue(model['minimum_leakage'])
        for s in samples:
            self.assertEqual({v['id'] for v in s['scenario']['openings']},{'Door'})
            self.assertEqual({v['id'] for v in s['openings']},{'Door'})
            apply_minimum_leakage(s['scenario'])
            self.assertTrue(s['scenario']['minimum_leakage'])

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
    def test_external_flow_sign_uses_csv_reference_for_all_vent_types(self):
        import numpy as np
        from unittest.mock import patch
        from pyrocast_cfbt.validation import SPECIES, validate_native
        t=np.array([0.,1.]);mass={'Time':t};units={}
        for layer in ('UL','LL'):
            for species in SPECIES:
                k=f'{layer}M{species}_1';mass[k]=np.zeros(2);units[k]='kg'
        mass['ULMN2_1']=np.array([1.,2.])
        c=dict(Time=t,PRS_1=np.zeros(2),HRR_1=np.ones(2),HRR_E1=np.ones(2))
        for prefix in ('WT','CFT','MT'):
            for reference in ('1','Outside'):
                vents={f'{prefix}_{reference}_{layer}_{direction}_1':np.ones(2) if layer=='u' and direction==('outflow' if reference=='Outside' else 'inflow') else np.zeros(2) for layer in ('u','l') for direction in ('inflow','outflow')}
                model=dict(rooms=[dict(id='A',leak_area_ratio=[0,0])],openings=[],mechanical_vents=[])
                if prefix=='MT':model['mechanical_vents']=[dict(id='V',comp='A',direction='supply')]
                else:model['openings']=[dict(id='V',a='A',b='OUTSIDE',type='FLOOR' if prefix=='CFT' else 'WALL')]
                with patch('pyrocast_cfbt.native.read_native_csv',return_value=(mass,{},units)):
                    result=validate_native(dict(compartments=c,native_vents=vents,native_vents_ids={k:'V' for k in vents}),model,'.')
                self.assertTrue(result['passed'],(prefix,reference,result))

    def test_pressure_failure_suppresses_indices_but_rich_fuel_is_review(self):
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
        self.assertEqual({r['check'] for r in v['reasons']},{'max_abs_pressure_Pa'})
        self.assertEqual(v['review_required'][0]['check'],'upper_fuel_accumulation')
        self.assertEqual(v['warnings'][0]['check'],'low_source_hrr_energy_ratio')
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
            self.assertEqual(self.evaluate(interface=[2.94])[key]['gate'],[None])
            self.assertEqual(self.evaluate(interface=[2.94])[key]['occurred'],[None])

    def test_missing_fuel_is_unknown_not_negative(self):
        self.assertEqual(self.evaluate(room='Stair',fuel=[None])['FGI']['occurred'],[None])

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

    def test_wando_r5_explicit_fgi_oxygen_not_replaced_by_native_combustion_limit(self):
        from pyrocast_cfbt.criteria import evaluate_cell
        model=sealed();model['fuel_groups'][0]['heat_of_combustion_kJ_kg']=25000
        model['gas']={'native_lower_oxygen_limit_mass_fraction':.15}
        model['criteria']={'fgi_oxygen_vol_percent':10}
        room=model['rooms'][1];room['size_m'][2]=6.405
        r=evaluate_cell(model,room,[2305],[421.723130638],[2.39530866637],[11.4096635957],[.04446537048911817],[0])
        self.assertAlmostEqual(r['FGI']['proximity'][0]*100,114.096635957)
        self.assertTrue(r['FGI']['occurred'][0])
        model['gas']['native_lower_oxygen_limit_mass_fraction']=.18
        other=evaluate_cell(model,room,[2305],[421.723130638],[2.39530866637],[11.4096635957],[.04446537048911817],[0])
        self.assertEqual(r['FGI']['proximity'],other['FGI']['proximity'])

    def test_rollover_is_independent_and_includes_origin(self):
        r=self.evaluate(bulk_kW=[10])
        self.assertTrue(r['rollover']['active'][0]);self.assertIsNone(r['FGI']['proximity'][0])


class Tactics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import sys,json
        from pathlib import Path
        root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/'tools'))
        from d5_match import matches
        cls.matches=staticmethod(matches)
        cls.rules={r['code']:r for r in json.loads((root/'config/tactic_rules.json').read_text('utf-8'))['rules']}

    def test_rich_cold_hypoxic_state_never_advances(self):
        facts=dict(FO=0,FGI=0,backdraft=0,BD_potential=17.9/10.9,FGI_proximity=None,
                   validity_passed=True,active_fire=False,bd_raw_hazard=True,Tu=35)
        self.assertFalse(self.matches(self.rules['C-1'],facts))
        self.assertTrue(self.matches(self.rules['B-0'],facts))
        self.assertIn('각별한 주의',self.rules['B-0']['text'])
        self.assertNotIn('개방 금지',self.rules['B-0']['text'])

    def test_burning_room_and_unverified_result_never_advance(self):
        clean=dict(FO=0,FGI=0,backdraft=0,BD_potential=0,FGI_proximity=0,
                   validity_passed=True,active_fire=False,bd_raw_hazard=False)
        self.assertTrue(self.matches(self.rules['C-1'],clean))
        self.assertFalse(self.matches(self.rules['C-1'],dict(clean,active_fire=True)))
        self.assertFalse(self.matches(self.rules['C-1'],dict(clean,validity_passed=False)))
        for rule in self.rules.values():
            self.assertFalse(self.matches(rule,dict(clean,physically_invalid=True)))

    def test_fgi_warning_has_no_temperature_rise_gate(self):
        self.assertTrue(self.matches(self.rules['G-1'],dict(route_room=True,FGI_proximity=.8,temperature_rising=False,Tu=20)))

    def test_invalid_briefing_contains_no_tactical_rules(self):
        from lite_ai_briefing import briefing_value,basic_briefing
        class Service:
            def case(self,a):return dict(physical_validation={'status':'physically_invalid'},limits=['물리 타당성 검사 실패: 압력'])
        for fn in (briefing_value,basic_briefing):
            value=fn(Service(),dict(building='B',case='C'))
            self.assertEqual(value['rules'],[]);self.assertNotIn('전진',value['text'])
