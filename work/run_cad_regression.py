import sys, os, json, pathlib, subprocess, time, hashlib

WORK = pathlib.Path(__file__).resolve().parent
CAD = pathlib.Path(r'C:\Users\예방\Documents\Codex\2026-09-07\2\CAD3D')
env = dict(os.environ, PYTHONPATH=str(WORK/'cad-deps'), PYTHONIOENCODING='utf-8')
specs = [('hotel', '28-200-2018-00000088', '4F'),
         ('hotel', '28-200-2018-00000088', '1F'),
         ('office', '28-200-2026-00000010', '1F'),
         ('office', '28-200-2026-00000010', '4F'),
         ('exhibition', '28-710-2025-00000016', '1F')]
report = []
for label, building, floor in specs:
    original = json.loads((CAD/'out'/building/(floor+'.json')).read_text(encoding='utf-8'))
    dxf = WORK/'cad-input'/f'{label}-{floor}.dxf' if label == 'hotel' else CAD/'out'/building/'dxf'/original['src']
    record = dict(building=building, floor=floor, label=label, source=str(dxf),
                  source_sha256=hashlib.sha256(dxf.read_bytes()).hexdigest())
    for version, folder in [('before', WORK/'cad-baseline'), ('after', CAD)]:
        output = WORK/'cad-runs'/f'{label}-{floor}-{version}'
        if label != 'hotel' or floor != '4F':
            started = time.monotonic()
            with output.with_suffix('.log').open('w',encoding='utf-8') as log:
                subprocess.run([sys.executable,str(folder/'cad_plan.py'),str(dxf),str(output),
                                '--map',str(folder/'layer_map.json')], env=env, check=True,
                               stdout=log, stderr=subprocess.STDOUT)
            print(f'{label} {floor} {version}: {time.monotonic()-started:.1f}s', flush=True)
        plan = json.loads(output.with_suffix('.json').read_text(encoding='utf-8'))
        record[version] = dict(stats=plan['stats'], holes=sum(len(p.get('h',[])) for r in plan['rooms'] for p in r.get('polys',[])),
            checks=dict(__import__('collections').Counter(c['rule'] for c in plan['checks'])),
            room_ids=[r['id'] for r in plan['rooms']],
            door_connections={o['id']:o['sides'] for o in plan['openings'] if o['kind'] in ('door','door_elev','door_internal')},
            swings={o['id']:[l['sgn'] for l in o.get('leaves',[])] for o in plan['openings'] if o.get('leaves')},
            heal=plan['heal']['summary'])
    before,after=record['before'],record['after']
    record['regression'] = dict(room_count_preserved=before['stats']['rooms']==after['stats']['rooms'],
        door_connections_preserved=before['door_connections']==after['door_connections'],
        swing_directions_preserved=before['swings']==after['swings'])
    report.append(record)
    (WORK/'cad-runs'/'regression.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(sample=f'{label}-{floor}',checks=record['regression']),ensure_ascii=False),flush=True)
