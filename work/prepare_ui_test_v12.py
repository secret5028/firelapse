from pathlib import Path
import sys,json,shutil,re,sqlite3
root=Path(__file__).resolve().parent.parent;engine=root/'work/cad-web/cad_engine'
sys.path.insert(0,str(engine));sys.path.insert(0,str(root/'work/cad-deps'))
from cad_model_transport import prepare_model
home=Path('C:/Users/<user>/Desktop/소방 크로키 업-로컬웹앱/data');test=root/'work/cad-ui-test-data';test.mkdir(exist_ok=True)
with sqlite3.connect(home/'history.sqlite') as src,sqlite3.connect(test/'history.sqlite') as dst:src.backup(dst)
job='d018b4bb75da4475b1fd75447603c1a0';folder=test/job;folder.mkdir(exist_ok=True)
for name in ['files.json','result.html']:shutil.copy2(home/job/name,folder/name)
out=folder/'cad-output';out.mkdir(exist_ok=True)
for name in ['index.html','plans.html','summary.json']:shutil.copy2(home/job/'cad-output'/name,out/name)
b=json.loads((home/job/'cad-output/building.json').read_text('utf8'))
plans={f['name']:json.loads((home/job/'cad-output'/f['name']/'plan.json').read_text('utf8')) for f in b['floors']}
model,audit=prepare_model(b,plans)
(out/'building.json').write_text(json.dumps(model,ensure_ascii=False),'utf8')
shutil.copy2(engine/'integrated_viewer.html',out/'model.html')
script=re.findall(r'<script type="module">([\s\S]*?)</script>',(out/'model.html').read_text('utf8'))[0]
(root/'work/cad-v12-check.mjs').write_text(script,'utf8')
deliver=root/'outputs/CAD-인터페이스복원-v12'
shutil.copy2(out/'building.json',deliver/'building.json')
ramps=[dict(floor=f['name'],to=r.get('to_floor'),span=r.get('span_degrees'),rise=r.get('rise_m'),slope=r.get('slope_percent'),length=r['length_m']) for f in model['floors'] for r in f['model_ramps']]
report=dict(floors=len(model['floors']),stairs_elevator_connections=len(model['vertical_connections']),ramps=ramps,structural_tops=[{k:v for k,v in t.items() if k!='roof_polys'} for t in model['structural_tops']])
(deliver/'모델수정검사.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(json.dumps(ramps))
