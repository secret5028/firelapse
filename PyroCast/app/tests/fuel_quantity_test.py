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
  if not (ROOT/'simulation/results/room_rule_r8_20261025/source-scenario.json').exists(): self.skipTest('SKIP: evidence folder missing')
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
 def test_floor_room_inheritance_and_type(self):
  ctx=api.context(self.building,self.sha);rows=[r for r in ctx['rooms'] if r['floor']=='5F' and r['editable']];a,b=rows[:2]
  ctx=api.apply(self.payload(ctx,[dict(id=a['id'],multiplier=1,usage_class='warehouse')]),self.building,self.sha)
  ctx=api.apply(dict(building_sha256=self.sha,revision=ctx['revision'],floors=[dict(id='5F',multiplier=2,usage_class='office')]),self.building,self.sha)
  byid={r['id']:r for r in ctx['rooms']};self.assertEqual(byid[a['id']]['usage_class'],'warehouse');self.assertEqual(byid[a['id']]['multiplier'],1)
  self.assertEqual(byid[b['id']]['usage_class'],'office');self.assertEqual(byid[b['id']]['multiplier'],2)
  raw,_=model.prepared('parkmarine','5F',self.sha)
  for rid in (a['id'],b['id']):
   g=next(g for g in raw['fuel_groups'] if g['room']==rid)
   area=next(r['area_m2'] for r in raw['rooms'] if r['id']==rid)
   self.assertEqual(g['hrrpua_kW_m2'],byid[rid]['hrrpua']);self.assertAlmostEqual(g['energy_MJ'],byid[rid]['load']*area,places=2)
  ctx=api.apply(self.payload(ctx,[dict(id=a['id'],inherit=True)]),self.building,self.sha)
  r=next(r for r in ctx['rooms'] if r['id']==a['id']);self.assertEqual(r['scope'],'floor');self.assertEqual(r['multiplier'],2);self.assertEqual(r['usage_class'],'office')
 def test_real_ai_path_mock_transport_and_protection(self):
  import lite_ai_fuel
  ctx=api.context(self.building,self.sha);a=next(r for r in ctx['rooms'] if r['floor']=='5F' and r['editable'])
  ctx=api.apply(self.payload(ctx,[dict(id=a['id'],usage_class='office',multiplier=1)]),self.building,self.sha)
  calls=[]
  def transport(cfg,key,messages):
   facts=json.loads(messages[0]['content'].split('\n',1)[1]);calls.append(facts)
   self.assertTrue(all('position_m' in r and 'neighbors' in r for r in facts['surrounding_rooms']))
   return json.dumps([dict(room_id=r['id'],usage_class='hotel_room',reason='층 용도·위치 기준 추정') for r in facts['rooms']])
  with patch.object(lite_ai_fuel,'settings',return_value=dict(base_url='https://example.invalid',model='test',api_key_env='FUEL_TEST_KEY')),patch.dict('os.environ',{'FUEL_TEST_KEY':'dummy-test-secret'}):
   ctx=api.initialize_defaults(dict(revision=ctx['revision']),self.building,self.sha,transport)
  self.assertGreater(len(calls),1);self.assertEqual(len(ctx['ai_pending']),0)
  saved=q.load(self.sha);self.assertNotIn(a['id'],saved['defaults']);self.assertEqual(saved['rooms'][a['id']]['usage_class'],'office')
  self.assertNotIn('dummy-test-secret',q.path_for(self.sha).read_text('utf-8'));self.assertFalse(ctx['simulation_started'])
 def test_missing_ai_does_not_invent_defaults(self):
  import lite_ai_fuel
  with patch.object(lite_ai_fuel,'settings',return_value=None):
   ctx=api.context(self.building,self.sha);self.assertIn('AI 초기 배치 대기',ctx['default_status'])
   with self.assertRaisesRegex(ValueError,'AI 초기 배치 대기'):api.initialize_defaults(dict(revision=ctx['revision']),self.building,self.sha)
  self.assertEqual(q.load(self.sha),{})
 def test_search_is_read_only_and_uses_catalog_numbers(self):
  import lite_ai_fuel as ai
  with patch.object(ai,'settings',return_value=dict(base_url='https://example.invalid',model='test',api_key_env='FUEL_TEST_KEY')),patch.dict('os.environ',{'FUEL_TEST_KEY':'test-token'}):
   ctx=api.context(self.building,self.sha);body=dict(building_sha256=self.sha,revision=ctx['revision'],search='목재 가구')
   result=api.search_classes(body,self.building,self.sha,lambda *args:json.dumps([dict(usage_class='office',reason='사무실 용도 기준으로 대체하는 추정')]))
   self.assertEqual(result['suggestions'][0]['mean'],ctx['classes']['office']['mean']);self.assertFalse(result['saved']);self.assertEqual(q.load(self.sha),{})
   with self.assertRaisesRegex(ValueError,'검증 실패'):
    api.search_classes(body,self.building,self.sha,lambda *args:'[{"usage_class":"invented","reason":"test"}]')
   self.assertEqual(q.load(self.sha),{})
 def test_quantity_only_override_still_gets_ai_default(self):
  import lite_ai_fuel as ai
  ctx=api.context(self.building,self.sha);r=next(r for r in ctx['rooms'] if r['editable'])
  ctx=api.apply(self.payload(ctx,[dict(id=r['id'],multiplier=1.7)]),self.building,self.sha)
  self.assertIn(r['id'],ctx['ai_pending'])
  with patch.object(ai,'settings',return_value=dict(base_url='https://example.invalid',model='test',api_key_env='FUEL_TEST_KEY')),patch.dict('os.environ',{'FUEL_TEST_KEY':'test-token'}):
   def reply(*args):
    facts=json.loads(args[-1][0]['content'].split('\n',1)[1]);return json.dumps([dict(room_id=r['id'],usage_class='office',reason='시험용 추정') for r in facts['rooms']])
   ctx=api.initialize_defaults(dict(revision=ctx['revision']),self.building,self.sha,reply)
  row=next(x for x in ctx['rooms'] if x['id']==r['id']);self.assertEqual(row['multiplier'],1.7);self.assertEqual(row['usage_class'],'office')
 def test_rank_refresh_after_fuel_save(self):
  _,before=model.prepared('parkmarine','5F',self.sha);ctx=api.context(self.building,self.sha)
  row=before['ranked'][-1];rid=row['room']
  api.apply(self.payload(ctx,[dict(id=rid,usage_class='library',multiplier=3)]),self.building,self.sha)
  _,after=model.prepared('parkmarine','5F',self.sha)
  new=next(r for r in after['ranked'] if r['room']==rid)
  self.assertNotEqual(row['score'],new['score']);self.assertNotEqual(row['rank1'],new['rank1'])
  print('rank linkage:',rid,'score',row['score'],'->',new['score'],'rank',row['rank1'],'->',new['rank1'])
 def test_unsaved_rank_preview_is_read_only(self):
  ctx=api.context(self.building,self.sha);rid='CAD_5F_R19'
  _,baseline=model.prepared('parkmarine','5F',self.sha)
  before=next(r for r in baseline['ranked'] if r['room']==rid)
  for amount,rank in [(1.5,5),(2,1)]:
   payload={**self.payload(ctx,[dict(id=rid,multiplier=amount)]),'preview_floor':'5F'}
   preview=api.apply(payload,self.building,self.sha);row=next(r for r in preview['score']['ranked'] if r['room']==rid)
   self.assertEqual(row['rank1'],rank);self.assertGreater(row['fuel_energy_MJ'],before['fuel_energy_MJ'])
   self.assertFalse(preview['saved']);self.assertFalse(preview['simulation_started']);self.assertEqual(q.load(self.sha),{})
   self.assertEqual(list(q.DIRECTORY.glob('*')),[])
  _,unchanged=model.prepared('parkmarine','5F',self.sha)
  self.assertEqual(next(r for r in unchanged['ranked'] if r['room']==rid)['score'],before['score'])
 def test_approved_preview_does_not_persist(self):
  if not (ROOT/'simulation/results/room_rule_r8_20261025/source-scenario.json').exists(): self.skipTest('SKIP: evidence folder missing')
  raw=json.loads((ROOT/'simulation/results/room_rule_r8_20261025/source-scenario.json').read_text('utf-8'))
  before=prepare_inputs(raw);sha=raw['cad']['building_sha256'];rid='CAD_3F_R2'
  after=prepare_inputs(raw,{'rooms':{rid:{'multiplier':2}}})
  self.assertEqual(next(g['energy_MJ'] for g in after['fuel_groups'] if g['room']==rid),2*next(g['energy_MJ'] for g in before['fuel_groups'] if g['room']==rid))
  self.assertEqual(q.load(sha),{})
 def test_ai_transport_formats_and_invalid_response_atomic(self):
  import lite_ai_fuel as ai
  from unittest.mock import MagicMock
  for base,native in [('https://api.anthropic.com/v1',True),('http://127.0.0.1:8000/v1',False)]:
   reply={'content':[{'type':'text','text':'[]'}]} if native else {'choices':[{'message':{'content':'[]'}}]}
   response=MagicMock();response.__enter__.return_value.read.return_value=json.dumps(reply).encode();opener=MagicMock();opener.open.return_value=response
   with patch.object(ai,'build_opener',return_value=opener):
    self.assertEqual(ai.completion(dict(base_url=base,model='fixture'),'test-token',[{'role':'system','content':'rules'},{'role':'user','content':'request'}]),'[]')
   req=opener.open.call_args.args[0];body=json.loads(req.data);self.assertTrue(req.full_url.endswith('/messages' if native else '/chat/completions'))
   self.assertEqual('system' in body,native);self.assertNotIn('test-token',req.data.decode())
  calls=[]
  def invalid(*args):calls.append(1);return '[]'
  with patch.object(ai,'settings',return_value=dict(base_url='https://example.invalid',model='test',api_key_env='FUEL_TEST_KEY')),patch.dict('os.environ',{'FUEL_TEST_KEY':'test-token'}):
   ctx=api.context(self.building,self.sha)
   with self.assertRaisesRegex(ValueError,'검증 실패'):api.initialize_defaults(dict(revision=ctx['revision']),self.building,self.sha,invalid)
  self.assertEqual(len(calls),2);self.assertEqual(q.load(self.sha),{})
if __name__=='__main__':unittest.main()
