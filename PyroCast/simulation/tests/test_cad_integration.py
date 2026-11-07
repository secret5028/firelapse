import csv
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from pyrocast_cfbt.native import read_native_csv
from pyrocast_cfbt.deck import active_fuels, make_deck, candidates, opening_frame
from pyrocast_cfbt.model import normalize
from pyrocast_cfbt.exposure import _polygon_exit
from pyrocast_cfbt.playback import fire_visuals
from pyrocast_cfbt.native import digest
from pyrocast_cfbt.cad import opening_candidates, geometry_dependencies
import json

ROOT=Path(__file__).resolve().parents[1]


class CadIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.model=normalize(json.loads((ROOT/'examples/three_rooms.json').read_text()))

    def test_basement_uses_explicit_connections_without_default_outdoor_leakage(self):
        raw=deepcopy(self.model)
        raw['rooms'][0].update(cad_floor='B3',below_grade=True)
        raw['rooms'][1]['cad_floor']='1F'
        raw['rooms'][2].update(cad_floor='지하 2층',leak_area_ratio=[.0001,0.])
        model=normalize(raw)
        rooms=model['rooms']
        self.assertEqual(rooms[0]['leak_area_ratio'],[0.,0.])
        self.assertNotIn('leak_area_ratio',rooms[1])
        self.assertEqual(rooms[2]['leak_area_ratio'],[.0001,0.])
        self.assertEqual(model['openings'],self.model['openings'])
        from pyrocast_lite.shared_inputs import read_shared
        model['fuel_groups']=[g for g in model['fuel_groups'] if 'initial_time_s' in g]
        leak_rooms={leak['room'] for leak in read_shared(model)['leak_vents']}
        self.assertNotIn(rooms[0]['id'],leak_rooms)
        self.assertIn(rooms[1]['id'],leak_rooms)
        self.assertIn(rooms[2]['id'],leak_rooms)

    def test_uniform_fuel_cells_stay_inside_concave_room_and_preserve_budget_weights(self):
        geometry_dependencies(Path.home()/'Documents/Codex/2026-10-14/files-pasted-by-the-user-cad3d')
        from pyrocast_cfbt.fuel_layout import layout
        from pyrocast_cfbt.cad import footprint
        from pyrocast_cfbt.exposure import emission_samples
        from shapely.geometry import box
        room={'key':'CAD_TEST','z_m':10,'cad_polys':[{'o':[[0,0],[12,0],[12,4],[6,4],[6,12],[0,12]],
            'h':[[[1,1],[3,1],[3,3],[1,3]]]}]}
        anchors=[{'xyz':[.6,6,10.76],'opening_id':'D1'},{'xyz':[20,20,10.76],'opening_id':'OUT'}]
        units=layout(room,anchors);shape=footprint(room['cad_polys'])
        self.assertGreater(len(units),4)
        self.assertAlmostEqual(sum(u['budget_fraction'] for u in units),1.)
        self.assertTrue(any(u['opening_id']=='D1' for u in units))
        self.assertFalse(any(u['opening_id']=='OUT' for u in units))
        for u in units:
            x,y,z=u['position_m'];e=u['edge_m']/2
            self.assertTrue(shape.covers(box(x-e,y-e,x+e,y+e)))
        samples=emission_samples(room,{'fuel_units':units},[.6,6,10.76],4)
        self.assertLessEqual(len(samples),4)
        self.assertAlmostEqual(sum(w for _,w in samples),1.)
        self.assertAlmostEqual(sum(5000*w for _,w in samples),5000.)

    def test_fuel_surface_and_explicit_plume_base_are_separate_without_changing_threshold(self):
        from pyrocast_cfbt.spread import assess
        material=deepcopy(self.model['material']);t=np.array([0.,5.])
        target={'id':'T','room':'R2','group':'reserve_R2','xyz':[6,2,.6],
                'solver_xyz':[6,2,.6],'fire_source_xyz':[6,2,.02],
                'solver_fire_xyz':[6,2,.02],'fire_source_base_m':.02,
                'material':material,'normal':[0,0,1]}
        response={'crossing_s':3.,'surface_C':np.array([20.,400.]),
                  'absorbed_kJ_m2':np.array([0.,100.]),'energy_residual_kJ_m2':0.}
        with patch('pyrocast_cfbt.spread.room_series',return_value={}), \
             patch('pyrocast_cfbt.spread.device_series',return_value=np.zeros(2)), \
             patch('pyrocast_cfbt.spread.supplementary',return_value=({'aperture':np.zeros(2)},np.zeros(2,bool))), \
             patch('pyrocast_cfbt.spread.plate',return_value=response) as thermal:
            events,_,_=assess(self.model,{'zone':{'Time':t}},[target],[])
        self.assertEqual(events[0]['xyz'],[6,2,.02])
        self.assertEqual(events[0]['surface_xyz'],[6,2,.6])
        self.assertEqual(events[0]['solver_xyz'],[6,2,.02])
        self.assertEqual(thermal.call_args.args[0]['ignition_C'],material['ignition_C'])

    def test_native_fire_order_follows_commits_and_preserves_initial_index(self):
        model=self.model
        model['fuel_groups']=list(reversed(model['fuel_groups']))
        events=[{'group':'reserve_R3','t_ign_s':10,'xyz':[10,2,.02]},
                {'group':'reserve_R2','t_ign_s':20,'xyz':[6,2,.02]}]
        self.assertEqual([g['id'] for g in active_fuels(model,events)],['primary','reserve_R3','reserve_R2'])
        deck=make_deck(model,events,candidates(model))
        fire_lines=[line for line in deck.splitlines() if line.startswith('&FIRE')]
        self.assertIn("F_primary",fire_lines[0]);self.assertIn("F_reserve_R3",fire_lines[1])
        self.assertIn("F_reserve_R2",fire_lines[2])

    def test_committed_fire_keeps_ignition_height_in_native_table(self):
        model=self.model
        event={'group':'reserve_R2','t_ign_s':20,'xyz':[4.12,2,.76]}
        deck=make_deck(model,[event],candidates(model))
        rows=[line for line in deck.splitlines() if line.startswith("&TABL ID='F_reserve_R2' DATA=")]
        self.assertTrue(rows)
        self.assertTrue(all(float(line.split('DATA=')[1].split(',')[2])==.76 for line in rows))
        self.assertIn('LOCATION=0.12,2 IGNITION_CRITERION',deck)

    def test_cad_candidates_receive_through_aperture_and_reject_closed_exterior_and_holes(self):
        try:
            geometry_dependencies(Path.home()/'Documents/Codex/2026-10-14/files-pasted-by-the-user-cad3d')
        except ImportError:self.skipTest('CAD Shapely dependency unavailable')
        room={'id':'CAD_R2','z_m':10.,'height_m':3.,'cad_polys':[{'o':[[4,0],[8,0],[8,4],[4,4]],'h':[]}]}
        solver={'id':'R2','cad_bounds_m':[4,0,8,4],'origin_m':[100,0,10.],'size_m':[8,2,3]}
        door={'id':'D','a':'merged_a','b':'merged_b','cad_a':'CAD_R1','cad_b':'CAD_R2','schedule':[[0,1]],
              'cad_geometry':{'center_m':[4,2,10.],'normal_a_to_b':[1,0,0]}}
        group={'id':'fuel'}
        points=opening_candidates(room,solver,group,self.model['material'],[door])
        self.assertEqual(len(points),2)
        np.testing.assert_allclose(points[0]['xyz'],[4.6,2,10.76])
        np.testing.assert_allclose(points[0]['solver_xyz'],[101.2,1,10.76])
        self.assertEqual(points[0]['normal'],[-1,0,0]);self.assertEqual(points[0]['source_cad_key'],'CAD_R1')
        self.assertEqual({p['shared_budget_group'] for p in points},{'fuel'})
        closed=deepcopy(door);closed['schedule']=[[0,0]]
        outside=deepcopy(door);outside['cad_a']='OUTSIDE'
        self.assertEqual(opening_candidates(room,solver,group,self.model['material'],[closed,outside]),[])
        room['cad_polys'][0]['h']=[[[5.2,1.5],[5.8,1.5],[5.8,2.5],[5.2,2.5]]]
        self.assertEqual(len(opening_candidates(room,solver,group,self.model['material'],[door])),1)

    def test_physical_cad_frame_does_not_use_native_origin(self):
        opening=deepcopy(self.model['openings'][0])
        opening['cad_geometry']={'center_m':[42,18,16.1],'tangent':[0,1,0],'normal_a_to_b':[1,0,0]}
        frame=opening_frame(opening,{r['id']:r for r in self.model['rooms']})
        np.testing.assert_allclose(frame[0],[42,18,16.1])
        self.model['rooms'][1]['origin_m']=[100,0,0]
        target={'id':'C_CAD','room':'R2','group':'reserve_R2','xyz':[42.5,18,.76],
                'solver_xyz':[101.5,2,.76],'normal':[0,0,1],'label':'representative_plate','material':self.model['material']}
        self.model['explicit_candidates']=[target]
        deck=make_deck(self.model,[],candidates(self.model))
        self.assertIn('LOCATION=1.5,2.0,0.76',deck)
        self.assertNotIn('LOCATION=-57.5',deck)

    def test_polygon_ray_stops_at_hole_and_outer_boundary(self):
        poly={'o':[[-2,-4],[2,-4],[2,0],[-2,0]],'h':[[[-.5,-3],[.5,-3],[.5,-2],[-.5,-2]]]}
        self.assertAlmostEqual(_polygon_exit(np.array([0.,0.,1.]),np.array([0.,-1.,0.]),[poly]),2.)
        self.assertAlmostEqual(_polygon_exit(np.array([1.,0.,1.]),np.array([0.,-1.,0.]),[poly]),4.)

    def test_wrapped_zone_csv_keeps_interior_blank_units(self):
        base=ROOT/'results/unit_tmp';base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as directory:
            path=Path(directory)/'wide.csv';count=16400
            names=['Time']+['V_'+str(i) for i in range(1,count)]
            units=['s']+['C']*(count-1);units[100]=''
            records=[units,names,[0.]+[1.]*(count-1),[5.]+[2.]*(count-1)]
            with path.open('w',newline='') as stream:
                writer=csv.writer(stream)
                for row in records:
                    writer.writerow(row[:16384]+['']);writer.writerow(row[16384:])
            values,ids,loaded_units=read_native_csv(path)
            self.assertEqual(len(values),count);self.assertEqual(loaded_units['V_100'],'')
            np.testing.assert_array_equal(values['Time'],[0,5]);np.testing.assert_array_equal(values['V_16399'],[1,2])
            with path.open('a') as stream:stream.write('10,incomplete_future_record\n')
            prefix,_,_=read_native_csv(path,until_s=5)
            np.testing.assert_array_equal(prefix['Time'],[0,5])
            with self.assertRaises(ValueError):read_native_csv(path)

    def test_floor_vent_has_native_deck_and_order_validation(self):
        model=self.model
        model['openings'].append({'id':'V_CAD','type':'FLOOR','a':'R3','b':'R1','area_m2':2,'schedule':[[0,1]]})
        normalize(model)
        deck=make_deck(model,[],[])
        self.assertIn("TYPE='FLOOR' ID='V_CAD'",deck)
        model['openings'].insert(0,model['openings'].pop())
        with self.assertRaisesRegex(ValueError,'Wall vents must precede'):
            normalize(model)

    def test_real_view_uses_matching_native_height_and_time_varying_input_area(self):
        base=ROOT/'results/unit_tmp';base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as directory:
            folder=Path(directory)
            (folder/'case.in').write_text("&CHEM ID='F_primary' RADIATIVE_FRACTION=0.35 /\n"
                "&TABL ID='F_primary' DATA=0,0,0,0.1 /\n&TABL ID='F_primary' DATA=10,1,0,2 /\n"
                "&CHEM ID='F_added' RADIATIVE_FRACTION=0.35 /\n"
                "&TABL ID='F_added' DATA=0,0,0,0.1 /\n&TABL ID='F_added' DATA=10,1,0,1 /\n",encoding='ascii')
            (folder/'case_compartments.csv').write_text('Time,HRR_1,FLHGT_1,HRR_2,FLHGT_2,PYROL_1,IGN_1,PYROL_2,IGN_2\n'
                'Simulation Time,HRR,height,HRR,height,pyrol,ign,pyrol,ign\nTime,F_primary,F_primary,F_added,F_added,F_primary,F_primary,F_added,F_added\ns,W,m,W,m,kg/s,,kg/s,\n'
                '0,0,0,0,0,0,1,0,0\n10,1000,2.2,500,1.1,.05,1,.025,1\n',encoding='ascii')
            result={'scenario':{'fuel_groups':[{'id':'added'},{'id':'primary','initial_time_s':0}]},
                    'ignitions':[{'group':'added','t_ign_s':5}], 'time_s':[0,10],
                    'runs':[{'folder':str(folder)}],'final_input_sha256':digest(folder/'case.in'),
                    'solid_fuel_inventory':{'primary':{'actual_HRR_W':[0,1000]},'added':{'actual_HRR_W':[0,500]}}}
            visuals=fire_visuals(result)
            np.testing.assert_array_equal(visuals['primary']['flame_height_m'],[0,2.2])
            self.assertAlmostEqual(visuals['primary']['area_m2'][1],2.)
            self.assertAlmostEqual(visuals['added']['area_m2'][1],.55)
            self.assertEqual(visuals['primary']['combustion_state'],['activated_no_supply','burning'])
            self.assertEqual(visuals['added']['combustion_state'],['inactive','burning'])
            self.assertEqual(result['solid_fuel_inventory']['primary']['actual_HRR_W'],[0,1000])
            result['solid_fuel_inventory']['added']['actual_HRR_W']=[0,1234]
            with self.assertRaisesRegex(ValueError,'active fire ordering'):
                fire_visuals(result)


if __name__=='__main__':unittest.main()
