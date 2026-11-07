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
