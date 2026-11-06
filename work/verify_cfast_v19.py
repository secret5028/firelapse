"""Conditional-ignition data checks, not physical validation of example materials."""
from pathlib import Path
import json,hashlib,math
root=Path(__file__).resolve().parent.parent;out=root/'outputs/CAD-2차착화-v19'
j=json.loads((out/'cfast-demo.json').read_text('utf8'))
ref=json.loads((out/'no-ignition-reference/cfast-demo.json').read_text('utf8'))
assert j['duration']==1800 and len(j['rooms'])==156 and j['solver_compartments']==100
assert len(j['vertical_connections'])==36 and len(j['fires'])==4
assert 'NORMAL EXIT' in (out/'multifloor-execution.log').read_text().upper()
for r in j['rooms']:
 assert len(r['series'])==361 and r['series'][-1][0]==1800
 assert all(math.isfinite(x) for row in r['series'] for x in row)
 assert all(0<=v[3]<=r['height']+.01 for v in r['series'])
events=[]
for f in j['fires']:
 assert len(f['hrr'])==len(f['ignited'])==len(f['flame_height'])==361
 assert all(math.isfinite(x) for a in ['hrr','flame_height'] for x in f[a])
 assert all(q==0 for q,ign in zip(f['hrr'],f['ignited']) if not ign)
 if f['id']=='ExampleFire':continue
 assert len(f['target_series'])==361
 field=1 if f['criterion']=='TEMPERATURE' else 2
 if f['ignition_time'] is not None:
  i=int(f['ignition_time']/5);assert f['ignited'][i]==1 and not any(f['ignited'][:i])
  assert max(row[field] for row in f['target_series'][:i+1])>=f['setpoint']*.99
  assert max(f['hrr'])>0 and f['hrr'][-1]==0,'Finite secondary fuel curve should finish within this case'
 else:assert not any(f['ignited']) and max(f['hrr'])==0
 events.append({'id':f['id'],'criterion':f['criterion'],'setpoint':f['setpoint'],'unit':f['unit'],'first_ignition_sample':f['ignition_time'],'max_target_value':max(v[field] for v in f['target_series']),'peak_hrr_kW':max(f['hrr'])})
assert any(f['ignition_time'] is not None for f in j['fires'][1:])
assert j['fires'][-1]['ignition_time'] is None
assert all(f['ignition_time'] is None for f in ref['fires'][1:])
for i,q in enumerate(j['total_hrr']):assert abs(q-sum(f['hrr'][i] for f in j['fires']))<.001
assert max(j['total_hrr'])>max(ref['total_hrr'])
r=next(r for r in j['rooms'] if r['key']==j['fire_key']);r0=next(r for r in ref['rooms'] if r['key']==j['fire_key'])
assert max(v[1] for v in r['series'])>max(v[1] for v in r0['series'])
app=Path('C:/Users/<user>/Desktop/소방 크로키 업-로컬웹앱');dest=app/'data/d018b4bb75da4475b1fd75447603c1a0/cad-output'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(dest/'building.json')==j['building_sha256']
prefix=lambda p:p.read_text('utf8').split('// Coupled CFAST results')[0]
assert prefix(out/'before-model.html')==prefix(out/'model.html')
code=(root/'work/cad_cfast_multifloor_overlay.js').read_text('utf8')
assert 'cutaway' not in code and 'clippingPlanes=[' not in code and 'cfCut' not in code
record={'status':'passed','duration':1800,'engine_seconds':j['elapsed_seconds'],'events':events,'peak_total_hrr_kW':max(j['total_hrr']),'peak_fire_room_upper_C':max(v[1] for v in r['series']),'no_ignition_reference_peak_upper_C':max(v[1] for v in r0['series']),'geometry_unchanged':True,'legacy_prefix_unchanged':True,'automatic_wall_cut_removed':True,'scope':'Conditional ignition/energy feedback/data range/geometry checks; not physical validation'}
(out/'검증결과.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),'utf8');print(json.dumps(record,ensure_ascii=False))
