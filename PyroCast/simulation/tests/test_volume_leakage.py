"""Equivalent ventilation paths: inputs and invariants, no native solver runs."""
import unittest
from copy import deepcopy
from pyrocast_cfbt.leakage import apply_minimum_leakage
from pyrocast_cfbt.basement_pressure import record_and_resize
from test_physics_p0 import sealed

class VolumeLeakage(unittest.TestCase):
    def area(self,m):
        apply_minimum_leakage(m)
        return sum(v['width_m']*(v['top_m']-v['bottom_m']) for v in m['openings'] if v.get('minimum_leakage'))

    def test_volume_proportional_and_no_pressure_notice_before_resize(self):
        a=sealed();b=deepcopy(a)
        for r in b['rooms']:r['size_m'][2]*=2
        self.assertAlmostEqual(self.area(b),2*self.area(a))
        self.assertAlmostEqual(self.area(a),6*327/(3600*8))
        self.assertFalse(any(s.startswith('지하 압력 간략식:') for s in a['limits']))
        self.assertTrue(any('실측 아님' in s for s in a['limits']))
        self.assertEqual(a['basement_pressure']['limit_Pa'],300)
        self.assertFalse(record_and_resize(a,299))

    def test_parking_area_not_volume_and_mixed_component(self):
        a=sealed();a['approved_input']={'room_uses':{'Fire':{'usage_class':'parking'}}}
        b=deepcopy(a);b['rooms'][0]['size_m'][2]*=10
        expected=(27*100+6*27)/(3600*8)
        self.assertAlmostEqual(self.area(a),expected)
        self.assertAlmostEqual(self.area(b),expected)
        row=a['below_grade_ventilation'][0]
        self.assertEqual(row['parking_area_m2'],100)
        self.assertEqual(row['general_below_volume_m3'],27)

    def test_partitioned_parking_uses_parent_usage(self):
        a=sealed();a['rooms'][0]['parent_room']='Original'
        a['approved_input']={'room_uses':{'Original':{'usage_class':'parking'}}}
        self.assertAlmostEqual(self.area(a),(27*100+6*27)/28800)

    def test_ground_minimum_and_geometry_unchanged(self):
        a=sealed()
        for r in a['rooms']:r.update(below_grade=False,origin_m=[0,0,0],leak_area_ratio=[0,0])
        self.assertEqual(self.area(a),.02)
        vent=next(v for v in a['openings'] if v.get('minimum_leakage'))
        self.assertEqual(vent['a'],'Stair');self.assertEqual(vent['width_m'],.02/2.1)
        self.assertEqual(a['below_grade_ventilation'],[])
        self.assertNotIn('basement_pressure',a)

    def test_explicit_ui_area_survives_repeated_normalization(self):
        for value in (.02,.04,.5):
            a=sealed();a['leakage_defaults']={k:value for k in ('stair_area_m2','elevator_area_m2','fallback_area_m2')}
            self.assertAlmostEqual(self.area(a),value)
            saved=deepcopy(a);self.assertAlmostEqual(self.area(a),value);self.assertEqual(a,saved)
            self.assertEqual(a['below_grade_ventilation'],[])
        a=sealed();a['leakage_area_m2']=.03;self.assertAlmostEqual(self.area(a),.03)

    def test_area_spreads_to_connected_rooms_without_clipping(self):
        a=sealed();a['rooms'][1]['size_m']=[.01,3,3]
        expected=6*(300+.09)/28800
        self.assertAlmostEqual(self.area(a),expected)
        vents=[v for v in a['openings'] if v.get('minimum_leakage')]
        self.assertEqual(len(vents),2)
        rooms={r['id']:r for r in a['rooms']}
        self.assertTrue(all(v['width_m']<=rooms[v['a']]['size_m'][0] for v in vents))

    def test_no_leak_if_real_ambient_path_and_no_double_count_for_two_fires(self):
        a=sealed();a['fuel_groups'].append(dict(room='Stair',initial_time_s=0))
        self.assertAlmostEqual(self.area(a),6*327/28800)
        self.assertEqual(len(a['below_grade_ventilation']),1)
        a['openings'].append(dict(id='Exit',a='Stair',b='OUTSIDE',schedule=[[0,1]]))
        self.assertEqual(self.area(a),0)

    def test_closed_door_excludes_neighbor_volume(self):
        a=sealed();a['openings'][0]['schedule']=[[0,0]]
        self.assertAlmostEqual(self.area(a),6*300/28800)

    def test_invalid_new_parameters_rejected(self):
        for key in ('below_grade_ach','parking_m3_h_m2','duct_velocity_m_s'):
            for value in (0,-1,float('nan'),float('inf'),True):
                a=sealed();a['leakage_defaults']={key:value}
                with self.assertRaises(ValueError):self.area(a)
