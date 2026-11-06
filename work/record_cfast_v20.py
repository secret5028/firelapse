from pathlib import Path
import json,math,hashlib
root=Path(__file__).resolve().parent.parent;out=root/'outputs/CAD-가연물기본값-v20'
j=json.loads((out/'cfast-demo.json').read_text('utf8'));preset=json.loads((root/'work/cfast_material_defaults.json').read_text('utf8'))
assert j['ignition_scenario']['defaults']==preset
assert len(j['rooms'])==156 and j['duration']==1800 and len(j['fires'])==4
assert 'NORMAL EXIT' in (out/'multifloor-execution.log').read_text().upper()
for f in j['fires'][1:]:
 assert f['criterion']=='TEMPERATURE' and f['setpoint']==300 and f['unit']=='°C'
 assert len(f['hrr'])==len(f['target_series'])==361
 assert all(q==0 for q,ign in zip(f['hrr'],f['ignited']) if not ign)
 assert all(math.isfinite(x) for row in f['target_series'] for x in row)
for r in j['rooms']:
 assert len(r['series'])==361 and all(math.isfinite(x) for v in r['series'] for x in v)
assert j['fires'][-1]['ignition_time'] is None
prefix=lambda p:p.read_text('utf8').split('// Coupled CFAST results')[0]
assert prefix(out/'model.html')==prefix(out/'before-model.html')
app=Path('C:/Users/<user>/Desktop/소방 크로키 업-로컬웹앱');job=app/'data/d018b4bb75da4475b1fd75447603c1a0/cad-output'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(job/'building.json')==j['building_sha256']
record={'status':'passed','preset_id':preset['preset_id'],'duration':1800,'engine_seconds':j['elapsed_seconds'],'events':{f['id']:f['ignition_time'] for f in j['fires']},'geometry_unchanged':True,'legacy_prefix_unchanged':True,'scope':'Default inheritance and calculation output checks; not material validation'}
(out/'검증결과.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),'utf8')
(out/'material-defaults.json').write_text(json.dumps(preset,ensure_ascii=False,indent=2),'utf8')
print(json.dumps(record,ensure_ascii=False))
