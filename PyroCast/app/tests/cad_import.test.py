"""CAD-only import validation; never runs a fire simulation."""
import base64, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'simulation/plot_deps')]
import cad_import as imp

class CADImportTest(unittest.TestCase):
    def test_reject_scan_and_paths_before_storage(self):
        for name in ['scan.png','scan.pdf','../a.dwg','C:/a.dwg']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                imp.upload({'files':[dict(name=name,data=base64.b64encode(b'AC1027').decode())]})
    def test_invalid_dwg_header(self):
        with self.assertRaisesRegex(ValueError,'헤더'):
            imp.upload({'files':[dict(name='scan.dwg',data=base64.b64encode(b'not cad').decode())]})
    def test_cad_saved_with_original_hash(self):
        with tempfile.TemporaryDirectory() as d, patch.object(imp,'STAGING',Path(d)), patch.object(imp,'runtime',return_value={}):
            v=imp.upload({'files':[dict(name='floor.dwg',data=base64.b64encode(b'AC1027test').decode())]})
            self.assertEqual(v['state'],'uploaded')
            self.assertEqual((Path(d)/v['id']/'source/floor.dwg').read_bytes(),b'AC1027test')
            self.assertEqual(len(v['files'][0]['sha256']),64)
    def test_floor_range(self):
        self.assertEqual(imp.expected_floors(dict(lowest='B1',highest='2F')),['B1','1F','2F'])
        with self.assertRaises(ValueError):imp.expected_floors(dict(lowest='3F',highest='1F'))
    def test_reject_missing_floor_and_severe_geometry(self):
        from types import SimpleNamespace
        shapes={'slab':SimpleNamespace(area=100,is_empty=False),'tiny':SimpleNamespace(area=5)}
        with patch('prepare_building_graph.geometry',side_effect=lambda x:shapes[x]):
            errors,_=imp.geometry_checks(dict(floors=[dict(name='1F',slab='slab',h=3,rooms=[dict(polys='tiny')])]),['1F','2F'])
        self.assertTrue(any('누락 층' in e for e in errors))
        self.assertTrue(any('심각한 결측' in e for e in errors))

if __name__=='__main__':unittest.main()
