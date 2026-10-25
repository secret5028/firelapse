from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import tempfile
import numpy as np

from pyrocast_cfbt.model import normalize
from pyrocast_cfbt.flashover import integral, source_curves, proposals
from pyrocast_cfbt.spread import simulate


class FlashoverTests(unittest.TestCase):
    def setUp(self):
        self.model=normalize(json.loads((Path(__file__).resolve().parents[1]/'examples/three_rooms.json').read_text()))
        self.model['flashover']['enabled']=True
        self.events=[{'kind':'fo_transition','room':'R1','t_ign_s':20.}]

    def test_room_pool_preserves_energy_prefix_area_and_single_late_source(self):
        # Different pre-FO area/HRR laws must not change before the switch.
        ignition={'group':'reserve_R1','t_ign_s':5.}
        base,_=source_curves(self.model,[ignition],[])
        curves,pools=source_curves(self.model,[ignition],self.events)
        for key in ('primary','reserve_R1'):
            old=base[key]; new=curves[key]
            samples=np.linspace(old['start_s'],20.,91)
            np.testing.assert_allclose(np.interp(samples,new['t'],new['q']),np.interp(samples,old['t'],old['q']),atol=1e-10)
            np.testing.assert_allclose(np.interp(samples,new['t'],new['area']),np.interp(samples,old['t'],old['area']),atol=1e-10)
            self.assertTrue(np.all(np.diff(new['t'])>0))
        energy=sum(float(integral(c['t'],c['q'],c['t'][-1])) for c in curves.values())
        self.assertAlmostEqual(energy,400000.,places=6)
        end=pools['R1']['ramp_end_s']
        self.assertEqual(np.interp(end+1,curves['reserve_R1']['t'],curves['reserve_R1']['q']),0.)
        self.assertGreater(np.interp(end+1,curves['primary']['t'],curves['primary']['q']),0.)

    def test_unignited_room_reserve_is_pooled_once_without_new_fire(self):
        curves,pools=source_curves(self.model,[],self.events)
        self.assertEqual(list(curves),['primary'])
        self.assertAlmostEqual(float(integral(curves['primary']['t'],curves['primary']['q'],1e9)),400000.,places=6)
        self.assertIn('reserve_R1',pools['R1']['remaining_by_group_kJ'])

    def test_room_supply_cap_preserves_budget_and_does_not_cut_existing_supply(self):
        base,_=source_curves(self.model,[],[])
        present=float(np.interp(20.,base['primary']['t'],base['primary']['q']))
        for cap in (present/2,present*2):
            m=deepcopy(self.model)
            m['flashover']['max_supply_kW']=1e6
            m['flashover']['max_supply_by_room_kW']={'R1':cap}
            curves,pools=source_curves(m,[],self.events)
            self.assertAlmostEqual(pools['R1']['target_supply_kW'],max(present,cap))
            c=curves['primary']
            self.assertAlmostEqual(float(integral(c['t'],c['q'],1e9)),400000.,places=6)

    def test_very_small_remaining_budget_shortens_ramp_and_never_creates_energy(self):
        for at in (1.,30.,80.):
            m=deepcopy(self.model)
            m['flashover']['transition_s']=1e5
            curves,_=source_curves(m,[],[{'room':'R1','t_ign_s':at}])
            c=curves['primary']
            self.assertAlmostEqual(float(integral(c['t'],c['q'],1e9)),400000.,places=6)
            self.assertTrue(np.all(np.diff(c['t'])>0))
            self.assertTrue(np.all(c['q']>=0))

    def test_temperature_constant_and_latch_apply_to_initial_fire(self):
        t=np.array([0.,10.,20.,30.]); result={'zone':{'Time':t}}
        states={'R1':{'T_upper_C':np.array([20.,500.,700.,400.])}}
        proposed=proposals(self.model,result,states,[],[],[])
        self.assertEqual(len(proposed),1)
        self.assertEqual(proposed[0]['t_ign_s'],15.)
        self.assertEqual(proposals(self.model,result,states,[],proposed,[]),[])
        states['R1']['T_upper_C']=np.array([20.,400.,471.4,450.])
        self.assertEqual(proposals(self.model,result,states,[],[],[]),[])

    def test_missing_floor_flux_does_not_trigger_and_chemistry_mismatch_rejected(self):
        m=deepcopy(self.model);m['flashover']['criterion']='temperature_or_flux'
        self.assertEqual(proposals(m,{'zone':{'Time':np.array([0.,10.])}},
                                  {'R1':{'T_upper_C':np.array([20.,400.])}},[],[],[]),[])
        m['fuel_groups'][1]['heat_of_combustion_kJ_kg']*=2
        with self.assertRaisesRegex(ValueError,'identical effective fuel'):
            normalize(m)

    def test_failed_fo_run_keeps_previous_state_and_uncommitted_transition(self):
        from contextlib import ExitStack
        self.model['spread'].update(enabled=False,max_added_ignitions=0)
        event={**self.events[0],'event_id':'FO_R1','t_ign_s':1.}
        fake={'run':{'input_sha256':'valid','folder':'unused'},
              'zone':{'Time':np.arange(3.),**{f'DJET_{i}':np.zeros(3) for i in range(1,4)}},
              'rooms':[],'vents':[],'slabs':[]}
        root=Path(__file__).resolve().parents[1]
        temp_root=root/'results/unit_tmp';temp_root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_root) as folder, ExitStack() as stack:
            self.assertTrue(Path(folder).resolve().is_relative_to(root.resolve()))
            engine=stack.enter_context(patch('pyrocast_cfbt.spread.execute',side_effect=[fake,RuntimeError('solver failed')]))
            stack.enter_context(patch('pyrocast_cfbt.spread.assess',return_value=([],[],{})))
            stack.enter_context(patch('pyrocast_cfbt.spread.fo_proposals',return_value=[event]))
            stack.enter_context(patch('pyrocast_cfbt.spread.classify',return_value={}))
            stack.enter_context(patch('pyrocast_cfbt.spread.neutral_planes',return_value={}))
            stack.enter_context(patch('pyrocast_cfbt.spread.solid_inventory',return_value={}))
            stack.enter_context(patch('pyrocast_cfbt.spread.digest',return_value='engine'))
            d=simulate(self.model,'unused.exe',folder)
        self.assertEqual(engine.call_count,2)
        self.assertEqual(d['fo_transitions'],[])
        self.assertEqual(d['pending_candidates'],[event])
        self.assertEqual(d['final_input_sha256'],'valid')
        self.assertEqual(d['terminated'],'solver_failed')


if __name__=='__main__':unittest.main()
