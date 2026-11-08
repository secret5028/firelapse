import sys,unittest,tempfile,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from serve_wando_c11 import empty_playback

class DeletedSamplePreview(unittest.TestCase):
    def test_deleted_sample_keeps_geometry_without_synthetic_results(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/'operating-building.json').write_bytes((ROOT/'data/wando-coldstore/operating-building.json').read_bytes())
            data=empty_playback(p)
            self.assertTrue(data['model_preview']);self.assertFalse(data['complete'])
            self.assertEqual(data['solvers'],{});self.assertIsNone(data['fire_key'])
            self.assertGreater(len(data['rooms']),0);self.assertEqual(data['time_s'],[0])
            self.assertFalse((p/'P1-playback.json').exists())

if __name__=='__main__':unittest.main()
