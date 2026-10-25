from copy import deepcopy
import json
from pathlib import Path
import tempfile
import hashlib
import unittest
from unittest.mock import patch
import numpy as np

from pyrocast_cfbt.cad import adapt,resolve_building,dedicated_core_kind
from pyrocast_cfbt.model import normalize
from pyrocast_cfbt.practical import apply_profile,room_defaults
from pyrocast_cfbt.exposure import emission_points
from pyrocast_cfbt.flashover import source_curves,integral
from pyrocast_cfbt.spread import assess

ROOT=Path(__file__).resolve().parents[1]


def building_fixture():
    def rectangle(a,b,c,d):return [{'o':[[a,b],[c,b],[c,d],[a,d]],'h':[]}]
    return {'structure':'steel','floors':[{'name':'GF','z':0.,'h':3.,
        'rooms':[{'id':'Office','names':['office'],'polys':rectangle(0,0,4,4)},
                 {'id':'Passage','names':['corridor'],'polys':rectangle(4,0,8,4)}],
        'openings':[{'id':'Door','polys':[[[3.95,1],[4.05,1],[4.05,2],[3.95,2]]]}],
        'simulation_graph':{'connections':[{'id':'Door','sides':['Office','Passage'],'kind':'door',
             'dimensions':{'width_m':1.,'bottom_m':0.,'top_m':2.1}}]}}]}


class PracticalTests(unittest.TestCase):
    def temp(self):
        root=ROOT/'results/unit_tmp';root.mkdir(parents=True,exist_ok=True)
        return tempfile.TemporaryDirectory(dir=root)

    def test_new_building_without_legacy_files_or_3f_r9(self):
        with self.temp() as directory:
            path=Path(directory)/'building.json';path.write_text(json.dumps(building_fixture()))
            model=normalize(adapt(path))
        self.assertEqual(model['cad']['fire_key'],'CAD_GF_Office')
        self.assertEqual(len(model['fuel_groups']),2)
        self.assertTrue(model['explicit_candidates'])
        self.assertFalse(model['gas']['vent_gate_enabled'])
        self.assertEqual(model['gas']['activation_J_mol'],0.)
        self.assertTrue(model['flashover']['enabled'])
        self.assertEqual(model['flashover']['radiation_points'],4)
        passage=next(g for g in model['fuel_groups'] if g['usage']=='passage')
        self.assertEqual(passage['energy_MJ'],16*30)
        self.assertAlmostEqual(passage['fuel_area_m2'],16*.05)
        self.assertIn('light',model['wall_material']['basis'])

    def test_mixed_industrial_hall_does_not_become_low_fuel(self):
        self.assertEqual(room_defaults({'names':['ELEV.홀','Assembly Line','우레탄']},{})['usage'],'process_or_storage')
        self.assertIsNone(dedicated_core_kind({'names':['주차장','계단실 1','발전기실','문서창고','상부OPEN']}))

    def test_single_floor_core_identity_does_not_require_vertical_links(self):
        raw=building_fixture();floor=raw['floors'][0]
        floor['rooms'][1]['names']=[];floor['rooms'][1]['tags']=['stair_inside']
        # No OCR name and no vertical connection: the CAD tag still identifies stairs.
        with self.temp() as directory:
            path=Path(directory)/'building.json';path.write_text(json.dumps(raw))
            model=normalize(adapt(path,{'scope_floor':'GF'}))
        core=next(r for r in model['rooms'] if r['cad_room']=='Passage')
        self.assertEqual(core['core_kind'],'stair')
        self.assertTrue(core['shaft'])
        self.assertFalse(any(g['room']==core['id'] for g in model['fuel_groups']))
        self.assertTrue(any('계단' in w for w in model['cad']['warnings']))

    def test_dedicated_core_node_without_tags_and_elevator_hall_distinction(self):
        raw=building_fixture();floor=raw['floors'][0]
        floor['rooms'][0]['names']=['ELEV.홀']
        raw['core_nodes']=[{'floor':'GF','core_id':'C1','room_id':'Passage','kind':'elev'}]
        with self.temp() as directory:
            path=Path(directory)/'building.json';path.write_text(json.dumps(raw))
            model=normalize(adapt(path,{'scope_floor':'GF'}))
        byid={r['cad_room']:r for r in model['rooms']}
        self.assertEqual(byid['Passage']['core_kind'],'elev')
        self.assertIsNone(byid['Office']['core_kind'])

    def test_clear_height_tag_remaps_current_geometry_and_checks_source_hash(self):
        raw=building_fixture();floor=raw['floors'][0];raw['origin']=[0,0];floor['shift']=[0,0]
        with self.temp() as directory:
            root=Path(directory);source=root/'drawing.dxf';source.write_bytes(b'test DXF identity')
            floor['provenance']={'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
            path=root/'building.json';path.write_text(json.dumps(raw))
            (root/'work').mkdir();audit=root/'work/cfast_ceiling_heights_v30.json'
            audit.write_text(json.dumps({'building_sha256':'old_geometry_hash',
                'all_tags':[{'height_m':2.7,'native_point':[2000,2000],'source':str(source)}]}))
            model=normalize(adapt(root,{'scope_floor':'GF'}))
            office=next(r for r in model['rooms'] if r['cad_room']=='Office')
            self.assertEqual(office['size_m'][2],2.7)
            self.assertEqual(office['structural_height_m'],3.)
            self.assertEqual(office['height_confidence'],'tag_interpretation')
            source.write_bytes(b'changed unrelated drawing')
            changed=normalize(adapt(root,{'scope_floor':'GF'}))
            self.assertEqual(next(r for r in changed['rooms'] if r['cad_room']=='Office')['size_m'][2],3.)

    def test_explicit_room_height_precedes_floor_height(self):
        raw=building_fixture();raw['floors'][0]['ceil_h']=2.8
        raw['floors'][0]['rooms'][0]['clear_height_m']=2.6
        with self.temp() as directory:
            path=Path(directory)/'building.json';path.write_text(json.dumps(raw))
            model=normalize(adapt(path))
        self.assertEqual([r['size_m'][2] for r in model['rooms']],[2.6,2.8])

    def test_unicode_floor_and_room_ids_preserve_display_labels(self):
        raw=building_fixture();floor=raw['floors'][0];floor['name']='지상1층'
        floor['rooms'][0]['id']='사무실';floor['rooms'][1]['id']='복도'
        floor['simulation_graph']['connections'][0]['sides']=['사무실','복도']
        with self.temp() as directory:
            path=Path(directory)/'building.json';path.write_text(json.dumps(raw),encoding='utf-8')
            model=normalize(adapt(path))
        self.assertEqual(model['cad']['display_rooms'][0]['cad_room'],'사무실')
        self.assertTrue(all(r['id'].isascii() for r in model['rooms']))

    def test_ambiguous_building_requires_explicit_choice(self):
        with self.temp() as directory:
            root=Path(directory)
            for job in ('a','b'):
                path=root/f'work/cad-ui-test-data/{job}/cad-output';path.mkdir(parents=True)
                (path/'building.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'여러 개'):resolve_building(root)
            self.assertEqual(resolve_building(root,path/'building.json'),path/'building.json')

    def test_profile_preserves_explicit_settings_and_caps_cost(self):
        raw={'gas':{'gas_ignition_C':480},'spread':{'max_runs':50,'wall_time_budget_s':5000}}
        model=apply_profile(raw)
        self.assertEqual(model['gas']['gas_ignition_C'],480)
        self.assertEqual(model['spread']['max_runs'],3)
        self.assertEqual(model['spread']['wall_time_budget_s'],1800)
        self.assertNotIn('execution_profile',raw)

    def test_full_floor_cannot_bypass_budget_but_keeps_all_fuel_candidates(self):
        raw=json.loads((ROOT/'examples/three_rooms.json').read_text())
        raw['spread']={'full_floor_search':True,'max_runs':96,'max_passes':48,
                       'max_added_ignitions':80,'run_timeout_s':1200,'wall_time_budget_s':7200}
        raw['execution_profile']='practical'
        model=normalize(raw)
        self.assertEqual(model['spread']['max_runs'],3)
        self.assertEqual(model['spread']['max_passes'],3)
        self.assertEqual(model['spread']['max_added_ignitions'],80)
        self.assertEqual(model['spread']['run_timeout_s'],600)
        self.assertFalse(model['spread']['automatic_retry'])
        self.assertEqual(model['gas'],normalize({**raw,'execution_profile':'legacy'})['gas'])

    def test_hour_budget_defaults_and_explicit_shorter_limits(self):
        half=apply_profile({'duration_s':1800})
        hour=apply_profile({'duration_s':3600})
        for key in ('run_timeout_s','wall_time_budget_s'):
            self.assertEqual(hour['spread'][key],2*half['spread'][key])
        self.assertEqual(hour['spread']['max_runs'],3)
        self.assertEqual(hour['spread']['max_passes'],3)
        self.assertEqual(hour['spread']['stall_timeout_s'],90)
        self.assertFalse(hour['spread']['automatic_retry'])
        shorter=apply_profile({'duration_s':3600,'spread':{'run_timeout_s':100,'wall_time_budget_s':200}})
        self.assertEqual(shorter['spread']['run_timeout_s'],100)
        self.assertEqual(shorter['spread']['wall_time_budget_s'],200)

    def test_cad_hour_budget_reaches_native_settings(self):
        with self.temp() as directory:
            path=Path(directory)/'building.json'
            path.write_text(json.dumps(building_fixture()))
            for duration,timeout,budget in ((1800,600,1800),(3600,1200,3600)):
                model=normalize(adapt(path,{'duration_s':duration}))
                self.assertEqual(model['spread']['run_timeout_s'],timeout)
                self.assertEqual(model['spread']['wall_time_budget_s'],budget)

    def test_hour_normalization_caps_and_preserves_physics(self):
        raw=json.loads((ROOT/'examples/three_rooms.json').read_text())
        raw.update(duration_s=3600,execution_profile='practical')
        raw['spread']={'max_runs':99,'max_passes':99,'run_timeout_s':9000,'wall_time_budget_s':9000}
        model=normalize(raw)
        self.assertEqual(model['spread']['run_timeout_s'],1200)
        self.assertEqual(model['spread']['wall_time_budget_s'],3600)
        self.assertEqual(model['spread']['max_runs'],3)
        self.assertEqual(model['spread']['max_passes'],3)
        legacy=normalize({**raw,'execution_profile':'legacy'})
        for key in ('gas','flashover','fuel_groups'):
            self.assertEqual(model[key],legacy[key])

    def test_sparse_radiation_points_stay_in_polygon_and_one_keeps_origin(self):
        room={'origin_m':[0,0,0],'size_m':[4,4,3],
              'cad_polys':[{'o':[[0,0],[4,0],[4,4],[0,4]],'h':[[[0,0],[2,0],[2,2],[0,2]]]}]}
        np.testing.assert_equal(emission_points(room,[3,3,.2],1),[[3,3,.2]])
        points=emission_points(room,[3,3,.2],4)
        self.assertEqual(len(points),3)

    def test_fuel_area_pool_preserves_fuel_energy(self):
        raw=json.loads((ROOT/'examples/three_rooms.json').read_text())
        model=normalize(apply_profile(raw))
        curves,pools=source_curves(model,[],[{'room':'R1','t_ign_s':20.}])
        self.assertAlmostEqual(pools['R1']['area_m2'],16*.31)
        self.assertAlmostEqual(sum(float(integral(c['t'],c['q'],1e9)) for c in curves.values()),400000.)

    def test_negative_candidate_isolated_and_not_sent_to_plate(self):
        model=normalize(json.loads((ROOT/'examples/three_rooms.json').read_text()))
        target={'id':'C1','room':'R2','group':'reserve_R2','material':model['material']}
        native={'zone':{'Time':np.array([0.,5.])},'devices':{
            'TRGFLXI_1':np.zeros(2),'B_TRGFLXI_1':np.zeros(2),'TRGGAST_1':np.zeros(2)}}
        with patch('pyrocast_cfbt.spread.room_series',return_value={}), \
             patch('pyrocast_cfbt.spread.supplementary',return_value=({'aperture':np.array([-1.,-2.])},np.zeros(2))), \
             patch('pyrocast_cfbt.spread.plate') as plate:
            decisions,views,_=assess(model,native,[target],[])
        self.assertEqual(decisions,[]);self.assertEqual(views[0]['status'],'invalid_exposure')
        plate.assert_not_called()

    def test_initial_solver_failure_stops_without_retry_or_time_step_change(self):
        from pyrocast_cfbt.spread import simulate
        model=apply_profile(json.loads((ROOT/'examples/three_rooms.json').read_text()))
        model['spread']['max_runs']=2;model['flashover']['enabled']=False
        with self.temp() as folder, patch('pyrocast_cfbt.spread.execute',side_effect=RuntimeError('solver failed')) as engine:
            with self.assertRaisesRegex(RuntimeError,'solver failed'):simulate(model,'unused.exe',folder)
            summary=json.loads((Path(folder)/'summary.json').read_text('utf-8'))
        self.assertEqual(engine.call_count,1)
        self.assertFalse(summary['simulation_complete_to_requested_horizon'])
        self.assertEqual(summary['terminated'],'solver_failed')
        self.assertEqual(summary['attempts'][0]['max_time_step_s'],model['max_time_step_s'])


if __name__=='__main__':unittest.main()
