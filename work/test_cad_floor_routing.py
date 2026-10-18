import sys,pathlib,tempfile,unittest
W=pathlib.Path(__file__).resolve().parent;sys.path[:0]=[str(W/'cad-deps'),str(W/'cad-web'),str(W/'cad-web/cad_engine')]
import ezdxf
from cad_upload import inspect_dxf
class Routing(unittest.TestCase):
 def inspect(self,titles,override=None):
  with tempfile.TemporaryDirectory(dir=W/'test-temp') as tmp:
   p=pathlib.Path(tmp)/'input.dxf';d=ezdxf.new();m=d.modelspace()
   for t in titles:m.add_text(t)
   d.saveas(p);return inspect_dxf(p,'input.dxf',override)['floors']
 def test_basement_with_stair_detail(self):self.assertEqual(self.inspect(['지 하 1층 평 면 도','계단실#3 지상1층 평면도']),['B1'])
 def test_multi_floor_cannot_be_overridden(self):self.assertEqual(self.inspect(['1층 평면도','2층 평면도'],'1F'),['1F','2F'])
 def test_unknown_override(self):self.assertEqual(self.inspect(['건축 평면도'],'3F'),['3F'])
 def test_inserted_title(self):
  with tempfile.TemporaryDirectory(dir=W/'test-temp') as tmp:
   p=pathlib.Path(tmp)/'input.dxf';d=ezdxf.new();d.blocks.new('TITLE').add_text('옥탑층 평면도');d.modelspace().add_blockref('TITLE',(0,0));d.saveas(p)
   self.assertEqual(inspect_dxf(p,'input.dxf')['floors'],['PH'])
if __name__=='__main__':unittest.main()
