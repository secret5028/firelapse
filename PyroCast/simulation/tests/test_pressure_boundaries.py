import unittest
from copy import deepcopy
from unittest.mock import patch
import numpy as np
from test_physics_p0 import sealed
from pyrocast_cfbt.leakage import apply_minimum_leakage,BOUNDARY_REVISION
from pyrocast_cfbt.validation import validate_native,SPECIES
class PressureBoundaries(unittest.TestCase):
 def test_closing_exterior_door_retains_passive_path(self):
  for schedule in ([[0,1],[30,0]],[[0,0],[30,1]]):
   m=sealed();m['openings'].append(dict(id='Exit',a='Stair',b='OUTSIDE',schedule=schedule));apply_minimum_leakage(m)
   self.assertTrue(m['minimum_leakage']);self.assertEqual(m['boundary_revision'],BOUNDARY_REVISION)
   before=deepcopy(m);apply_minimum_leakage(m);self.assertEqual(m,before)
 def test_fan_cutoff_does_not_remove_passive_path(self):
  for direction in ('supply','exhaust'):
   m=sealed();m['mechanical_vents']=[dict(id='Fan',comp='Fire',flow_m3_s=2,direction=direction,cutoffs=[200,300])];apply_minimum_leakage(m)
   self.assertTrue(m['minimum_leakage']);self.assertEqual(m['mechanical_vents'][0]['flow_m3_s'],2)
 def test_above_grade_sealed_room_uses_same_rule(self):
  m=sealed()
  for r in m['rooms']:r['below_grade']=False;r['origin_m'][2]=3;r['leak_area_ratio']=[0,0]
  apply_minimum_leakage(m);self.assertTrue(m['minimum_leakage'])
 def test_existing_passive_exit_unchanged(self):
  m=sealed();m['openings'].append(dict(id='Exit',a='Stair',b='OUTSIDE',schedule=[[0,.1],[30,1]]));apply_minimum_leakage(m);self.assertEqual(m['minimum_leakage'],[])
class MassLedger(unittest.TestCase):
 def test_native_cumulative_fuel_handles_pulse_between_samples(self):
  t=np.array([0.,10.]);mass={'Time':t};units={}
  for layer in ('UL','LL'):
   for species in SPECIES:k=f'{layer}M{species}_1';mass[k]=np.zeros(2);units[k]='kg'
  mass['ULMN2_1']=np.array([10.,12.]);mass['PYTOL_T_1']=np.array([0.,2.]);units['PYTOL_T_1']='kg'
  c=dict(Time=t,PRS_1=np.array([0.,5.]),PYROL_1=np.zeros(2),HRR_1=np.ones(2),HRR_E1=np.ones(2))
  m=dict(rooms=[dict(id='A',leak_area_ratio=[0,0])],openings=[])
  with patch('pyrocast_cfbt.native.read_native_csv',return_value=(mass,{},units)):
   result=validate_native(dict(compartments=c),m,'.')
  self.assertTrue(result['passed']);self.assertEqual(result['metrics']['mass_balance_error'],0)
  self.assertEqual(result['metrics']['fuel_ledger_basis'],'native_cumulative');self.assertEqual(result['metrics']['pressure_peak_room'],'A');self.assertEqual(result['metrics']['pressure_peak_time_s'],10)
  mass['ULMN2_1'][-1]=13
  with patch('pyrocast_cfbt.native.read_native_csv',return_value=(mass,{},units)):
   result=validate_native(dict(compartments=c),m,'.')
  self.assertIn('mass_balance_error',[x['check'] for x in result['reasons']])
