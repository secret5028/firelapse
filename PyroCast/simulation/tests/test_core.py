from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
from contextlib import contextmanager
import numpy as np

from pyrocast_cfbt.model import normalize
from pyrocast_cfbt.deck import candidates, fire_curve, gas_sidecar
from pyrocast_cfbt.thermal import plate, SIGMA
from pyrocast_cfbt.exposure import _aperture
from pyrocast_cfbt.spread import check_causality, simulate

ROOT=Path(__file__).resolve().parents[1]


@contextmanager
def local_temp():
    base=ROOT/'results'/'unit_tmp'
    base.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=base) as folder:
        if not Path(folder).resolve().is_relative_to(ROOT.resolve()):
            raise ValueError('Test cleanup target escaped the simulation workspace')
        yield folder


class ConservationTests(unittest.TestCase):
    def setUp(self):
        self.model=normalize(json.loads((ROOT/'examples/three_rooms.json').read_text()))

    def test_design_curve_includes_decay_and_exact_budget(self):
        for fuel in self.model['fuel_groups']:
            for energy in (.001,1,100,300):
                t,q,area=fire_curve({**fuel,'energy_MJ':energy},16)
                self.assertAlmostEqual(float(np.trapezoid(q,t)),energy*1000,places=7)
                self.assertLessEqual(max(q),fuel['peak_kW'])
                self.assertLessEqual(max(area),16)
                self.assertEqual(q[-1],0)
                self.assertTrue(np.all(np.diff(t)>0))

    def test_future_opening_candidates_predeclared(self):
        self.model['openings'][0]['schedule']=[[0,0],[60,0],[60.1,1]]
        points=candidates(self.model)
        self.assertTrue(any(p['label'].startswith('D12') and p['room']=='R2' for p in points))

    def test_vol_percent_is_not_passed_as_mass_fraction(self):
        sidecar=gas_sidecar(self.model)
        self.assertIn('oxygen_min_vol=0.12',sidecar)
        self.assertNotIn('lower_oxygen_limit',sidecar)

    def test_radiation_cache_is_opt_in_and_separate_from_combustion(self):
        self.assertNotIn('radiation_cache_enabled',gas_sidecar(self.model))
        self.model['engine_optimization']['radiation_cache']=True
        side=gas_sidecar(normalize(self.model))
        self.assertIn('radiation_cache_enabled=.TRUE.',side)
        self.model['engine_optimization']['radiation_cache']='yes'
        with self.assertRaisesRegex(ValueError,'boolean'):normalize(self.model)

    def test_plate_isothermal_equilibrium(self):
        material={**self.model['material'],'absorptivity':.9,'emissivity':.9}
        t=np.arange(0,11,dtype=float); q=np.full(len(t),SIGMA*293.15**4/1000); gas=np.full(len(t),20.)
        result=plate(material,t,q,q,gas,gas)
        np.testing.assert_allclose(result['surface_C'],20,atol=1e-9)
        self.assertIsNone(result['crossing_s'])

    def test_aperture_isothermal_cancels_and_shifted_floor(self):
        state={'interface':np.array([11.]),'T':[np.array([400.]),np.array([400.])],
               'k':[np.array([.2]),np.array([1.])], 'walls':[np.array([400.])]*4}
        result=_aperture(np.array([0,.5,11.]),np.array([0,-1,0]),.5,10.,12.,
                         [(-1,1),(-3,0),(10,12)],state,state,12,ambient_K=400.)
        np.testing.assert_allclose(result,0,atol=1e-10)

    def test_causality_detects_past_temperature_change(self):
        previous={'zone':{'Time':np.arange(5.),'ULT_1':np.full(5,20.)},'rooms':[]}
        altered=deepcopy(previous); altered['zone']['ULT_1'][1]=22
        with self.assertRaisesRegex(ValueError,'causal mismatch'):
            check_causality(previous,altered,{'t_ign_s':3},self.model['spread'])

    def _fake_run(self,signature):
        return {'run':{'input_sha256':signature,'folder':'unused'},
                'zone':{'Time':np.arange(3.),'ULT_1':np.full(3,20.),
                        **{f'DJET_{i}':np.zeros(3) for i in range(1,4)}},
                'rooms':[],'vents':[],'slabs':[]}

    def _event(self,group,time):
        return {'event_id':group,'group':group,'room':'R2','candidate':'C_1',
                't_ign_s':time,'xyz':[5.,2.,0.]}

    def test_prescribed_smoke_reuses_events_without_spread_search(self):
        model=deepcopy(self.model)
        event=self._event('reserve_R2',1.)
        model.update(prescribed_smoke=True,prescribed_fire_events=[event],
                     prescribed_fo_transitions=[],explicit_candidates=[])
        model['spread'].update(enabled=False,max_runs=1)
        with local_temp() as folder, \
             patch('pyrocast_cfbt.spread.execute',return_value=self._fake_run('prescribed')) as engine, \
             patch('pyrocast_cfbt.spread.assess') as assess, \
             patch('pyrocast_cfbt.spread.fo_proposals') as fo, \
             patch('pyrocast_cfbt.spread.room_series',return_value={}), \
             patch('pyrocast_cfbt.spread.classify',return_value={}), \
             patch('pyrocast_cfbt.spread.neutral_planes',return_value={}), \
             patch('pyrocast_cfbt.spread.solid_inventory',return_value={}), \
             patch('pyrocast_cfbt.spread.digest',return_value='engine'):
            result=simulate(model,'unused.exe',folder)
        self.assertEqual(engine.call_count,1)
        assess.assert_not_called()
        fo.assert_not_called()
        self.assertEqual(result['ignitions'],[event])
        self.assertEqual(result['attempts'][0]['proposed_groups'],['reserve_R2'])
        self.assertEqual(result['terminated'],'prescribed_smoke')
        self.assertFalse(result['spread_search_complete'])
        self.assertFalse(result['fo_transition_search_complete'])
        self.assertIn('not_repredicted',result['fire_event_evaluation'])

    def test_limit_never_commits_an_unexecuted_last_fire(self):
        model=deepcopy(self.model); model['spread'].update(max_runs=2,max_added_ignitions=1)
        first=self._event('reserve_R2',1.); pending=self._event('reserve_R3',2.)
        with local_temp() as folder, \
             patch('pyrocast_cfbt.spread.execute',side_effect=[self._fake_run('a'),self._fake_run('b')]) as engine, \
             patch('pyrocast_cfbt.spread.assess',side_effect=[([first],[],{}),([pending],[],{})]), \
             patch('pyrocast_cfbt.spread.classify',return_value={}), \
             patch('pyrocast_cfbt.spread.neutral_planes',return_value={}), \
             patch('pyrocast_cfbt.spread.solid_inventory',return_value={}), \
             patch('pyrocast_cfbt.spread.digest',return_value='engine'):
            result=simulate(model,'unused.exe',folder)
        self.assertEqual(engine.call_count,2)
        self.assertEqual(result['final_input_sha256'],'b')
        self.assertEqual(result['ignitions'],[first])
        self.assertEqual(result['pending_candidates'],[pending])
        self.assertFalse(result['spread_search_complete'])

    def test_failed_next_run_keeps_last_valid_state(self):
        first=self._event('reserve_R2',1.)
        with local_temp() as folder, \
             patch('pyrocast_cfbt.spread.execute',side_effect=[self._fake_run('a'),RuntimeError('engine failed')]), \
             patch('pyrocast_cfbt.spread.assess',return_value=([first],[],{})), \
             patch('pyrocast_cfbt.spread.classify',return_value={}), \
             patch('pyrocast_cfbt.spread.neutral_planes',return_value={}), \
             patch('pyrocast_cfbt.spread.solid_inventory',return_value={}), \
             patch('pyrocast_cfbt.spread.digest',return_value='engine'):
            result=simulate(self.model,'unused.exe',folder)
        self.assertEqual(result['final_input_sha256'],'a')
        self.assertEqual(result['ignitions'],[])
        self.assertEqual(result['pending_candidates'],[first])
        self.assertEqual(result['terminated'],'solver_failed')


if __name__=='__main__':unittest.main()
