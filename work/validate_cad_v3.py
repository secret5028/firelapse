import json,pathlib,subprocess,sys,os,time
W=pathlib.Path(__file__).resolve().parent;CAD=pathlib.Path(r'C:\Users\<user>\Documents\Codex\2026-09-07\2\CAD3D')
sys.path.insert(0,str(CAD))
from cad_evidence import geometry,polygon_parts
from shapely.geometry import box
env=dict(os.environ,PYTHONPATH=str(W/'cad-deps'),PYTHONIOENCODING='utf-8')
report=[]
for case in json.loads((W/'cad-runs/regression.json').read_text(encoding='utf-8')):
    label,floor,building=case['label'],case['floor'],case['building'];out=W/'cad-v3-runs'/f'{label}-{floor}';out.mkdir(exist_ok=True)
    args=[sys.executable,str(CAD/'cad_pipeline.py'),case['source'],str(out),'--floor',floor]
    ref=CAD/'out'/building
    if (ref/(floor+'_fire.json')).exists():args+=['--fire-json',str(ref/(floor+'_fire.json')),'--fire-reference-plan',str(ref/(floor+'.json'))]
    with (out/'run.log').open('w',encoding='utf-8') as log:result=subprocess.run(args,env=env,stdout=log,stderr=subprocess.STDOUT)
    if result.returncode:raise RuntimeError((out/'run.log').read_text(encoding='utf-8'))
    p=json.loads((out/'plan.json').read_text(encoding='utf-8'));old=json.loads((W.parent/'outputs/CAD-통합추출-v2'/f'{label}-{floor}'/'plan.json').read_text(encoding='utf-8'))
    # Compare semantic room correspondence, allowing intentional tier merges and core separation.
    mapping={r['id']:max(p['rooms'],key=lambda n:geometry(polygon_parts(r)).intersection(geometry(polygon_parts(n))).area)['id'] for r in old['rooms']}
    current={o['id']:o for o in p['openings']};lost=[]
    for o in old['openings']:
        if not o['kind'].startswith('door') or o['connection_status'] not in ('interior','exterior'):continue
        expected=[mapping.get(s,s) for s in o['sides']]
        new=current.get(o['id'])
        if not new or sorted(expected)!=sorted(new['sides'],key=lambda s:str(s)):lost.append(o['id'])
    assert not p['quality']['errors']
    assert not lost,('lost door connections',label,floor,lost)
    core_checks=[]
    for c in p['cores']:
        if c['kind']!='elev' or c.get('src')!='block':continue
        q=box(c['cx']-c['w']/2,c['cy']-c['h']/2,c['cx']+c['w']/2,c['cy']+c['h']/2)
        overlap=sum(geometry(polygon_parts(r)).intersection(q).area for r in p['rooms'] if 'elev' not in r.get('tags',[]))
        core_checks.append(round(overlap,4))
    if label=='hotel' and floor=='4F':
        assert len(core_checks)==3 and max(core_checks)<.001
        assert p['stats']['doors_elev']==3
    if label=='office' and floor=='1F':
        hall=[r for r in p['rooms'] if '다목적실' in r.get('names',[])]
        assert len(hall)==1 and hall[0]['area']>150
        assert sum(v['excluded_by_auto'] for v in p['source_vectors'])==7
    graph=p['simulation_graph'];ids={r['id'] for r in p['rooms']}|{'out'}
    assert all(len(c['sides'])==2 and all(s in ids for s in c['sides']) and c['sides'][0]!=c['sides'][1] for c in graph['connections'])
    args=[sys.executable,str(CAD/'cad_build3d.py'),str(out/'building'),str(out/'plan.json'),'--names',floor]
    subprocess.run(args,env=env,check=True,capture_output=True)
    b=json.loads((out/'building.json').read_text(encoding='utf-8'))['floors'][0]
    assert {r['id'] for r in b['rooms']}=={r['id'] for r in p['rooms']},'3D room lost'
    assert {o['id'] for o in b['openings']}=={o['id'] for o in p['openings']},'3D opening lost'
    item=dict(sample=f'{label}-{floor}',rooms_before=len(old['rooms']),rooms_after=len(p['rooms']),
        elevator_doors_before=old['stats']['doors_elev'],elevator_doors_after=p['stats']['doors_elev'],
        valid_geometry=True,existing_door_connections_preserved=True,ordinary_room_core_overlap_m2=core_checks,
        graph_connections=len(graph['connections']),excluded_graph_openings=len(graph['excluded_openings']),
        auto_checks=[c for c in p['checks'] if c['rule'].startswith('AUTO')],three_d_rooms=len(b['rooms']),
        checks_remaining=p['quality']['issues'])
    report.append(item);(W/'cad-v3-runs/validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in item.items() if k not in ('auto_checks','checks_remaining')},ensure_ascii=False),flush=True)
