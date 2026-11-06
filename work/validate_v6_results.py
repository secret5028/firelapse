import pathlib,sys,json,os,subprocess,math
W=pathlib.Path(__file__).resolve().parent;CAD=pathlib.Path(r'C:\Users\<user>\Documents\Codex\2026-09-07\2\CAD3D')
sys.path[:0]=[str(W/'cad-deps'),str(CAD)]
from cad_evidence import geometry,polygon_parts,opening_parts
from fire_zone import Model
import numpy as np
env=dict(os.environ,PYTHONPATH=str(W/'cad-deps'),PYTHONIOENCODING='utf-8')
reports=[]
for out in sorted((W/'cad-v6-runs').iterdir()):
 if not out.is_dir():continue
 p=json.loads((out/'plan.json').read_text(encoding='utf8'));old=json.loads((W.parent/'outputs/CAD-벽공리-v5'/out.name/'plan.json').read_text(encoding='utf8'))
 gs={r['id']:geometry(polygon_parts(r)) for r in p['rooms']};mapping={}
 for r in old['rooms']:
  a=geometry(polygon_parts(r));best=max(gs,key=lambda id:a.intersection(gs[id]).area);mapping[r['id']]=best
 cur={o['id']:o for o in p['openings']};changed=[];new=[]
 for o in old['openings']:
  if o['connection_status'] not in ('interior','exterior'):continue
  expected=sorted(mapping.get(s,s) for s in o['sides']);n=cur.get(o['id'])
  if not n or sorted(n.get('sides',[]),key=str)!=expected:changed.append(dict(id=o['id'],previous=o['sides'],mapped=expected,now=n.get('sides') if n else None))
 prev={o['id']:o for o in old['openings']}
 for o in p['openings']:
  if o['connection_status'] in ('interior','exterior') and (o['id'] not in prev or prev[o['id']]['connection_status'] not in ('interior','exterior')):new.append(dict(id=o['id'],sides=o['sides']))
 assert not p['quality']['errors']
 subprocess.run([sys.executable,str(CAD/'cad_build3d.py'),str(out/'building'),str(out/'plan.json'),'--names',p['floor']],env=env,check=True,capture_output=True)
 b=json.loads((out/'building.json').read_text(encoding='utf8'));bf=b['floors'][0]
 assert {r['id'] for r in bf['rooms']}==set(gs)
 assert {o['id'] for o in bf['openings']}==set(cur)
 states=[0,50,100] if out.name=='office-1F' else [50];runs=[]
 for state in states:
  m=Model(b,p['floor'],dict(fire_room='R0',door_open_default=state,window_open_default=state));assert set(m.rmap)==set(gs)
  assert {v[5] for v in m.vents}=={c['id'] for c in bf['simulation_graph']['connections']}
  sol=m.run(t_end=60,dt_out=10);assert sol.success and np.isfinite(sol.y).all() and sol.t[-1]==60
  result=m.result();result.pop('flags',None);(out/f'simulation-{state}.json').write_text(json.dumps(result,ensure_ascii=False),encoding='utf8');runs.append(dict(state=state,seconds=60,solver_success=True))
 report=dict(sample=out.name,rooms_before=len(old['rooms']),rooms_after=len(p['rooms']),room_mapping=mapping,changed_existing_connections=changed,new_connections=new,excluded=p['simulation_graph']['excluded_openings'],rejected=[o['id'] for o in p['rejected_openings']],runs=runs)
 reports.append(report);print(json.dumps({k:v for k,v in report.items() if k not in ('room_mapping','runs')},ensure_ascii=False),flush=True)
(W/'cad-v6-runs/validation.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf8')
