import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'simulation')]
from fixed_calculation import set_ventilation_input
from pyrocast_cfbt.leakage import apply_minimum_leakage
class FanInputs(unittest.TestCase):
 def model(self):return dict(rooms=[dict(id='Room',size_m=[10,10,3],origin_m=[0,0,-3],below_grade=True)],fuel_groups=[dict(id='Fire',room='Room',initial_time_s=0)],openings=[],mechanical_vents=[dict(id='Old',comp='Room',flow_m3_s=3)])
 def test_zero_means_fan_off_not_no_leakage(self):
  m=self.model();set_ventilation_input(m,dict(room='Room',ventilation_ach=0));self.assertEqual(m['mechanical_vents'],[]);apply_minimum_leakage(m);self.assertTrue(m['minimum_leakage']);self.assertEqual(m['ventilation_assumptions']['Room']['mode'],'off')
 def test_balanced_flow_and_shared_leakage(self):
  m=self.model();set_ventilation_input(m,dict(room='Room',ventilation_ach=6));self.assertEqual(len(m['mechanical_vents']),2);self.assertTrue(all(v['flow_m3_s']==.5 for v in m['mechanical_vents']));apply_minimum_leakage(m);self.assertTrue(m['minimum_leakage'])
 def test_invalid_ach_rejected(self):
  for x in (-1,float('nan'),float('inf'),True,'6'):
   with self.assertRaises(ValueError):set_ventilation_input(self.model(),dict(room='Room',ventilation_ach=x))
if __name__=='__main__':unittest.main()
