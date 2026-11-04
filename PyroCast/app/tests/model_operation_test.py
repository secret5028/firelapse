"""Read-only operational UI integration; no solver invocation."""
import sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import model_operation as op
class OperationTest(unittest.TestCase):
 def test_existing_results_and_isolation(self):
  hotel=op.playback('parkmarine');showroom=op.playback('showroom')
  self.assertNotEqual(hotel['building_sha256'],showroom['building_sha256'])
  self.assertEqual(hotel['time_s'][-1],60)
  with self.assertRaises(ValueError):op.playback('showroom',hotel['case_id'])
 def test_display_does_not_run(self):
  with patch.object(op.sim,'start',side_effect=AssertionError('simulation forbidden')):
   for ident,floor in [('parkmarine','5F'),('showroom','2F')]:
    self.assertTrue(op.jobs(ident));self.assertTrue(op.playback(ident)['rooms'])
    v=op.screening(ident,floor)
    self.assertFalse(v['available']);self.assertIsNone(v['comparison'])
    self.assertTrue(all(r['floor']==floor for r in v['score']['ranked']))
 def test_stale_building_rejected(self):
  with patch.object(op.sim,'fingerprint',return_value='0'*64):
   self.assertEqual(op.jobs('parkmarine'),[])
   with self.assertRaises(ValueError):op.playback('parkmarine')
if __name__=='__main__':unittest.main()
