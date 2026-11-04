"""Checkpointed, serial representative-floor runs; no solver or threshold changes.

Prepare never calculates. Run consumes frozen inputs once, in child processes,
with a wall timeout and a process lock. Failures are retained, never retried.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'simulation'), str(ROOT/'simulation/deps')]
import model_simulation as sim
from model_library import entries, model_path

OUT = ROOT/'simulation/results/overnight-20261104'
CUTOFF = '2026-11-05T00:00:00+00:00'

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path, default=None):
    try: return json.loads(Path(path).read_text('utf8'))
    except (OSError, ValueError): return default
def save(path, value):
    from result_catalog import atomic_json
    atomic_json(path, value)

def engine_files():
    return {p.relative_to(ROOT).as_posix():sha(p) for folder in ('simulation/pyrocast_lite','simulation/pyrocast_cfbt')
            for p in sorted((ROOT/folder).glob('*')) if p.suffix in ('.py','.json')}

def freeze_openings(data, raw, config):
    """Keep the input schedule, replacing only same-building confirmed openings.

    A saved floor-specific MC state is not extrapolated to other floors.
    """
    fixed=(config or {}).get('fixed_state')
    if fixed and fixed.get('building_sha256')!=raw['cad']['building_sha256']:
        raise ValueError('Confirmed openings belong to another building')
    original={v['id']:v for v in raw['openings']}
    fixed_states=(fixed or {}).get('states',{})
    applied=[];states=[]
    for vent in data['openings']:
        vent['schedule']=deepcopy(original[vent['id']]['schedule'])
        item=fixed_states.get(vent['id'])
        if item:
            if (item.get('a'),item.get('b'))!=(vent['a'],vent['b']):
                raise ValueError('Confirmed opening endpoints changed: '+vent['id'])
            fraction=item['effective_fraction']
            if type(fraction) not in (int,float) or not 0<=fraction<=1:
                raise ValueError('Invalid opening fraction')
            vent['schedule']=[[0.,fraction]];applied.append(vent['id'])
        states.append(dict(id=vent['id'],a=vent['a'],b=vent['b'],open=vent['schedule'][0][1]>0,
                           effective_fraction=vent['schedule'][0][1],schedule=vent['schedule']))
    basis='confirmed_subset_and_input_default' if applied else 'input_default'
    data['screening_source'].update(state=basis,opening_states=states)
    data['overnight_openings']=dict(basis=basis,confirmed_ids=applied,
        confirmation_source={k:v for k,v in (fixed or {}).items() if k!='states'},
        worst_case_claim=False)
    return basis

def prepare():
    if (OUT/'plan.json').exists(): raise ValueError('Plan already exists; inputs must not be overwritten')
    from pyrocast_lite.fuel_quantity import load
    from pyrocast_lite.screening_v8_approved import score as approved_score, scenario
    from lite_fixed_openings import classifications
    rows=[];excluded=[]
    approved=read(ROOT/'simulation/pyrocast_lite/approved_uses_v8.json')
    for entry in entries():
        if not entry.get('simulation_enabled') or entry.get('source_kind')!='cad':
            excluded.append(dict(building=entry['id'],reason='dedicated_native_cases' if entry['id']=='wando' else 'scan_or_disabled'))
            continue
        ident=entry['id'];path=model_path(entry);digest=sha(path);building=read(path)
        config_path=(ROOT/'simulation/config/lite-door-overrides.json' if ident=='ganghwa' else
            ROOT/'simulation/config/model-fixed-openings'/(digest+'.json'))
        config=read(config_path,{})
        for floor in building['floors']:
            name=floor['name'];folder=OUT/ident/name
            if not folder.resolve().is_relative_to(OUT.resolve()):raise ValueError('Invalid floor path')
            row=dict(building=ident,floor=name,building_sha256=digest,folder=str(folder),state='blocked',
                     engine='pyrocast_lite',origin=None,error=None)
            try:
                raw,scored=sim.prepare_floor(path,name,digest,json.dumps(load(digest),sort_keys=True))
                # The reviewed factory 3F keeps its approved uses, including R2=1800.
                if digest==approved['building_sha256'] and set(approved['rooms']) <= {r['id'] for r in raw['rooms']}:
                    scored=approved_score(raw,1,door_overrides=classifications(config))
                candidates=[r for r in scored['ranked'] if r['origin_budget']['Q_origin_peak_kW']>0]
                if not candidates:raise ValueError('No eligible representative origin')
                winner=candidates[0];rid=winner['room'];data=scenario(scored,rid,'open_except_confirmed',3600)
                data['cad']['fire_key']=rid
                basis=freeze_openings(data,raw,config)
                connected={key for v in data['openings'] for key in (v['a'],v['b']) if key!='OUTSIDE'}
                isolates=[r['id'] for r in data['rooms'] if r['id'] not in connected]
                request=dict(building=ident,floor=name,room=rid,duration_s=3600,opening_state=basis,
                    building_sha256=digest,created_at=time.time(),engine='pyrocast_lite',
                    selection='existing_score_first',tie_break='room_id_ascending',origin_score=winner['score'],
                    isolated_rooms=isolates,origin_isolated=rid in isolates,classification='existing_table_and_user_overrides')
                save(folder/'input.json',data);save(folder/'request.json',request)
                save(folder/'score.json',{k:v for k,v in scored.items() if k!='classified_model'})
                row.update(state='queued',origin=rid,score=winner['score'],rooms=len(data['rooms']),
                           isolated_rooms=isolates,opening_state=basis,input_sha256=sha(folder/'input.json'))
            except Exception as exc: row['error']=f'{type(exc).__name__}: {exc}'
            rows.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
    priority={('ganghwa','3F'):0,('parkmarine','5F'):1}
    rows.sort(key=lambda r:(priority.get((r['building'],r['floor']),2),r['building'],r['floor']))
    plan=dict(schema='overnight-floors/1',created_at=time.time(),cutoff_utc=CUTOFF,engine='pyrocast_lite',
        duration_s=3600,budget_s=1200,child_timeout_s=1260,workers=1,automatic_retries=0,
        engine_files=engine_files(),rows=rows,excluded=excluded)
    save(OUT/'plan.json',plan);save(OUT/'control.json',dict(stop=False))
    return plan

def child(folder):
    folder=Path(folder).resolve()
    if not folder.is_relative_to(OUT.resolve()):raise ValueError('Child output outside batch')
    sim.execute(folder)

def run():
    import msvcrt
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/'batch.lock').open('a+b') as lock:
        lock.seek(0);lock.write(b'1');lock.flush();lock.seek(0)
        try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:raise RuntimeError('Another serial batch is running')
        plan=read(OUT/'progress.json') or read(OUT/'plan.json')
        save(OUT/'worker.json',dict(pid=os.getpid(),started_at=time.time()))
        if plan['engine_files']!=engine_files():raise ValueError('Engine changed since input freeze')
        env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
        for row in plan['rows']:
            folder=Path(row['folder'])
            if row['state']=='running':
                row.update(state='interrupted',error='Prior worker exited; no automatic retry')
                save(folder/'status.json',dict(state='interrupted',error=row['error']))
            if row['state']!='queued':continue
            if (folder/'attempt.json').exists():
                row.update(state='interrupted',error='Prior attempt retained; no automatic retry');continue
            if read(OUT/'control.json',{}).get('stop') or datetime.now(timezone.utc)>=datetime.fromisoformat(plan['cutoff_utc']):break
            if sha(folder/'input.json')!=row['input_sha256'] or plan['engine_files']!=engine_files():
                raise ValueError('Frozen input/engine changed; stop batch')
            save(folder/'attempt.json',dict(started_at=time.time(),owner_pid=os.getpid()))
            row['state']='running';save(OUT/'progress.json',plan);start=time.monotonic()
            try:
                with (folder/'console.txt').open('w',encoding='utf8') as log:
                    subprocess.run([sys.executable,'-B','-X','utf8',__file__,'child',str(folder)],cwd=ROOT,env=env,
                        stdout=log,stderr=subprocess.STDOUT,timeout=1260,check=True,
                        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                status=read(folder/'status.json',{})
                row.update(state=status.get('state','failed'),error=status.get('error'),summary=status.get('summary'))
                save(folder/'execution-evidence-nightly.json',dict(input_sha256=row['input_sha256'],
                    engine_sha256=plan['engine_files'],request=read(folder/'request.json'),kind='new_execution'))
                if row['state']=='complete' and row['building'] in ('parkmarine','showroom'):
                    dest=sim.RESULTS/row['building']/uuid.uuid4().hex
                    shutil.copytree(folder,dest);row['published_folder']=str(dest)
            except subprocess.TimeoutExpired:row.update(state='timeout',error='1260 s wall timeout; no retry')
            except Exception as exc:row.update(state='failed',error=f'{type(exc).__name__}: {exc}')
            row['wall_s']=time.monotonic()-start
            if row['state']!='complete':
                save(folder/'status.json',dict(state=row['state'],error=row['error'],wall_s=row['wall_s']))
            save(OUT/'progress.json',plan);print(row['building'],row['floor'],row['state'],row['wall_s'],flush=True)
        plan['finished_at']=time.time();save(OUT/'progress.json',plan)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('prepare','run','child'));parser.add_argument('folder',nargs='?');args=parser.parse_args()
    if args.action=='prepare':prepare()
    elif args.action=='run':run()
    else:child(args.folder)
