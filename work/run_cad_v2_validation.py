import os, sys, json, pathlib, subprocess, time
W=pathlib.Path(__file__).resolve().parent
CAD=pathlib.Path(r'C:\Users\<user>\Documents\Codex\2026-09-07\2\CAD3D')
env=dict(os.environ,PYTHONPATH=str(W/'cad-deps'),PYTHONIOENCODING='utf-8')
report=[]
for old in json.loads((W/'cad-runs/regression.json').read_text(encoding='utf-8')):
    label,floor,building=old['label'],old['floor'],old['building']
    output=W/'cad-v2-runs'/f'{label}-{floor}'
    args=[sys.executable,str(CAD/'cad_pipeline.py'),old['source'],str(output),'--floor',floor]
    ref=CAD/'out'/building
    if (ref/(floor+'_fire.json')).exists():
        args+=['--fire-json',str(ref/(floor+'_fire.json')),'--fire-reference-plan',str(ref/(floor+'.json'))]
    start=time.monotonic()
    output.mkdir(parents=True,exist_ok=True)
    with (output/'run.log').open('w',encoding='utf-8') as log:
        proc=subprocess.run(args,env=env,stdout=log,stderr=subprocess.STDOUT)
    if not (output/'plan.json').exists():
        print((output/'run.log').read_text(encoding='utf-8'),flush=True)
        raise RuntimeError(f'{label} {floor} failed')
    plan=json.loads((output/'plan.json').read_text(encoding='utf-8'))
    connections={o['id']:o['sides'] for o in plan['openings'] if o['kind'] in ('door','door_elev','door_internal')}
    swings={o['id']:[l['sgn'] for l in o.get('leaves',[])] for o in plan['openings'] if o.get('leaves')}
    checks=dict(room_count_preserved=old['after']['stats']['rooms']==len(plan['rooms']),
        existing_door_connections_preserved=all(connections.get(k)==v for k,v in old['after']['door_connections'].items()),
        swing_directions_preserved=old['after']['swings']==swings,valid_geometry=not plan['quality']['errors'])
    item=dict(sample=f'{label}-{floor}',building=building,seconds=round(time.monotonic()-start,2),exit_code=proc.returncode,
        checks=checks,stats=plan['stats'],quality=plan['quality'],
        source_vectors=len(plan['source_vectors']),fire_symbols=len(plan.get('fire',{}).get('symbols',[])),
        fire_alignment_verified=plan.get('fire',{}).get('alignment_verified'),
        changed_openings=[dict(id=o['id'],before=o['kind_before_fire'],after=o['kind']) for o in plan['openings'] if o.get('kind_before_fire')])
    report.append(item)
    (W/'cad-v2-runs/validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in item.items() if k in ('sample','seconds','checks','fire_symbols','changed_openings')},ensure_ascii=False),flush=True)
    if proc.returncode not in (0,2): raise RuntimeError((output/'run.log').read_text(encoding='utf-8'))
