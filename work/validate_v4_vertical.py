import pathlib,subprocess,sys,json,shutil,os
W=pathlib.Path(__file__).resolve().parent
CAD=pathlib.Path(r'C:\Users\예방\Documents\Codex\2026-09-07\2\CAD3D')
sys.path[:0]=[str(W/'cad-deps'),str(CAD)]
from fire_zone import Model
import numpy as np
source=next((CAD.parent/'도면수집/28-200-2018-00000088').glob('A-308*.dwg'))
inputs=W/'cad-input';shutil.copy2(source,inputs/'hotel-5F.dwg')
exe=CAD.parent/'tmp/two-stage-src/local-resources/cad-tools/dwg2dxf.exe'
with (inputs/'hotel-5F-conversion.log').open('w') as log:
    subprocess.run([str(exe),'-y','-o','hotel-5F.dxf','hotel-5F.dwg'],cwd=inputs,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
out=W/'cad-v4-runs/hotel-5F';out.mkdir(parents=True,exist_ok=True)
env=dict(os.environ,PYTHONPATH=str(W/'cad-deps'),PYTHONIOENCODING='utf-8')
ref=CAD/'out/28-200-2018-00000088'
with (out/'run.log').open('w',encoding='utf8') as log:
    subprocess.run([sys.executable,str(CAD/'cad_pipeline.py'),str(inputs/'hotel-5F.dxf'),str(out),'--floor','5F',
        '--fire-json',str(ref/'5F_fire.json'),'--fire-reference-plan',str(ref/'5F.json')],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
multi=W/'cad-v4-runs/hotel-4F-5F';multi.mkdir(exist_ok=True)
with (multi/'build.log').open('w',encoding='utf8') as log:
    subprocess.run([sys.executable,str(CAD/'cad_build3d.py'),str(multi/'building'),str(W/'cad-v4-runs/hotel-4F/plan.json'),str(out/'plan.json'),'--names','4F,5F'],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
b=json.loads((multi/'building.json').read_text(encoding='utf8'))
assert len(b['shafts'])>=3,b['unconfirmed_vertical_cores']
report=dict(shafts=b['shafts'],unconfirmed=b['unconfirmed_vertical_cores'],levels_source='floor_defaults',floors=[])
for floor in b['floors']:
    m=Model(b,floor['name'],dict(fire_room='R0',door_open_default=50,window_open_default=0))
    assert set(m.rmap)=={r['id'] for r in floor['rooms']}
    for shaft in b['shafts']:
        rid=shaft['room_ids'][floor['name']]
        assert m.nodes[m.rmap[rid]]['kind']==shaft['kind']
        assert not any(n['id']==rid for n in m.nodes),'Duplicate shaft room'
    assert not any(v[5].startswith('EL') for v in m.vents),'Invented nearest room link'
    sol=m.run(t_end=30,dt_out=10)
    assert sol.success and np.isfinite(sol.y).all()
    result=m.result();result.pop('flags')
    (multi/(floor['name']+'-simulation.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    report['floors'].append(dict(floor=floor['name'],mapped_rooms=len(m.rmap),solver_nodes=m.N,solver_success=True,seconds=30))
(multi/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(report,ensure_ascii=False),flush=True)
