"""Input isolation and validation tests; no solver execution."""
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import model_simulation as sim

class ModelSimulationTest(unittest.TestCase):
 def test_scan_cannot_enter_worker(self):
  for ident in ('apartment-scan','modori-scan','../parkmarine','wando','ganghwa'):
   with self.assertRaises(ValueError):sim.entry(ident)
 def test_hotel_and_showroom_isolated(self):
  fingerprints=[]
  for ident,floor in [('parkmarine','5F'),('showroom','2F')]:
   sha=sim.fingerprint(ident);raw,score=sim.prepared(ident,floor,sha)
   fingerprints.append(sha)
   rid=next(r['room'] for r in score['ranked'] if r['origin_budget']['Q_origin_peak_kW']>0)
   data,digest=sim.request_data(dict(building=ident,floor=floor,room=rid,duration_s=60,opening_state='closed'))
   self.assertEqual(digest,sha);self.assertEqual(data['cad']['building_sha256'],sha)
   self.assertEqual(data['duration_s'],60);self.assertEqual(data['cad']['fire_key'],rid)
   self.assertTrue(all(r['cad_floor']==floor for r in data['rooms']))
   self.assertEqual([g['room'] for g in data['fuel_groups'] if g.get('initial_time_s')==0],[rid])
   self.assertEqual(data['screening_source']['state'],'closed')
  self.assertNotEqual(*fingerprints)
 def test_b1_geometry_corrections_are_explicit(self):
  raw,_=sim.prepared('parkmarine','B1',sim.fingerprint('parkmarine'))
  repairs=[v['width_correction'] for v in raw['openings'] if v.get('width_correction')]
  self.assertTrue(repairs)
  self.assertTrue(all(r['revision']=='cad_aperture_extent_v1' and r['previous_width_m']>r['width_m'] for r in repairs))
  self.assertTrue(any('여유 폭 축소' in w for w in raw['cad']['warnings']))
 def test_invalid_request_never_launches(self):
  body=dict(building='parkmarine',floor='5F',room='CAD_5F_R16',duration_s=60,opening_state='closed')
  for patch in [dict(duration_s=True),dict(duration_s=61),dict(duration_s=7200),dict(opening_state='invented'),dict(room='CAD_3F_R2')]:
   with self.assertRaises(ValueError):sim.request_data({**body,**patch})
 def test_job_traversal_rejected(self):
  with self.assertRaises(ValueError):sim.job_path('parkmarine','../../wando')

if __name__=='__main__':unittest.main()
