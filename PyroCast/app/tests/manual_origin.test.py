import sys,json,hashlib,unittest,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'simulation'),str(ROOT/'simulation/deps')]
from pyrocast_lite.screening_v8_approved import score
from lite_manual_origin import origins,validate_rooms,manual_scenario
class ManualOrigin(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  raw=json.loads((ROOT/'simulation/results/room_rule_r8_20261025/source-scenario.json').read_text('utf-8'))
  cls.scored=score(raw,8);cls.before=json.dumps(cls.scored,sort_keys=True)
 def test_outside_ranking(self):
  s=self.scored;rid='CAD_3F_R11'
  self.assertNotIn(rid,{r['room'] for r in s['ranked']})
  self.assertIn(rid,{r['room'] for r in origins(s)})
  for state in ('open_except_confirmed','closed'):
   data=manual_scenario(s,rid,state);initial=[g for g in data['fuel_groups'] if 'initial_time_s' in g]
   self.assertEqual(len(initial),1);self.assertEqual(initial[0]['room'],rid)
   self.assertEqual(data['cad']['fire_key'],rid)
   self.assertEqual(initial[0]['energy_MJ'],s['origin_budgets'][rid]['energy_MJ'])
   self.assertEqual(initial[0]['peak_kW'],s['origin_budgets'][rid]['Q_origin_peak_kW'])
   self.assertEqual(s['origin_budgets'][rid]['fuel_load_MJ_m2'],40)
  self.assertEqual(json.dumps(s,sort_keys=True),self.before)
 def test_reject(self):
  for rooms in ([],['CAD_3F_R11','CAD_3F_R2'],'CAD_3F_R11',['CAD_3F_R14'],['CAD_3F_R2_C0'],['../bad']):
   with self.assertRaises(ValueError):validate_rooms(self.scored,rooms)
 def test_existing_origin_unchanged(self):
  from pyrocast_lite.screening_v8_approved import scenario
  for state in ('open_except_confirmed','closed'):
   old=scenario(self.scored,'CAD_3F_R2',state);new=manual_scenario(self.scored,'CAD_3F_R2',state)
   new['cad']=old['cad'];new['screening_source']=old['screening_source'];self.assertEqual(old,new)
if __name__=='__main__':unittest.main()
