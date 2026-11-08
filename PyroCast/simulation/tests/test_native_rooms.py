import unittest,copy
from pyrocast_cfbt.native_rooms import coalesce
class NativeRoomTests(unittest.TestCase):
 def model(self):
  return dict(rooms=[dict(id='X0',parent_room='X',origin_m=[0,0,0],size_m=[5,4,3]),dict(id='X1',parent_room='X',origin_m=[5,0,0],size_m=[5,4,3]),dict(id='Y',origin_m=[30,0,0],size_m=[4,4,3])],openings=[dict(id='Virtual',a='X0',b='X1',virtual_cell_boundary=True),dict(id='Door',a='X1',b='Y',face='FRONT',offset_m=1,width_m=1)],fuel_groups=[dict(id='F',room='X1',energy_MJ=100,room_rule_curve={'t':[0,10], 'q':[0,100]})],mechanical_vents=[dict(id='Fan',comp='X1',flow_m3_s=1)])
 def test_geometry_fuel_sensors_and_real_opening_preserved(self):
  raw=self.model();before=copy.deepcopy(raw);target=dict(id='T',room='X1',xyz=[6,2,2])
  m,targets,manifest=coalesce(raw,[target],{})
  self.assertEqual(raw,before);self.assertEqual([r['id'] for r in m['rooms']],['X','Y']);self.assertEqual(m['rooms'][0]['size_m'],[10,4,3])
  self.assertEqual(m['fuel_groups'][0]['room_rule_curve'],raw['fuel_groups'][0]['room_rule_curve']);self.assertEqual(m['fuel_groups'][0]['energy_MJ'],100)
  self.assertEqual(m['openings'],[dict(id='Door',a='X',b='Y',face='FRONT',offset_m=6,width_m=1)])
  self.assertEqual(targets,[dict(id='T',room='X',xyz=[6,2,2])]);self.assertEqual(m['mechanical_vents'][0]['flow_m3_s'],1)
  self.assertEqual(manifest['native_compartments']['cell_to_room'],{'X0':'X','X1':'X','Y':'Y'})
 def test_non_tiling_cells_rejected(self):
  m=self.model();m['rooms'][1]['origin_m'][0]=6
  with self.assertRaises(ValueError):coalesce(m,[],{})
 def test_real_internal_wall_not_silently_removed(self):
  m=self.model();m['openings'][0].pop('virtual_cell_boundary')
  with self.assertRaises(ValueError):coalesce(m,[],{})
 def test_identity_without_virtual_cells(self):
  m=self.model();m['rooms']=m['rooms'][2:];m.update(openings=[],fuel_groups=[],mechanical_vents=[])
  m['rooms'][0].update(origin_m=[300,0,20],size_m=[4,4,2.4])
  out,_,_=coalesce(m,[],{});self.assertEqual(out['rooms'][0]['id'],'Y');self.assertEqual(out['rooms'][0]['size_m'],[4,4,2.4])
