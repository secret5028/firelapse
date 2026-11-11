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
    def test_bundled_converter_is_used_without_local_config(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'app'
            for name in ('cad-reader/run_building.py','cad-tools/libredwg/dwg2dxf.exe'):
                (root/name).parent.mkdir(parents=True);(root/name).write_bytes(b'')
            with patch.object(imp,'ROOT',root):cfg=imp.runtime()
            self.assertEqual(Path(cfg['reader_dir']),root/'cad-reader')
            self.assertEqual(Path(cfg['dwg2dxf']),root/'cad-tools/libredwg/dwg2dxf.exe')
            self.assertEqual(cfg['dependency_paths'],[str(root/'simulation/cad_deps')])
    def test_missing_converter_is_reported(self):
        with tempfile.TemporaryDirectory() as d, patch.object(imp,'ROOT',Path(d)/'app'), self.assertRaisesRegex(ValueError,'미설정'):
            imp.runtime()
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
