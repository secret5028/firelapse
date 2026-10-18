from pathlib import Path
import json,sys,math,hashlib,urllib.request,urllib.error
root=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(root/'work/cad-deps'))
from shapely.geometry import Polygon
from shapely.ops import unary_union
job='d018b4bb75da4475b1fd75447603c1a0';folder=root/'work/cad-ui-test-data'/job
b=json.loads((folder/'cad-output/building.json').read_text('utf8'))
old=json.loads(Path('C:/Users/예방/Desktop/소방 크로키 업-로컬웹앱/data',job,'cad-output/building.json').read_text('utf8'))
checks=[]
for f,o in zip(b['floors'],old['floors']):
 assert f['openings']==o['openings'] and f['bands']==o['bands'] and f['transport']==o['transport']
 assert [r['polys'] for r in f['rooms']]==[r['polys'] for r in o['rooms']]
checks.append('approved extraction, openings, walls and stair/elevator positions unchanged')
assert b['vertical_connections']==old['vertical_connections'];assert len(b['movement_connections'])==36
r=b['floors'][0]['model_ramps'][0];assert r['span_degrees']==180 and r['rise_m']==5.1
assert math.isclose(r['length_m']*r['slope_percent']/100,5.1)
assert r['to_floor']=='1F' and len(r['inner'])==len(r['outer'])==121
checks.append('reviewed B1 to 1F half-turn ramp: 180 degrees, 5.10 m rise, 17.088 percent centerline slope')
poly=lambda ps:unary_union([Polygon(p['o'],p['h']) for p in ps])
ph=b['floors'][-1];lower=b['floors'][-2];top=b['structural_tops'][-2]
assert abs(poly(top['roof_polys']).union(poly(ph['slab'])).area-poly(lower['slab']).union(poly(ph['slab'])).area)<1e-6
assert math.isclose(top['z'],ph['z'],abs_tol=1e-9) and math.isclose(ph['z'],lower['z']+lower['h'],abs_tol=1e-9)
assert all(poly(t['ceiling_polys']).is_valid for t in b['structural_tops'])
checks.append('7F structural ceiling/PH roof-floor coverage and elevation agree; suspended ceiling remains separate')
def api(path,value=None):
 data=json.dumps(value).encode() if value is not None else None
 with urllib.request.urlopen('http://127.0.0.1:8883'+path,data=data,timeout=20) as response:return json.load(response)
ctx=api('/cad-result/'+job+'/legacy-context.json');assert ctx['jobId']==job
assert ctx['state']['operations']['vehicles'] and ctx['state']['operations']['routes'] and ctx['state']['operations']['people']
try:api('/api/jobs/'+job+'/cad-state',{'version':1,'jobId':'wrong','operations':{}});raise AssertionError('wrong job accepted')
except urllib.error.HTTPError as e:assert e.code==400
checks.append('browser-created operations persisted on server; cross-job state rejected')
manifest=json.loads((folder/'files.json').read_text('utf8'));digest=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()
f1=b['floors'][1];x,y=f1['rooms'][0]['c'];z=f1['z']-b['floors'][1]['z']
net=dict(version=1,buildingId=digest,name='검증용 계통 · 실제 설비 아님',reviewed=False,inlet='test-A',active=[],nodes=[
 dict(id='test-A',type='inlet',name='검증 송수구 A',x=x-3,y=z+1,z=-y,floor=1),
 dict(id='test-head-A',type='outlet',name='검증 말단 A',x=x+3,y=z+3,z=-y,floor=1),
 dict(id='test-B',type='inlet',name='검증 송수구 B',x=x-3,y=z+1,z=-y-4,floor=1),
 dict(id='test-head-B',type='outlet',name='검증 말단 B',x=x+3,y=z+8.5,z=-y-4,floor=2)],pipes=[
 dict(id='test-pipe-A',**{'from':'test-A','to':'test-head-A'},state='open',direction='both',system='sprinkler'),
 dict(id='test-pipe-B',**{'from':'test-B','to':'test-head-B'},state='open',direction='both',system='waterSpray')])
(folder/'hydraulics.json').write_text(json.dumps(net,ensure_ascii=False),'utf8')
report=dict(status='passed',checks=checks,fixture='hydraulics test data is isolated in work/cad-ui-test-data; never deployed')
(root/'outputs/CAD-인터페이스복원-v12/검증결과.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(json.dumps(report))
