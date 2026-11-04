"""Fuel quantity input integration; no solver execution and no persistent changes."""
import sys,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'simulation'),str(ROOT/'simulation/deps')]
import model_simulation as model
import lite_fuel_settings as api
from pyrocast_lite import fuel_quantity as q
from pyrocast_lite.screening_v8_approved import prepare_inputs
class FuelQuantityTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'app/tests');self.patch=patch.object(q,'DIRECTORY',Path(self.tmp.name));self.patch.start()
  self.sha=model.fingerprint('parkmarine');self.building=model.read(model.model_path(model.entry('parkmarine')))
 def tearDown(self):self.patch.stop();self.tmp.cleanup()
 def payload(self,ctx,rows):return dict(building_sha256=self.sha,revision=ctx['revision'],rooms=rows)
 def test_hotel_input_and_saved_result_isolation(self):
  before,_=model.prepared('parkmarine','5F',self.sha);ctx=api.context(self.building,self.sha)
  row=next(x for x in ctx['rooms'] if x['floor']=='5F' and x['editable']);rid=row['id']
  after=api.apply(self.payload(ctx,[dict(id=rid,multiplier=2)]),self.building,self.sha)
  self.assertFalse(after['simulation_started']);self.assertTrue(after['rerun_required'])
  raw,_=model.prepared('parkmarine','5F',self.sha)
  a=next(g for g in before['fuel_groups'] if g['room']==rid);b=next(g for g in raw['fuel_groups'] if g['room']==rid)
  self.assertEqual(b['energy_MJ'],a['energy_MJ']*2);self.assertEqual(b['hrrpua_kW_m2'],a['hrrpua_kW_m2'])
  self.assertEqual(next(r for r in raw['rooms'] if r['id']==rid)['fuel_default']['load_MJ_m2'],row['base_load']*2)
  for u in b.get('fuel_units',[]):self.assertAlmostEqual(u['energy_MJ'],b['energy_MJ']*u['budget_fraction'])
  self.assertEqual(q.load('0'*64),{})
  with self.assertRaises(ValueError):api.apply(self.payload(ctx,[dict(id=rid,multiplier=3)]),self.building,self.sha)
 def test_validation_atomic(self):
  ctx=api.context(self.building,self.sha);rid=next(r['id'] for r in ctx['rooms'] if r['editable']);core=next(r['id'] for r in ctx['rooms'] if not r['editable'])
  for value in [0,3.1,True,float('nan'),float('inf'),'2']:
   with self.assertRaises(ValueError):api.apply(self.payload(ctx,[dict(id=rid,multiplier=value)]),self.building,self.sha)
  for bad in ['unknown',core]:
   with self.assertRaises(ValueError):api.apply(self.payload(ctx,[dict(id=rid,multiplier=2),dict(id=bad,multiplier=2)]),self.building,self.sha)
  self.assertEqual(list(q.DIRECTORY.glob('*.json')),[])
 def test_approved_R2_input(self):
  raw=json.loads((ROOT/'simulation/results/room_rule_r8_20261025/source-scenario.json').read_text('utf-8'))
  before=prepare_inputs(raw);sha=raw['cad']['building_sha256'];rid='CAD_3F_R2'
  q.path_for(sha).write_text(json.dumps(dict(building_sha256=sha,rooms={rid:dict(multiplier=1.5)})),'utf-8')
  after=prepare_inputs(raw)
  a=next(g for g in before['fuel_groups'] if g['room']==rid);b=next(g for g in after['fuel_groups'] if g['room']==rid)
  self.assertEqual(b['energy_MJ'],a['energy_MJ']*1.5);self.assertEqual(b['fuel_area_m2'],a['fuel_area_m2'])
  self.assertEqual(q.load(self.sha),{})
 def test_context_matches_all_hotel_floor_inputs(self):
  ctx={r['id']:r for r in api.context(self.building,self.sha)['rooms']}
  checked=0;unavailable=[]
  for f in self.building['floors']:
   try:raw,_=model.prepared('parkmarine',f['name'],self.sha)
   except ValueError as e:
    unavailable.append((f['name'],str(e)));continue
   checked+=1
   for r in raw['rooms']:self.assertEqual(ctx[r['id']]['load'],r['fuel_default']['load_MJ_m2'],r['id'])
  self.assertGreaterEqual(checked,5)
  print('hotel input floors verified:',checked,'unavailable:',unavailable)
if __name__=='__main__':unittest.main()
