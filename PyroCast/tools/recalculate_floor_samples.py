"""New, immutable 60-minute native-CFAST samples: one ranked origin per floor.

No MC. Preserve saved confirmed opening states only on their matching floor;
otherwise use the app's open_except_confirmed scenario. Never replace archives.
"""
import argparse,hashlib,json,os,subprocess,sys,time,uuid
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'simulation'),str(ROOT/'simulation/deps')]
from result_catalog import atomic_json as save,read
from runtime_storage import RESULTS

BUILDINGS=('parkmarine','ganghwa','cad-aabf1346d0e54c94b45ad7d7db7137d4')

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def apply_openings(data,config,room):
    """Only this origin's confirmed state; no other room/floor's MC is reused."""
    from copy import deepcopy
    legacy=(config or {}).get('fixed_state') or {}
    fixed=(config or {}).get('fixed_by_room',{}).get(room)
    if not fixed and legacy.get('source_room')==room:fixed=legacy
    if not fixed:return 'open_except_confirmed'
    if fixed.get('building_sha256')!=data['cad']['building_sha256'] or fixed.get('source_room')!=room:
        raise ValueError('Saved openings belong to another building/origin')
    applied=[];rows=[]
    for v in data['openings']:
        state=fixed.get('states',{}).get(v['id'])
        if not state:raise ValueError('Saved opening missing: '+v['id'])
        if (state.get('a'),state.get('b'))!=(v['a'],v['b']):raise ValueError('Saved opening endpoints changed')
        frac=state.get('effective_fraction')
        if type(frac) not in (float,int) or not 0<=frac<=1 or type(state.get('open')) is not bool:
            raise ValueError('Invalid saved opening state')
        v['schedule']=[[0.,frac]];applied.append(v['id']);rows.append(dict(state,id=v['id'],schedule=v['schedule']))
    data['screening_source'].update(state='saved_room_openings',opening_states=rows)
    data['sample_opening_provenance']=dict(basis='user_saved_room_openings',source_room=room,
        job_id=fixed.get('job_id'),sample_id=fixed.get('sample_id'),applied_ids=applied,
        note='Opening states only; no saved thermal output is reused')
    return 'saved_room_openings'

def prepare(plan_path):
    from model_library import entries,model_path
    from model_simulation import prepare_floor
    from pyrocast_lite.fuel_quantity import load
    from pyrocast_lite.screening_v8_approved import scenario,score as approved_score
    from lite_fixed_openings import classifications
    import model_mc
    from pyrocast_cfbt.room_rule_r8 import prepare_native
    from pyrocast_cfbt.deck import make_deck
    if plan_path.exists():raise ValueError('Plan exists; inputs are immutable')
    approved=read(ROOT/'simulation/pyrocast_lite/approved_uses_v8.json');rows=[]
    registry={e['id']:e for e in entries()}
    for ident in BUILDINGS:
        path=model_path(registry[ident]);digest=sha(path)
        if ident=='ganghwa':
            from lite_fixed_openings import CONFIG
            config=read(CONFIG,{})
        else:config=read(model_mc.config_path(ident),{})
        for floor in read(path)['floors']:
            name=floor['name'];raw,scored=prepare_floor(path,name,digest,json.dumps(load(digest),sort_keys=True))
            if digest==approved['building_sha256'] and set(approved['rooms']) <= {r['id'] for r in raw['rooms']}:
                scored=approved_score(raw,1,door_overrides=classifications(config))
            winner=next(r for r in scored['ranked'] if r['origin_budget']['Q_origin_peak_kW']>0)
            rid=winner['room'];data=scenario(scored,rid,'open_except_confirmed',3600)
            data['cad']['fire_key']=rid;data['cad']['source_path']=path.relative_to(ROOT).as_posix()
            basis=apply_openings(data,config,rid)
            model,targets,manifest=prepare_native(data);make_deck(model,[],targets)
            job=uuid.uuid4().hex;folder=RESULTS/'model-library'/ident/job
            if folder.exists():raise ValueError('Result folder already exists')
            request=dict(building=ident,floor=name,room=rid,duration_s=3600,opening_state=basis,
                         building_sha256=digest,created_at=time.time(),engine='cfast_native',
                         selection='highest existing candidate score; one room per floor; no MC',
                         batch='floor-samples-20261108',origin_score=winner['score'])
            save(folder/'input.json',data);save(folder/'request.json',request)
            row=dict(building=ident,label=registry[ident]['label'],floor=name,room=rid,job=job,
                     folder=str(folder),state='queued',input_sha256=sha(folder/'input.json'),
                     opening_state=basis,rooms=len(model['rooms']),geometry_notes=model.get('equivalent_apertures'),
                     width_corrections=[v for v in data['openings'] if v.get('width_correction')])
            rows.append(row);print(ident,name,rid,'prepared',flush=True)
    assert len(rows)==25
    save(plan_path,dict(schema='firelapse.floor-samples/1',created_at=time.time(),duration_s=3600,rows=rows))

def child(folder):
    import cfast_calculation as calc
    if os.environ.get('FIRELAPSE_CFAST'):calc.ENGINE=Path(os.environ['FIRELAPSE_CFAST'])
    start=time.perf_counter();req=read(folder/'request.json')
    pb,_,summary=calc.run_case(read(folder/'input.json'),folder,
        label=f"{req['floor']} · {req['room']} · CFAST · 2026-11-08 층별 표본")
    save(folder/'status.json',dict(state=pb.get('status','complete'),job=folder.name,building=req['building'],
        engine='cfast',physical_validation=pb.get('physical_validation'),wall_s=time.perf_counter()-start,summary=summary))

def run(plan_path,workers):
    plan=read(plan_path);pending=[r for r in plan['rows'] if r['state']=='queued']
    def work(row):
        folder=Path(row['folder'])
        if (folder/'attempt.json').exists():raise ValueError('Prior attempt retained; cannot overwrite')
        if sha(folder/'input.json')!=row['input_sha256']:raise ValueError('Input changed')
        row['state']='running';save(folder/'attempt.json',dict(started_at=time.time()))
        save(folder/'status.json',dict(state='running',job=row['job'],building=row['building']))
        start=time.monotonic()
        try:
            env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
            with (folder/'console.txt').open('w',encoding='utf8') as log:
                subprocess.run([sys.executable,'-B','-X','utf8',__file__,'child','--folder',str(folder)],
                    stdout=log,stderr=subprocess.STDOUT,env=env,check=True,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            status=read(folder/'status.json');row.update(state=status['state'],wall_s=status['wall_s'])
        except Exception as exc:
            row.update(state='failed',error=str(exc),wall_s=time.monotonic()-start)
            save(folder/'status.json',dict(state='failed',error=str(exc),job=row['job'],building=row['building']))
        return row
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures=[pool.submit(work,row) for row in pending]
        for f in as_completed(futures):
            row=f.result();save(plan_path,plan)
            print(row['building'],row['floor'],row['room'],row['state'],round(row['wall_s'],1),flush=True)
    plan['finished_at']=time.time();save(plan_path,plan)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run','child'])
    p.add_argument('--plan',type=Path);p.add_argument('--folder',type=Path);p.add_argument('--workers',type=int,default=2)
    a=p.parse_args()
    if a.action=='prepare':prepare(a.plan)
    elif a.action=='child':child(a.folder)
    else:run(a.plan,a.workers)
