import sys,unittest,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'simulation')]
from fixed_native_playback import native_geometry
class PhysicalPlayback(unittest.TestCase):
 def test_union_of_cells_keeps_fires_and_does_not_change_saved_payload(self):
  cells=[]
  for i in range(2):
   x=5*i;cells.append(dict(key=f'X{i}',solver_id=f'X{i}',original_room='X',cad_floor='5F',cad_room=str(i),cad_polys=[dict(o=[[x,0],[x+5,0],[x+5,4],[x,4]],h=[])],cad_center_m=[x+2,2],area_m2=20,z_m=0,height_m=3))
  saved=dict(rooms=cells,fire_key='X1',fires=[dict(id='F',cad_key='X1',solver_id='X1',Q_kW=[0,100])],fuel_symbols=[dict(room='X0')]);before=copy.deepcopy(saved)
  model=dict(rooms=[dict(id='X',size_m=[10,4,3])],native_compartments={'cell_to_room':{'X0':'X','X1':'X'}})
  result=native_geometry(model,saved)
  self.assertEqual(saved,before);self.assertEqual(result['fire_key'],'X');self.assertEqual(len(result['rooms']),1);self.assertEqual(result['rooms'][0]['area_m2'],40);self.assertEqual(result['fires'][0]['Q_kW'],[0,100]);self.assertEqual(result['fuel_symbols'][0]['room'],'X')
  model['native_compartments']['cell_to_room']['missing']='Y'
  with self.assertRaises(ValueError):native_geometry(model,saved)
 def test_single_zone_has_full_upper_layer(self):
  import numpy as np
  from pyrocast_cfbt.native_criteria import native_interface
  c={'Time':np.array([0,5])};np.testing.assert_array_equal(native_interface(c,{'shaft':True},1),[0,0]);self.assertTrue(np.isnan(native_interface(c,{},1)).all())
if __name__=='__main__':unittest.main()
