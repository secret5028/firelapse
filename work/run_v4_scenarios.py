import pathlib,sys,json,time
W=pathlib.Path(__file__).resolve().parent
CAD=pathlib.Path(r'C:\Users\<user>\Documents\Codex\2026-09-07\2\CAD3D')
sys.path[:0]=[str(W/'cad-deps'),str(CAD)]
import numpy as np
from fire_zone import Model

rows=[]
for name in ['hotel-4F','hotel-1F','office-1F','office-4F','exhibition-1F']:
    out=W/'cad-v4-runs'/name
    b=json.loads((out/'building.json').read_text(encoding='utf8'));f=b['floors'][0]
    # Same source room and fire parameters across the three opening states.
    candidates=[r for r in f['rooms'] if not any(t in r.get('tags',[]) for t in ('elev','stair'))
        and any(r['id'] in o['sides'] and o['kind']=='door' for o in f['simulation_graph']['connections'])]
    fire=max(candidates,key=lambda r:r['area'])['id']
    for state in (0,50,100):
        start=time.time()
        scenario=dict(fire_room=fire,door_open_default=state,window_open_default=state,opening_unit='percent')
        m=Model(b,f['name'],scenario)
        assert all(v[7]==state/100 for v in m.vents if v[6].startswith(('door','window')))
        sol=m.run(t_end=60,dt_out=10)
        assert sol.success and abs(sol.t[-1]-60)<1e-6 and np.isfinite(sol.y).all(),(name,state,sol.message)
        result=m.result();result.pop('flags')
        (out/f'simulation-{state}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
        row=dict(sample=name,state_percent=state,fire_room=fire,seconds=60,solver_success=True,
            nodes=m.N,mapped_rooms=len(m.rmap),isolated_rooms=m.input_issues['isolated_rooms'],
            max_upper_temperature_c=round(float(sol.y[2*m.N:3*m.N,-1].max()-273.15),3),
            runtime_s=round(time.time()-start,2))
        rows.append(row)
        (W/'cad-v4-runs/scenarios.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps(row,ensure_ascii=False),flush=True)
# Regression for the formerly dropped 14.3m2 room, including ignition there.
b=json.loads((W/'cad-v4-runs/office-1F/building.json').read_text(encoding='utf8'))
m=Model(b,'1F',dict(fire_room='R18'))
assert m.ig is not None and abs(m.nodes[m.ig]['A']-14.3216)<.1
sol=m.run(t_end=10,dt_out=5)
assert sol.success and np.isfinite(sol.y).all()
(W/'cad-v4-runs/isolated-room-test.json').write_text(json.dumps(dict(room='R18',area=m.nodes[m.ig]['A'],seconds=10,solver_success=bool(sol.success),included=True,connectivity='unresolved_isolated'),indent=2),encoding='utf8')
print('Isolated-room ignition test passed',flush=True)
