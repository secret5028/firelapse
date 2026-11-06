import json,math,unittest
from pathlib import Path
from copy import deepcopy
import numpy as np
from pyrocast_cfbt.room_rule_r7 import prepare,DEFAULTS
from pyrocast_cfbt.rule_cells import partition
from pyrocast_cfbt.rule_graph_r7 import delay_parents
from pyrocast_cfbt.deck import fire_curve,make_deck
ROOT=Path(__file__).resolve().parents[2]
class R7Tests(unittest.TestCase):
 def raw(self):return json.loads((ROOT/'fixtures/room_rule_benchmark_3room.json').read_text('utf-8'))
 def test_initial_energy_and_shape(self):
  m=self.raw();m['rooms'][0]['size_m']=[20,10,2.7]
  old=m['fuel_groups'][0];before=fire_curve(old,200)
  out,info=partition(m,split_initial=True)
  group=next(g for g in out['fuel_groups'] if 'initial_time_s' in g)
  share=group['room_rule_curve']['area_fraction']
  self.assertEqual(share,.5);np.testing.assert_array_equal(before[0],group['room_rule_curve']['t'])
  np.testing.assert_allclose(np.asarray(before[1])*.5,group['room_rule_curve']['q'])
  allocated=[g for g in out['fuel_groups'] if g['room'].startswith('R1_')]
  self.assertEqual(len(allocated),2);self.assertAlmostEqual(sum(g['energy_MJ'] for g in allocated),old['energy_MJ'])
  self.assertAlmostEqual(info['total_energy_MJ_before'],info['total_energy_MJ_after'])
 def test_passage_uses_immediate_sensor_not_root(self):
  m=self.raw();m['fuel_groups']=[g for g in m['fuel_groups'] if g['room']!='R2']
  model,targets,manifest=prepare(m)
  third=next(g for g in model['fuel_groups'] if g['room']=='R3')
  self.assertEqual(third['room_rule_trigger']['target_id'],'PC_R2')
  self.assertEqual(third['parent_transition']['delay_s'],60)
  self.assertTrue(next(t for t in targets if t['id']=='PC_R2')['passage_without_fire'])
 def test_item_and_room_supply_budget(self):
  m=self.raw()
  for g in m['fuel_groups']:
   if 'initial_time_s' not in g:g['peak_kW']=100
  a,_,ma=prepare(m);m['room_rule_r7']={'room_supply':'item_peak'};b,_,mb=prepare(m)
  for x,y in zip(a['fuel_groups'][1:],b['fuel_groups'][1:]):
   self.assertGreater(max(x['room_rule_curve']['q']),max(y['room_rule_curve']['q']))
   for g in (x,y):
    c=g['room_rule_curve'];self.assertAlmostEqual(np.trapezoid(c['q'],c['t'])/1000,g['energy_MJ'],places=7)
 def test_cell_300_and_distance(self):
  m=self.raw();m['rooms'][0]['size_m']=[20,10,2.7]
  out,targets,manifest=prepare(m)
  sibling=next(g for g in out['fuel_groups'] if g['room'].startswith('R1_') and 'initial_time_s' not in g)
  self.assertEqual(sibling['room_rule_trigger']['setpoint'],300)
  self.assertEqual(sibling['parent_transition']['delay_s'],200)
  self.assertTrue(sibling['room_rule_trigger']['target_id'].startswith('FC_'))
 def test_fallback_and_native_only(self):
  if not (ROOT/'simulation/results/mixture_r3f_cache_20261023/floor60/scenario.json').exists(): self.skipTest('SKIP: evidence folder missing')
  raw=json.loads((ROOT/'simulation/results/mixture_r3f_cache_20261023/floor60/scenario.json').read_text('utf-8'))
  m,t,manifest=prepare(raw)
  self.assertEqual(set(manifest['fallback_sensors']),{'CAD_3F_R13','CAD_3F_R19','CAD_3F_R20'})
  self.assertTrue(all(x['quality_label']=='판정 불확실' for x in t if x.get('sensor_quality')=='fallback'))
  self.assertNotIn('&CFBT',make_deck(m,[],t))
  self.assertAlmostEqual(manifest['initial_source']['area_fraction'],1/3)
  self.assertAlmostEqual(sum(g['energy_MJ'] for g in raw['fuel_groups']),
    sum(g['energy_MJ'] for g in m['fuel_groups'])+sum(g['energy_MJ'] for g in manifest['omitted_fuel']),places=6)
  self.assertFalse(any(m['gas'][k] for k in ('enabled','bulk_enabled','mixture_enabled')))
 def test_missing_coverage_defaults_half_and_invalid_rejected(self):
  m=self.raw()
  for g in m['fuel_groups']:g.pop('fuel_area_m2',None)
  _,_,manifest=prepare(m)
  self.assertEqual(manifest['supplies']['R2']['coverage_fraction'],.5)
  m['room_rule_r7']={'room_supply':'typo'}
  with self.assertRaises(ValueError):prepare(m)
if __name__=='__main__':unittest.main()
