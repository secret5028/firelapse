import copy,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
import numpy as np
from pyrocast_cfbt.basement_pressure import configure,below_grade,record_and_resize,rewrite_deck
from pyrocast_cfbt.native import execute,PressureSizingRestart,pressure_prefix

class BasementPressureTests(unittest.TestCase):
 def model(self):
  return dict(rooms=[dict(id='R',cad_floor='B2',origin_m=[0,0,0],size_m=[10,10,3])],
   openings=[dict(id='MINLEAK_R',a='R',b='OUTSIDE',width_m=.02,bottom_m=0,top_m=2,minimum_leakage=True)],fuel_groups=[])
 def test_generic_basement_and_explicit_override(self):
  for f in ('B1','B2','B3','B12','지하2층'):self.assertTrue(below_grade(dict(cad_floor=f),{}))
  self.assertFalse(below_grade(dict(cad_floor='5F'),{}))
  self.assertFalse(below_grade(dict(cad_floor='B2',below_grade=False),{}))
  self.assertTrue(below_grade(dict(origin_m=[0,0,2]),dict(grade_m=3)))
 def test_real_vent_geometry_is_not_changed(self):
  m=self.model();m['openings'][0].pop('minimum_leakage');before=copy.deepcopy(m);configure(m)
  self.assertEqual(m,before)
 def test_formula_and_pressure_history_are_explicit(self):
  m=self.model();configure(m);self.assertTrue(record_and_resize(m,400))
  self.assertAlmostEqual(m['openings'][0]['width_m'],.04)
  self.assertFalse(record_and_resize(m,140));self.assertTrue(m['basement_pressure']['passed'])
  self.assertEqual([h['peak_abs_pressure_Pa'] for h in m['basement_pressure']['history']],[400,140])
 def test_area_limit_fails_instead_of_clipping(self):
  m=self.model();configure(m);m['basement_pressure']['max_area_m2']=.05
  with self.assertRaises(ValueError):record_and_resize(m,400)
  self.assertEqual(m['basement_pressure']['verified_peak_Pa'],400)
 def test_above_ground_and_disabled_leave_policy_off(self):
  m=self.model();m['rooms'][0]['cad_floor']='5F';configure(m);self.assertNotIn('basement_pressure',m)
  m=self.model();m['basement_pressure_settings']={'enabled':False};configure(m);self.assertNotIn('basement_pressure',m)
 def test_native_recalculates_and_preserves_actual_pressure(self):
  m=self.model();configure(m)
  deck="&VENT TYPE='WALL' ID='MINLEAK_R' WIDTH=0.02 TOP=2 /\n&FIRE ID='f' /"
  fake=[dict(compartments={'PRS_1':np.array([0.,400.])}),dict(compartments={'PRS_1':np.array([0.,140.])})]
  with tempfile.TemporaryDirectory() as d,patch('pyrocast_cfbt.native._execute_once',side_effect=fake) as run:
   result=execute('unused',Path(d),deck,'',10,20,validation_model=m)
   self.assertEqual(run.call_count,2);self.assertIn('WIDTH=0.04',run.call_args.args[2]);self.assertIn("&FIRE ID='f'",run.call_args.args[2])
   np.testing.assert_array_equal(result['compartments']['PRS_1'],[0,140])
   self.assertTrue(Path(d,'basement-pressure.json').exists())
 def test_frozen_native_input_is_not_auto_resized(self):
  m=self.model();configure(m)
  with patch('pyrocast_cfbt.native._execute_once',return_value={'frozen':True}) as run:
   result=execute('x','x','x','',10,20,preserve_input_files=True,validation_model=m)
   self.assertEqual(result,{'frozen':True});self.assertEqual(m['basement_pressure']['history'],[])
 def test_rejected_prefix_is_not_returned_as_a_completed_result(self):
  m=self.model();configure(m)
  deck="&VENT TYPE='WALL' ID='MINLEAK_R' WIDTH=0.02 TOP=2 /"
  final=dict(compartments={'PRS_1':np.array([0.,140.])})
  with tempfile.TemporaryDirectory() as d,patch('pyrocast_cfbt.native._execute_once',side_effect=[PressureSizingRestart(400.,80.),final]) as run:
   result=execute('unused',Path(d),deck,'',3600,20,validation_model=m)
   self.assertIs(result,final);self.assertEqual(run.call_count,2)
   self.assertEqual(m['basement_pressure']['history'][0]['complete'],False)
   self.assertEqual(m['basement_pressure']['history'][0]['observed_until_s'],80.)
   self.assertTrue(m['basement_pressure']['passed'])
 def test_prefix_ignores_partial_record_and_checks_identity_units(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'case_compartments.csv'
   text='Time,PRS_1,PRS_2\n,,\nTime,R,Other\ns,Pa,Pa\n0,0,9999\n5,350,9999\n10,99999\n'
   p.write_text(text);self.assertEqual(pressure_prefix(p,self.model()),(350.,5.))
   p.write_text(text.replace('s,Pa,Pa','s,kPa,Pa'));self.assertIsNone(pressure_prefix(p,self.model()))
 def test_running_native_trial_is_killed_without_sealing_partial_output(self):
  from pyrocast_cfbt.native import _execute_once
  m=self.model();configure(m);clock=[0.]
  with tempfile.TemporaryDirectory() as d:
   folder=Path(d)
   class Process:
    killed=False
    def poll(self):return -1 if self.killed else None
    def kill(self):self.killed=True
    def wait(self,timeout=None):
     clock[0]+=6
   process=Process()
   def launch(*args,**kw):
    (folder/'case_compartments.csv').write_text('Time,PRS_1\n,\nTime,R\ns,Pa\n0,0\n5,350\n')
    return process
   with patch('pyrocast_cfbt.native.subprocess.Popen',side_effect=launch),patch('pyrocast_cfbt.native.time.monotonic',side_effect=lambda:clock[0]):
    with self.assertRaises(PressureSizingRestart):_execute_once(Path(__file__),folder,'&HEAD /','',3600,30,validation_model=m)
   self.assertTrue(process.killed);self.assertFalse((folder/'completed.json').exists())
 def test_bad_settings_rejected(self):
  for cfg in ({'limit_Pa':float('nan')},{'target_Pa':300},{'max_attempts':1.5},{'enabled':'yes'}):
   m=self.model();m['basement_pressure_settings']=cfg
   with self.assertRaises(ValueError):configure(m)
 def test_lite_rebuilds_input_and_keeps_final_unclipped_series(self):
  import json
  from types import SimpleNamespace
  from pyrocast_lite.adapter import prepare
  from pyrocast_lite.runner import run
  raw=json.loads((Path(__file__).resolve().parents[2]/'fixtures/room_rule_benchmark_3room_b3.json').read_text('utf8'))
  for r in raw['rooms']:r['below_grade']=True;r['leak_area_ratio']=[0,0]
  raw['openings']=[v for v in raw['openings'] if 'OUTSIDE' not in (v['a'],v['b'])]
  model,_=prepare(raw);pressures=iter([400.,140.]);widths=[]
  def once(m,*args):
   widths.append(sum(v['width_m'] for v in m.input_model['openings'] if v.get('basement_pressure_relief')))
   y=np.column_stack([m.y0(),m.y0()]);y[:m.N,1]+=next(pressures)
   m.sol=SimpleNamespace(t=np.array([0,10]),y=y,success=True);m.integration={'complete':True};return m.sol
  with patch('pyrocast_lite.runner._run_once',side_effect=once):run(model,10,budget_s=30)
  self.assertEqual(model.integration['from_zero_replays'],1);self.assertAlmostEqual(widths[1],2*widths[0])
  np.testing.assert_allclose(model.sol.y[:model.N,-1]-model.y0()[:model.N],140)

if __name__=='__main__':unittest.main()
