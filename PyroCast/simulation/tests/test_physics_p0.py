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
