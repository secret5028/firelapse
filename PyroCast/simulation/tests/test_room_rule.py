from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from pyrocast_cfbt.model import normalize
from pyrocast_cfbt.deck import make_deck,candidates,gas_sidecar,active_fuels,fire_curve
from pyrocast_cfbt.room_rule import prepare,supply_curve,settings,observe,ventilation_cap

EXAMPLE=Path(__file__).resolve().parents[1]/'examples/three_rooms.json'

class RoomRuleTests(unittest.TestCase):
    def raw(self):
        raw=json.loads(EXAMPLE.read_text('utf-8'));raw['room_fire_rule']={'enabled':True,'trigger_mode':'floor_r2'}
        return raw

    def test_budget_even_when_energy_cannot_reach_requested_peak(self):
        for energy in (.0001,10,10000):
            group={'energy_MJ':energy,'peak_kW':5000,'hrrpua_kW_m2':500,'fuel_area_m2':10}
            curve=supply_curve(group,16,settings({}))
            self.assertAlmostEqual(np.trapezoid(curve['q'],curve['t']),energy*1000,places=6)
            self.assertTrue(np.all(np.diff(curve['t'])>0))
            self.assertLessEqual(max(curve['q']),5000)

    def test_stable_standby_order_and_no_extra_reaction(self):
        raw=self.raw();before=deepcopy(raw);model,targets=prepare(raw)
        self.assertEqual(raw,before)
        self.assertEqual([g['room'] for g in model['fuel_groups']],['R1','R2','R3'])
        self.assertEqual(active_fuels(model,[]),active_fuels(model,[{'group':'reserve_R3'}]))
        self.assertFalse(model['gas']['enabled']);self.assertFalse(model['gas']['mixture_enabled'])
        self.assertFalse(model['flashover']['enabled']);self.assertFalse(model['engine_optimization']['adaptive_radiation'])
        deck=make_deck(model,[],targets)
        self.assertEqual(deck.count('&FIRE '),3);self.assertEqual(deck.count("IGNITION_CRITERION='FLUX'"),2)
        self.assertIn('SETPOINT=15',deck)
        old=normalize(before)
        self.assertEqual(fire_curve(old['fuel_groups'][0],16),fire_curve(model['fuel_groups'][0],16))

    def test_off_bytes_unchanged(self):
        raw=self.raw();raw.pop('room_fire_rule');old=normalize(raw)
        raw['room_fire_rule']={'enabled':False};off=normalize(raw)
        self.assertEqual(make_deck(old,[],candidates(old)),make_deck(off,[],candidates(off)))
        self.assertEqual(gas_sidecar(old),gas_sidecar(off))

    def test_pool_only_compatible_chemistry(self):
        raw=self.raw();extra=deepcopy(raw['fuel_groups'][2]);extra['id']='extra';raw['fuel_groups'].append(extra)
        model,_=prepare(raw)
        self.assertEqual(model['fuel_groups'][1]['energy_MJ'],200)
        raw['fuel_groups'][-1]['heat_of_combustion_kJ_kg']=19000
        with self.assertRaisesRegex(ValueError,'identical chemistry'):prepare(raw)

    def test_invalid_settings(self):
        for change in ({'criterion':'GAS_OR_FLUX'},{'ramp_s':0},{'setpoint':float('nan')},{'decay_energy_fraction':1},{'preset':'fake'}):
            with self.assertRaises(ValueError):settings({'room_fire_rule':change})
        raw=self.raw();raw['room_fire_rule']['sensor_height_m']=3
        with self.assertRaisesRegex(ValueError,'strictly inside'):prepare(raw)

    def test_id_mapped_native_flux_units_and_unignited_source(self):
        model,targets=prepare(self.raw());t=np.array([0.,5.,10.]);ids={'TRGFLXI_99':targets[0]['id'],'TRGSURT_99':targets[0]['id'],
            'TRGFLXI_2':targets[1]['id'],'TRGSURT_2':targets[1]['id']}
        with tempfile.TemporaryDirectory(dir=EXAMPLE.parents[1]/'build/unit_tmp') as name:
            (Path(name)/'case.log').write_text('Object #2 (F_reserve_R2) ignited at 7 seconds')
            result={'run':{'folder':name},'zone':{'Time':t,'HRR_2':np.array([0,0,2000]),'HRR_3':np.zeros(3)},
                'devices':{'TRGFLXI_99':np.array([0,14,18]),'TRGSURT_99':np.array([20,100,200]),
                           'TRGFLXI_2':np.zeros(3),'TRGSURT_2':np.ones(3)*20},'devices_ids':ids,
                'compartments':{'IGN_2':np.array([0,0,1]),'IGN_3':np.zeros(3)}}
            events,views,records=observe(model,result,targets)
            self.assertEqual(events[0]['t_ign_s'],7)
            self.assertEqual(events[0]['time_interval_s'],[6.5,7.5])
            self.assertEqual(records[0]['sensor_max'],18)
            self.assertIsNone(records[1]['ignition_s'])
            np.testing.assert_equal(views[0]['q_inc_kW_m2'],[0,14,18])

    def test_dispatch_bypasses_external_iteration(self):
        from pyrocast_cfbt.spread import simulate
        with patch('pyrocast_cfbt.room_rule.simulate_room_rule',return_value='single') as native:
            self.assertEqual(simulate(self.raw(),'engine','out'),'single');native.assert_called_once()

    def test_r3_reuses_fuel_target_and_keeps_floor_display_passive(self):
        raw=self.raw();raw['room_fire_rule']['trigger_mode']='fuel_r3'
        before=candidates(normalize(raw));model,targets=prepare(raw)
        original=next(v for v in before if v['group']=='reserve_R2')
        selected=next(v for v in targets if v['group']=='reserve_R2' and v['used_for_ignition'])
        for key in ('xyz','normal','material'):self.assertEqual(selected[key],original[key])
        self.assertEqual(model['fuel_groups'][1]['room_rule_trigger']['setpoint'],369.)
        deck=make_deck(model,[],targets)
        self.assertEqual(deck.count("IGNITION_CRITERION='TEMPERATURE'"),2)
        self.assertNotIn("DEVC_ID='RF_FLOOR_",deck)
        self.assertEqual(sum(not v['used_for_ignition'] for v in targets),2)

    def test_new_requests_default_r3_and_saved_r2_stays_r2(self):
        self.assertEqual(settings({'room_fire_rule':{'enabled':True}})['trigger_mode'],'fuel_r3')
        self.assertEqual(settings({'room_fire_rule':{'prepared':True,'setpoint':15}})['trigger_mode'],'floor_r2')

    def test_r3_presets_are_explicit_assumptions(self):
        raw=self.raw();raw['room_fire_rule'].update(trigger_mode='fuel_r3',preset='aggressive')
        model,_=prepare(raw)
        self.assertAlmostEqual(model['fuel_groups'][1]['room_rule_trigger']['setpoint'],369*.8)
        self.assertEqual(model['room_fire_rule']['ramp_s'],30)
        raw['room_fire_rule']['setpoint']=15
        with self.assertRaisesRegex(ValueError,'per-material'):prepare(raw)

    def test_cap_one_opening_not_sum_and_ineffective_in_fixture(self):
        model=normalize(self.raw());cap=ventilation_cap(model,'R2')
        self.assertAlmostEqual(cap['cap_kW'],1.5*1500*2.1*np.sqrt(2.1))
        self.assertGreater(cap['cap_kW'],5000)

    def test_closed_window_uses_post_breakage_fraction(self):
        model=normalize(self.raw());model['openings']=[{'id':'W','a':'R2','b':'OUTSIDE','kind':'window',
            'width_m':1.,'bottom_m':.5,'top_m':2.,'schedule':[[0,0]],'window_breakage':{'enabled':True,'post_fraction':.8}}]
        cap=ventilation_cap(model,'R2');self.assertEqual(cap['opening']['fraction'],.8)
        self.assertAlmostEqual(cap['cap_kW'],2250*1.5*.8*np.sqrt(1.5))

    def test_zero_cap_does_not_release_energy_or_divide_by_zero(self):
        raw=self.raw();raw['openings']=[];raw['room_fire_rule']['vent_cap_enabled']=True
        model,_=prepare(raw);curve=model['fuel_groups'][1]['room_rule_curve']
        self.assertEqual(curve['Q_max_kW'],0);self.assertEqual(np.trapezoid(curve['q'],curve['t']),0)

    def test_explicit_candidate_id_validation(self):
        raw=self.raw();raw['room_fire_rule'].update(trigger_mode='fuel_r3',candidate_ids={'R2':'missing'})
        with self.assertRaisesRegex(ValueError,'No existing'):prepare(raw)

    def test_saved_r3_scenario_reuses_identical_deck_and_original_candidate_id(self):
        raw=self.raw();candidate=next(v['id'] for v in candidates(normalize(raw)) if v['room']=='R2')
        raw['room_fire_rule'].update(trigger_mode='fuel_r3',candidate_ids={'R2':candidate})
        first,targets=prepare(raw);second,reloaded=prepare(first)
        self.assertEqual(make_deck(first,[],targets),make_deck(second,[],reloaded))
        self.assertEqual(second['fuel_groups'][1]['source_candidate_id'],candidate)

    def test_r4_external_cap_preferred_over_bigger_internal_and_initial_not_capped(self):
        raw=self.raw();raw['room_fire_rule']['trigger_mode']='fuel_r4'
        raw['openings'].append({'id':'W2','a':'R2','b':'OUTSIDE','face':'FRONT','width_m':1.8,'bottom_m':.9,'top_m':2.1})
        model,targets=prepare(raw);g=model['fuel_groups'][1]
        self.assertEqual(g['room_vent_cap']['opening']['opening_id'],'W2')
        self.assertAlmostEqual(g['room_vent_cap']['cap_kW'],1500*2.16*np.sqrt(1.2))
        self.assertNotIn('room_rule_curve',model['fuel_groups'][0])
        self.assertEqual(g['position_m'][2],0)
        self.assertGreater(next(t for t in targets if t['id']=='RF_R2')['xyz'][2],0)
        cap=ventilation_cap(normalize(self.raw()),'R2',1,True)
        self.assertEqual(cap['internal_discount'],.5)

    def test_r4_ceiling_plate_and_source_are_independent_and_reload_stable(self):
        raw=self.raw();raw['room_fire_rule']['trigger_mode']='ceiling_r4'
        model,targets=prepare(raw);g=model['fuel_groups'][1];t=targets[0]
        self.assertEqual(g['position_m'][2],0)
        self.assertEqual(t['xyz'][2],2.8);self.assertEqual(t['normal'],[0,0,-1])
        self.assertEqual(t['material']['thickness_m'],.001)
        self.assertEqual(g['room_rule_trigger']['setpoint'],500)
        again,ts=prepare(model)
        self.assertEqual(make_deck(model,[],targets),make_deck(again,[],ts))

    def test_r4_rejects_source_at_sensor_height(self):
        raw=self.raw();raw['room_fire_rule']['trigger_mode']='fuel_r4'
        raw['fuel_groups'][0]['position_m'][2]=1.5
        with self.assertRaisesRegex(ValueError,'fire base'):prepare(raw)

if __name__=='__main__':unittest.main()
