"""Isolated import tests. Mock interpretation exists only here, never in production."""
import base64, io, json, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image, ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
import model_import as imp
import model_library as library

def scan_bytes():
    im=Image.new('RGB',(400,300),'white');ImageDraw.Draw(im).rectangle((40,30,360,270),outline='black',width=4)
    b=io.BytesIO();im.save(b,format='PNG');return b.getvalue()

def interpretation():
    p=[[.1,.1],[.9,.1],[.9,.9],[.1,.9]]
    return dict(drawing_name='시험 도면',floor='1F',height_m=3,outline=p,
        walls=[dict(a=a,b=b,evidence='test fixture wall') for a,b in zip(p,p[1:]+p[:1])],openings=[],
        scale_anchor=dict(a=[.1,.1],b=[.9,.1],length_m=16),alignment=dict(id='X1-Y1',point=[.1,.1]),critical=[],warnings=[])

class ImportTest(unittest.TestCase):
    def setUp(self):
        self.testroot=Path(__file__).resolve().parents[2]/'reviews/new-building-20261105/test-temp';self.testroot.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=self.testroot);self.root=Path(self.temp.name)
        self.registry=self.root/'config/model-library.json';imp.atomic_json(self.registry,{'models':[{'id':'existing'}]})
        self.patches=[patch.object(imp,'ROOT',self.root),patch.object(imp,'STAGING',self.root/'data/model-imports'),patch.object(library,'REGISTRY',self.registry),patch.object(imp,'configured',return_value=False)]
        for p in self.patches:p.start()
        self.file=dict(name='건물/1F.png',data=base64.b64encode(scan_bytes()).decode())
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        assert self.root.resolve().is_relative_to(self.testroot.resolve())
        self.temp.cleanup()
    def job(self,number=1):
        value=imp.upload({'files':[self.file]});dest=imp.folder(value['id'])
        row=value['pages'][0];row.update(imp.clean_geometry(interpretation(),row));row['floor']=imp.floor_label(number)
        value['state']='review';imp.atomic_json(dest/'manifest.json',value)
        body=dict(name='시험 건물',lowest=row['floor'],highest=row['floor'],reviewed=True,pages=[dict(id=row['id'],included=True,floor=row['floor'],height_m=3,pixels_per_m=20)])
        return value,body
    def test_upload_preview_and_original_hash(self):
        v=imp.upload({'files':[self.file,self.file]});self.assertEqual(len(v['pages']),1);self.assertFalse(v['ai_available']);self.assertTrue((imp.folder(v['id'])/'page-1.png').exists());self.assertEqual(len(v['files'][0]['sha256']),64)
    def test_unconfigured_ai_cannot_fake_geometry(self):
        v=imp.upload({'files':[self.file]})
        with self.assertRaisesRegex(ValueError,'판독 연결 필요'):imp.analyse(v['id'])
        self.assertIsNone(imp.status(v['id'])['pages'][0]['geometry'])
    def test_generate_registers_once_without_simulation(self):
        v,b=self.job();result=imp.generate(v['id'],b);again=imp.generate(v['id'],b)
        self.assertEqual(result['model_id'],again['model_id']);reg=imp.read(self.registry);self.assertEqual(len(reg['models']),2)
        e=reg['models'][1];self.assertFalse(e['simulation_enabled']);m=imp.read(self.root/e['path']);self.assertFalse(m['model_provenance']['simulation_allowed']);self.assertEqual(m['floors'][0]['scan_page']['scale'],.05)
    def test_missing_floor_blocks_registry(self):
        v,b=self.job();b['highest']='3F';out=imp.generate(v['id'],b);self.assertEqual(out['state'],'blocked');self.assertIn('누락 층: 2F, 3F',out['errors']);self.assertEqual(len(imp.read(self.registry)['models']),1)
    def test_missing_basement(self):
        v,b=self.job();b['lowest']='B1';self.assertIn('누락 층: B1',imp.inspect(v['id'],b)[0]['errors'])
    def test_no_scale_no_height_no_confirmation(self):
        v,b=self.job();b['pages'][0].update(height_m=None,pixels_per_m=None);b['reviewed']=False
        check,_=imp.inspect(v['id'],b);self.assertFalse(check['ok']);self.assertTrue(any('축척' in e for e in check['errors']));self.assertTrue(any('층고' in e for e in check['errors']))
    def test_severe_geometry_defect_blocks(self):
        v,b=self.job();v['pages'][0]['critical']=['외벽 일부 판독 불가'];imp.atomic_json(imp.folder(v['id'])/'manifest.json',v);self.assertFalse(imp.inspect(v['id'],b)[0]['ok'])
    def test_uninterpreted_pages_block_without_crash(self):
        v=imp.upload({'files':[self.file]});b=dict(name='x',lowest='1F',highest='1F',reviewed=True,pages=[dict(id='1',included=True,floor='1F',height_m=3,pixels_per_m=20)])
        self.assertFalse(imp.inspect(v['id'],b)[0]['ok'])
    def test_multifloor_alignment_and_duplicate_floor(self):
        v,b=self.job();row=dict(v['pages'][0],id='2');row['geometry']=dict(row['geometry'],alignment=None);v['pages'].append(row);imp.atomic_json(imp.folder(v['id'])/'manifest.json',v);b['pages'].append(dict(b['pages'][0],id='2'))
        errors=imp.inspect(v['id'],b)[0]['errors'];self.assertTrue(any('중복' in x for x in errors));self.assertTrue(any('정렬' in x for x in errors))
    def test_invalid_polygon_and_nan(self):
        self.assertFalse(imp.polygon_valid([[0,0],[1,1],[0,1],[1,0]]));self.assertFalse(imp.polygon_valid([[0,0],[1,0],[float('nan'),1]]));self.assertTrue(imp.polygon_valid([[0,0],[1,0],[1,1],[0,1]]))
    def test_traversal_and_unsupported_file(self):
        for name in ['../1F.png','C:/1F.png','/1F.png','plan.exe']:
            with self.assertRaises(ValueError):imp.upload({'files':[dict(self.file,name=name)]})
        with self.assertRaises(ValueError):imp.folder('../secret')
    def test_corrupt_image_is_failed_not_published(self):
        v=imp.upload({'files':[dict(self.file,data=base64.b64encode(b'bad').decode())]});self.assertEqual(v['state'],'failed');self.assertEqual(len(imp.read(self.registry)['models']),1)
    def test_floor_range_and_unknown_floor(self):
        self.assertEqual(imp.floor_number('지하 3층'),-3);self.assertEqual(imp.floor_number('5F'),5)
        for label in ['0F','PH','no floor','101F']:
            with self.assertRaises(ValueError):imp.floor_number(label)

if __name__=='__main__':unittest.main()
