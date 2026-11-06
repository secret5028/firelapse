import json,sys,unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
from pyrocast_cfbt.rule_settings import FIELDS,PRESETS,resolve,comparison_options
from pyrocast_cfbt.room_rule_r8 import prepare
from pyrocast_cfbt.deck import make_deck
class R8SettingsTests(unittest.TestCase):
 def raw(self):return json.loads((ROOT/'fixtures/room_rule_benchmark_3room.json').read_text('utf-8'))
 def test_each_range_rejected_before_prepare(self):
  for key,(_,unit,default,lo,hi) in FIELDS.items():
   for value in (lo-1,hi+1,'bad',float('nan'),float('inf'),True,None):
    with self.subTest(key=key,value=value),patch('pyrocast_cfbt.room_rule_r8.prepare_r7') as generator:
     with self.assertRaises(ValueError) as error:prepare({**self.raw(),'room_rule_r8':{key:value}})
     self.assertIn(f'{lo:g}~{hi:g}',str(error.exception));generator.assert_not_called()
 def test_bounds_and_presets(self):
  for key,(_,_,_,lo,hi) in FIELDS.items():
   self.assertEqual(resolve({key:lo})['values'][key],lo);self.assertEqual(resolve({key:hi})['values'][key],hi)
  for name in PRESETS:self.assertEqual(resolve({'preset':name})['preset'],name)
 def test_defaults_override_provenance(self):
  self.assertEqual(resolve()['room_supply'],'item_peak')
  self.assertEqual(resolve({'room_supply':'room_involvement'})['values']['vent_cap_k'],.7)
  s=resolve({'preset':'aggressive','temperature_C':600})
  self.assertEqual(s['values']['ramp_s'],30);self.assertTrue(s['parameters']['temperature_C']['is_default'])
  self.assertEqual(s['parameters']['temperature_C']['source'],'user_override')
  self.assertFalse(s['parameters']['ramp_s']['is_default'])
 def test_aggressive_alternate_drops_six_overrides_only(self):
  options=comparison_options({'temperature_C':650,'room_supply':'room_involvement','coverage_default':.8,'vent_cap_k':.9})
  s=resolve(options);self.assertEqual(s['values']['temperature_C'],500);self.assertEqual(s['values']['coverage_default'],.8)
  self.assertEqual(s['values']['vent_cap_k'],.9)
 def test_coverage_only_standby_supply_and_initial_unchanged(self):
  raw=self.raw();raw['room_rule_r8']={'room_supply':'room_involvement','coverage_default':.2}
  a,_,ma=prepare(raw);raw['room_rule_r8']['coverage_default']=1.
  b,_,mb=prepare(raw)
  self.assertEqual(a['fuel_groups'][0]['room_rule_curve'],b['fuel_groups'][0]['room_rule_curve'])
  self.assertEqual(ma['supplies']['R2']['coverage_fraction'],.2);self.assertEqual(mb['supplies']['R2']['coverage_fraction'],1.)
 def test_closed_fire_door_blocked_open_uses_scenario(self):
  raw=self.raw();raw['openings'][0].update(fire_door=True,schedule=[[0,0]])
  _,_,m=prepare(raw);self.assertNotIn('R2',m['parents'])
  raw['openings'][0]['schedule']=[[0,1]]
  _,_,m=prepare(raw);self.assertEqual(m['parents']['R2']['delay_s'],60);self.assertEqual(m['initially_open_fire_doors'],['D12'])
 def test_default_matches_frozen_r7_item_deck(self):
  if not (ROOT/'simulation/results/mixture_r3f_cache_20261023/floor60/scenario.json').exists(): self.skipTest('SKIP: evidence folder missing')
  if not (ROOT/'simulation/results/room_rule_r7_20261025/C/item_peak/case.in').exists(): self.skipTest('SKIP: evidence folder missing')
  raw=json.loads((ROOT/'simulation/results/mixture_r3f_cache_20261023/floor60/scenario.json').read_text('utf-8'))
  m,t,_=prepare(raw)
  self.assertEqual(make_deck(m,[],t),(ROOT/'simulation/results/room_rule_r7_20261025/C/item_peak/case.in').read_text('ascii'))
if __name__=='__main__':unittest.main()
