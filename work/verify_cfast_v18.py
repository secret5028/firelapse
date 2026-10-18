"""Check data consistency and preserve the CAD/legacy baseline; not physics validation."""
from pathlib import Path
import hashlib,json,math
root=Path(__file__).resolve().parent.parent
out=root/'outputs/CAD-30분-실감보기-v18'
data=json.loads((out/'cfast-demo.json').read_text('utf8'))
old=json.loads((out/'before-cfast-demo.json').read_text('utf8'))
assert data['duration']==1800 and data['step']==5
assert len(data['rooms'])==156 and data['solver_compartments']==100
assert len(data['vertical_connections'])==36
assert data['solver_members']==old['solver_members']
max_delta=0
previous={r['key']:r for r in old['rooms']}
for r in data['rooms']:
 assert len(r['series'])==361 and r['series'][0][0]==0 and r['series'][-1][0]==1800
 for row in r['series']:
  assert all(math.isfinite(x) for x in row)
  assert 0<=row[3]<=r['height']+.001
 for a,b in zip(r['series'],previous[r['key']]['series']):
  max_delta=max(max_delta,max(abs(x-y) for x,y in zip(a,b)))
assert max_delta<.01, max_delta
assert len(data['hrr'])==len(data['flame_height'])==361
assert 'Normal exit from CFAST' in (out/'multifloor-execution.log').read_text('utf8')
summary={'threshold_od_per_m':.001,'meaning':'Display threshold only, not a hazard criterion. Five-second samples; grouped rooms share results.','floors':{}}
for floor in data['floors']:
 rr=[r for r in data['rooms'] if r['floor']==floor]
 arrival={r['key']:next((v[0] for v in r['series'] if max(v[4:6])>=.001),None) for r in rr}
 values=[x for x in arrival.values() if x is not None]
 summary['floors'][floor]={'first_display_seconds':min(values) if values else None,'rooms':arrival,'at_minutes':{}}
 for minute in [5,10,20,30]:
  hits=[{'key':r['key'],'name':r['name'],'upper_od':r['series'][minute*12][4],'lower_od':r['series'][minute*12][5]} for r in rr if max(r['series'][minute*12][4:6])>=.001]
  summary['floors'][floor]['at_minutes'][minute]={'count':len(hits),'rooms':hits}
(out/'spread-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),'utf8')
app=Path('C:/Users/예방/Desktop/소방 크로키 업-로컬웹앱')
dest=app/'data/d018b4bb75da4475b1fd75447603c1a0/cad-output'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(dest/'building.json')==data['building_sha256']
assert sha(dest/'model.html')==sha(out/'model.html')==sha(app/'_internal/cad_engine/integrated_viewer.html')
assert sha(dest/'cfast-demo.json')==sha(out/'cfast-demo.json')
prefix=lambda p:p.read_text('utf8').split('// Coupled CFAST results')[0]
assert prefix(out/'before-model.html')==prefix(out/'model.html')
record={'status':'passed','duration':1800,'samples_per_room':361,'normal_exit':True,'elapsed_seconds':data['elapsed_seconds'],'building_unchanged':True,'legacy_prefix_unchanged':True,'first_600_seconds_max_difference':max_delta,'solver_compartments':100,'display_rooms':156,'vertical_connections':36,'scope':'Data/installation regression only, not physical validation'}
(out/'검증결과.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),'utf8')
print(json.dumps({k:{'first':v['first_display_seconds'],'counts':{m:x['count'] for m,x in v['at_minutes'].items()}} for k,v in summary['floors'].items()},ensure_ascii=False))
print(record)
