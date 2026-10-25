"""Regressions for native window identity, causal histories and execution failures."""
from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import Mock, patch
import numpy as np
from pyrocast_cfbt.model import normalize
from pyrocast_cfbt.deck import make_deck, candidates
from pyrocast_cfbt.openings import window_targets, policy, histories, realized_fraction, device_series
from pyrocast_cfbt.spread import check_causality
from pyrocast_cfbt.native import execute
from pyrocast_cfbt.cad import adapt

ROOT=Path(__file__).resolve().parents[1]


def fixture():
    raw=json.loads((ROOT/'examples/three_rooms.json').read_text())
    raw.update(window_breakage={'enabled':True},output_step_s=5)
    raw['openings'].append({'id':'Window','a':'R1','b':'OUTSIDE','kind':'window',
        'face':'REAR','offset_m':1.,'width_m':2.,'bottom_m':1.,'top_m':2.8,'schedule':[[0,0.5]]})
    return normalize(raw)


class WindowTests(unittest.TestCase):
    def test_api_cache_tracks_policy_building_engine_and_duration(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('window_server_test',ROOT.parent/'tools/serve_cfbt_building.py')
        server=importlib.util.module_from_spec(spec);spec.loader.exec_module(server)
        engine=Path(__file__);options={'duration_s':1800,'window_breakage':{'enabled':True,'threshold':450.}}
        a=server.execution_key(options,'building',engine)
        self.assertEqual(a,server.execution_key(deepcopy(options),'building',engine))
        for patch_value in ({'duration_s':3600},{'window_breakage':{'enabled':True,'threshold':451.}}):
            self.assertNotEqual(a,server.execution_key({**options,**patch_value},'building',engine))
        self.assertNotEqual(a,server.execution_key(options,'other-building',engine))
        self.assertNotEqual(a,server.execution_key(options,'building',ROOT/'pyrocast_cfbt/native.py'))
        for duration in (1800,3600):
            self.assertEqual(server.checked_options({'duration_s':duration})['duration_s'],duration)
        with self.assertRaises(ValueError):server.checked_options({'window_breakage':{'enabled':True,'threshold':float('nan')}})

    def test_target_appended_and_exterior_rear_exact_boundary(self):
        model=fixture();targets=candidates(model);window=window_targets(model)[0]
        self.assertEqual(window['local_xyz'],[2.,4.,1.9])
        self.assertEqual(window['normal'],[0.,-1.,0.])
        self.assertLessEqual(len(window['material_id']),16)
        deck=make_deck(model,[],targets)
        self.assertGreater(deck.index("&DEVC ID='"+window['id']),deck.index("&DEVC ID='"+targets[-1]['id']))
        self.assertIn('PRE_FRACTION=0.5 POST_FRACTION=1',deck)
        self.assertIn('LOCATION=2,4,1.9 NORMAL=0,-1,0',deck)
        self.assertEqual(len(targets),len(candidates({**model,'window_breakage':{'enabled':False}})))

    def test_no_effect_window_uses_time_without_extra_target(self):
        model=fixture();model['window_breakage']['post_fraction']=.5
        self.assertEqual(window_targets(model),[])
        line=next(l for l in make_deck(model,[],[]).splitlines() if "ID='Window'" in l)
        self.assertIn("CRITERION='TIME'",line)

    def test_disabled_feature_leaves_deck_unchanged(self):
        raw=json.loads((ROOT/'examples/three_rooms.json').read_text())
        a=normalize(raw);b=normalize({**raw,'window_breakage':{'enabled':False,'threshold':900.}})
        self.assertEqual(make_deck(a,[],candidates(a)),make_deck(b,[],candidates(b)))

    def test_native_ids_override_device_position(self):
        result={'devices':{'TRGGAST_1':np.array([99]),'TRGGAST_4':np.array([20])},
                'devices_ids':{'TRGGAST_1':'WIN_123','TRGGAST_4':'fuel'}}
        np.testing.assert_array_equal(device_series(result,'fuel','TRGGAST',1),[20])
        with self.assertRaises(ValueError):device_series(result,'missing','TRGGAST',1)

    def test_fraction_previous_hold_and_id_mapping(self):
        native={'zone':{'Time':np.array([0,5,10])},'native_vents':{'Time':np.array([0,5,10]),'WF_99':np.array([.5,.75,1])},'native_vents_ids':{'WF_99':'Window'}}
        np.testing.assert_array_equal(realized_fraction(native,{'id':'Window'},[0,4.99,5,9,10]),[.5,.5,.75,.75,1])

    def test_observed_interval_not_an_exact_failure_time(self):
        m=fixture();target=window_targets(m)[0]
        native={'zone':{'Time':np.array([0,5,10])},'native_vents':{'Time':np.array([0,5,10]),'WF_1':np.array([.5,.5,1.])},'native_vents_ids':{'WF_1':'Window'},
                'devices':{'TRGSURT_8':np.array([20,440,500])},'devices_ids':{'TRGSURT_8':target['id']}}
        self.assertEqual(histories(m,native)['Window']['observed_interval_s'],[5.,10.])
        del native['native_vents_ids']
        with self.assertRaises(ValueError):histories(m,native)

    def test_invalid_policies_fail_before_engine(self):
        for change in ({'post_fraction':.4},{'threshold':float('nan')},{'material':{'thickness_m':0}}, {'criterion':'BOGUS'}):
            m=fixture();m['window_breakage'].update(change)
            with self.assertRaises(ValueError):window_targets(m)
        m=fixture();m['openings'][-1]['schedule'].append([100,1])
        with self.assertRaises(ValueError):window_targets(m)

    def test_internal_glass_is_unevaluated_not_a_false_external_boundary(self):
        m=fixture();v=m['openings'][-1];v['b']='R2'
        self.assertEqual(window_targets(m),[])
        v['window_breakage']={'enabled':True}
        with self.assertRaises(ValueError):window_targets(m)

    def test_changed_policy_changes_native_deck(self):
        m=fixture();a=make_deck(m,[],[])
        m['window_breakage']['threshold']=451
        self.assertNotEqual(a,make_deck(m,[],[]))

    def test_causal_window_change_cannot_be_committed_early(self):
        m=fixture();native={'zone':{'Time':np.array([0.,5.,10.])},'rooms':[],
            'native_vents':{'Time':np.array([0.,5.,10.]),'WF_1':np.array([.5,.5,1.])},'native_vents_ids':{'WF_1':'Window'}}
        updated=deepcopy(native);updated['native_vents']['WF_1'][1]=1
        with self.assertRaisesRegex(ValueError,'causal mismatch'):
            check_causality(native,updated,{'t_ign_s':9},m['spread'])

    def test_watchdog_kills_only_owned_process_and_does_not_commit(self):
        tmpbase=ROOT/'results/unit_tmp';tmpbase.mkdir(parents=True,exist_ok=True)
        process=Mock();process.poll.return_value=None
        with tempfile.TemporaryDirectory(dir=tmpbase) as d, patch('pyrocast_cfbt.native.subprocess.Popen',return_value=process):
            with self.assertRaisesRegex(TimeoutError,'wall_time_budget'):
                execute(Path(__file__),d,'&HEAD /','',1800,0)
            process.kill.assert_called_once();process.wait.assert_called_once()
            self.assertFalse((Path(d)/'completed.json').exists())
            self.assertEqual(json.loads((Path(d)/'execution-state.json').read_text())['status'],'incomplete')

    def test_selected_floor_keeps_closed_door_rooms_and_auto_event_capacity(self):
        from test_practical import building_fixture
        raw=building_fixture();tmpbase=ROOT/'results/unit_tmp';tmpbase.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=tmpbase) as d:
            path=Path(d)/'building.json';path.write_text(json.dumps(raw))
            m=normalize(adapt(path,{'scope_floor':'GF','door_fraction':0.}))
        self.assertEqual(len(m['rooms']),2)
        self.assertEqual(m['spread']['max_added_ignitions'],1)
        self.assertEqual(m['spread']['max_runs'],3)
        self.assertEqual(m['spread']['iteration_mode'],'fixed_point')


if __name__=='__main__':unittest.main()
