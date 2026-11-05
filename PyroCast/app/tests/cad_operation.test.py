"""New CAD operation registration and no-result bootstrap; no solver execution."""
import sys, unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import model_operation as op
import model_simulation as sim

class NewCADOperationTest(unittest.TestCase):
 def test_scans_cannot_be_registered(self):
  with self.assertRaises(ValueError):op.register_cad({'id':'scan-x','source_kind':'scan'},[{'ok':True}],{'models':[]})
 def test_failed_floors_do_not_enable_execution(self):
  row={'id':'cad-x','source_kind':'cad'}
  op.register_cad(row,[{'floor':'1F','ok':False}],{'models':[]})
  self.assertFalse(row['simulation_enabled']);self.assertIsNone(row['operation_url'])
 def test_partial_validity_and_stable_operation_port(self):
  row={'id':'cad-x','source_kind':'cad'}
  registry={'models':[dict(row,operation_port=8877)]}
  floors=[{'floor':'1F','ok':True},{'floor':'2F','ok':False,'error':'bad width'}]
  op.register_cad(row,floors,registry)
  self.assertTrue(row['simulation_enabled']);self.assertEqual(row['calculation_floors'],floors)
  self.assertEqual(row['operation_url'],'http://127.0.0.1:8877/model.html')
  self.assertEqual(row['execution_mode'],'library_lite')
 def test_disabled_cad_rejected(self):
  with patch.object(sim,'entries',return_value=[dict(id='x',source_kind='cad',execution_mode='library_lite',simulation_enabled=False)]):
   with self.assertRaises(ValueError):sim.entry('x')
 def test_empty_building_has_no_fake_measurements(self):
  b={'floors':[dict(name='1F',z=0,h=3,rooms=[dict(id='R1',names=['Room'],polys=[{'o':[[0,0],[3,0],[3,3],[0,3]],'h':[]}])])]}
  with patch.object(sim,'entry',return_value={}),patch.object(op,'model_path',return_value='unused'),patch.object(sim,'read',return_value=b),patch.object(sim,'fingerprint',return_value='abc'):
   p=op.model_preview('x')
  self.assertTrue(p['model_preview']);self.assertFalse(p['complete']);self.assertIsNone(p['fire_key'])
  self.assertEqual(p['solvers'],{});self.assertEqual(p['fires'],[]);self.assertEqual(len(p['rooms']),1)
 def test_startup_includes_registered_new_models(self):
  rows=[{'id':'parkmarine'},{'id':'cad-new'}]
  with patch('model_library.entries',return_value=rows),patch.object(op,'ensure_server',side_effect=['existing','new']) as start:
   self.assertEqual(op.start_servers(object),['existing','new']);self.assertEqual(start.call_count,2)
  op._base_handler=None
 def test_ai_status_only_registered_operation_can_read(self):
  import ai_connection as con
  from types import SimpleNamespace
  h=SimpleNamespace(headers={'Host':'127.0.0.1:8841','Origin':'http://127.0.0.1:8877'},client_address=('127.0.0.1',50000),server=SimpleNamespace(server_port=8841),command='GET',json=lambda v,code=200:(code,v))
  with patch('model_library.entries',return_value=[{'operation_url':'http://127.0.0.1:8877/model.html'}]):
   code,value=con.handle(h,'/models/ai/connection');self.assertEqual(code,200);self.assertNotIn('api_key',value)
   h.command='POST';self.assertEqual(con.handle(h,'/models/ai/connection')[0],403)
   h.command='GET';h.headers['Origin']='http://example.invalid';self.assertEqual(con.handle(h,'/models/ai/connection')[0],403)
 def test_active_without_results_returns_geometry_not_a_case(self):
  with patch.object(op,'jobs',return_value=[]),patch.object(sim,'fingerprint',return_value='abc'),patch('model_mc.cases',return_value=[]),patch('fixed_calculation.cases',return_value=[]),patch.object(op,'model_preview',return_value={'model_preview':True}) as preview:
   self.assertEqual(op.active_playback('new'),{'model_preview':True});preview.assert_called_once_with('new')
 def test_active_can_restore_saved_mc_without_seed_calculation(self):
  with patch.object(op,'jobs',return_value=[]),patch.object(sim,'fingerprint',return_value='abc'),patch('model_mc.cases',return_value=[{'id':'modelmc-test-S01'}]),patch('fixed_calculation.cases',return_value=[]),patch.object(op,'playback',return_value={'complete':True}) as playback:
   self.assertEqual(op.active_playback('new'),{'complete':True});playback.assert_called_once_with('new','modelmc-test-S01')
if __name__=='__main__':unittest.main()
