import pathlib,sys,json,os,subprocess,hashlib,math
W=pathlib.Path(__file__).resolve().parent;CAD=pathlib.Path(r'C:\Users\예방\Documents\Codex\2026-09-07\2\CAD3D');sys.path[:0]=[str(W/'cad-deps'),str(CAD)]
from cad_evidence import geometry,polygon_parts
from fire_zone import Model
from compare_v7 import compare
import numpy as np
env=dict(os.environ,PYTHONPATH=str(W/'cad-deps'),PYTHONIOENCODING='utf-8')
floors=['B1']+[f'{i}F' for i in range(1,8)]+['PH'];root=W/'cad-v7-runs';reports=[]
levels=[-4.2,.9,6.4,11.9,17.4,21.9,26.4,30.9,36.6,39.9]
for floor in floors:
 out=root/('office-'+floor);p=json.loads((out/'plan.json').read_text(encoding='utf8'))
 for group in ('code_sha256','evidence_code_sha256'):
  assert all(hashlib.sha256((CAD/f).read_bytes()).hexdigest()==sha for f,sha in p['provenance'][group].items()),floor+' stale code'
 assert p['quality']['errors']==0
 assert p['source_coverage']['primary']['floor']==floor
 assert len(p['source_vectors'])==p['layer_evidence']['input_primitives']+p['layer_evidence']['derived_wall_pieces']
 idx=floors.index(floor)
 subprocess.run([sys.executable,str(CAD/'cad_build3d.py'),str(out/'building'),str(out/'plan.json'),'--names',floor,'--levels='+','.join(map(str,levels[idx:idx+2]))],env=env,check=True,capture_output=True)
 b=json.loads((out/'building.json').read_text(encoding='utf8'));bf=b['floors'][0]
 assert {r['id'] for r in p['rooms']}=={r['id'] for r in bf['rooms']}
 assert {o['id'] for o in p['openings']}=={o['id'] for o in bf['openings']}
 runs=[]
 for state in (0,50,100):
  m=Model(b,floor,dict(fire_room=max(bf['rooms'],key=lambda r:r['area'])['id'],door_open_default=state,window_open_default=state))
  assert set(m.rmap)=={r['id'] for r in bf['rooms']}
  assert {v[5] for v in m.vents}=={c['id'] for c in bf['simulation_graph']['connections']}
  sol=m.run(t_end=60,dt_out=10);assert sol.success and np.isfinite(sol.y).all() and sol.t[-1]==60
  result=m.result();result.pop('flags',None);(out/f'simulation-{state}.json').write_text(json.dumps(result,ensure_ascii=False),encoding='utf8')
  runs.append(dict(state=state,seconds=60,solver_success=True))
 row=dict(floor=floor,rooms=len(p['rooms']),openings=len(p['openings']),connections=len(p['simulation_graph']['connections']),uncertain=p['simulation_graph']['excluded_openings'],
          isolated_rooms=p['simulation_graph']['isolated_rooms'],scanned_layers=len(p['layer_evidence']['scanned_layers']),vectors=len(p['source_vectors']),
          accepted_cross_layer=len(p['layer_evidence']['accepted']),wall_room_overlap_m2=round(sum(geometry(polygon_parts(r)).intersection(geometry(p['walls'])).area for r in p['rooms']),7),
          wall_room_repairs=[c for c in p['checks'] if c['rule']=='Q벽실분리'],quality_errors=p['quality']['errors'],runs=runs)
 old=W.parent/'outputs/CAD-문판정-v6'/out.name/'plan.json'
 if old.exists():row['comparison_v6']=compare(json.loads(old.read_text(encoding='utf8')),p)
 reports.append(row);print(floor,'validated',row['rooms'],len(row['uncertain']),'overlap',row['wall_room_overlap_m2'],flush=True)
levels=[-4.2,.9,6.4,11.9,17.4,21.9,26.4,30.9,36.6,39.9]
subprocess.run([sys.executable,str(CAD/'cad_build3d.py'),str(root/'building')]+[str(root/('office-'+f)/'plan.json') for f in floors]+['--names',','.join(floors),'--levels='+','.join(map(str,levels))],env=env,check=True)
b=json.loads((root/'building.json').read_text(encoding='utf8'));assert len(b['floors'])==9
assert all(len(f['rooms'])==r['rooms'] and len(f['openings'])==r['openings'] for f,r in zip(b['floors'],reports))
reg=[]
for out in (W/'cad-v7-regression').iterdir():
 if not out.is_dir():continue
 p=json.loads((out/'plan.json').read_text(encoding='utf8'));old=json.loads((W.parent/'outputs/CAD-문판정-v6'/out.name/'plan.json').read_text(encoding='utf8'))
 assert not p['quality']['errors'];comp=compare(old,p);assert not comp['changed'],comp
 reg.append(dict(sample=out.name,**comp,quality_errors=p['quality']['errors']))
record=dict(unit_tests_passed=67,floors=reports,regression=reg,levels_m=levels,
 height_note='B1 GL -4,200: 기존 추정 -2,900 교정. 7F는 층별 LEVEL/SL의 +30,900 채택; 별도 FL +31,500 및 +32,200 단차는 이번 단일 층 모델에 미반영. 천장 높이는 용도 기본값.',
 combined_alignment=[dict(floor=f['name'],align=f['align'],shift=f['shift'],scale=f['scale']) for f in b['floors']],
 browser_click_test='not_run_local_file_access_restricted',solver_scope='prototype execution sanity only; not validated fire physics')
(root/'validation.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf8')
