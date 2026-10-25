"""L1 section1.5 staged diagnostic runs, without native CFAST execution."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import argparse,json,time,concurrent.futures
from pathlib import Path
import numpy as np
from types import SimpleNamespace
import run_lite_l1 as base
from pyrocast_lite.adapter import prepare
from pyrocast_lite.runner import run,results
from pyrocast_lite.failure_state import describe
from pyrocast_lite.montecarlo import aggregate,output_balance_diagnostic,condition_summary,make_samples
from pyrocast_lite.door_classification import classify_doors
from pyrocast_lite.result_adapter import shared_conditions
OUT=base.ROOT/'simulation/results/lite_l1e_20261025'
OLD=base.ROOT/'simulation/results/lite_l1d_20261025'
def read(p):return json.loads(p.read_text('utf-8'))

def reaggregate():
    rows=[]
    for p in sorted((OLD/'samples').glob('*/summary.json')):
        s=read(p)
        if s.get('complete'):
            sample=read(p.parent/'sample.json');r=read(p.parent/'result.json')
            m,_=prepare(sample['scenario'])
            for event in r['events']:
                m.activation[event['room']]=event['condition_time_s'];m.pending.discard(event['room'])
            state=np.load(p.parent/'state.npz');m.sol=SimpleNamespace(t=state['t'],y=state['y'],success=True)
            r['shared_conditions']=shared_conditions(m,r)
            old=s;s=condition_summary(m,r,sample)
            s.update(balance_diagnostic=old['balance_diagnostic'],times=old['times'])
            base.save(OUT/'reaggregate'/p.parent.name/'conditions.json',r['shared_conditions'])
            d=s['balance_diagnostic'];d['limits_percent']={'mass':None,'energy':.1};d['passed']=d['energy_percent']<=.1
            for k in ('FGI','backdraft'):
                s['phenomena'][k]={'status':'not_evaluated','ever_room_count':None,'first_s':None,
                    'reason':'section1.5: no upper unburned fuel reaction in L1d'}
            if s.get('opening_risk'):s['opening_risk']={'status':'not_evaluated','reason':'old unburned inventory without upper reaction'}
        base.save(OUT/'reaggregate'/p.parent.name/'summary.json',s);rows.append(s)
    a=aggregate(rows);a['criterion_revision']='1.5 energy only; mass reported, causal source not proven'
    base.save(OUT/'reaggregate/aggregate.json',a)
    print('REAGG',a['completed'],len(a['output_diagnostic_failures']),flush=True)

def doors():
    overridepath=base.ROOT/'simulation/config/lite-door-overrides.json'
    overrides=read(overridepath) if overridepath.exists() else {}
    m,d=classify_doors(read(base.inputs()['3F']),overrides)
    base.save(OUT/'classified-source.json',m);base.save(OUT/'door-classification.json',d)
    import csv
    with (OUT/'door-classification.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['문ID','연결실A','연결실B','실이름','분류','규칙','확신도','열림확률','근거'])
        for r in d['rows']:w.writerow([r['id'],r['a'],r['b'],' / '.join(r['connected_names']),r['door_class'],r['rule'],r['confidence'],r['probability'],r['reason']])
    print('DOORS',[(r['id'],r['door_class'],r['rule']) for r in d['rows']],flush=True)

def execute(raw,folder,params=None,budget=600,method='BDF',primary_only=False):
    if (folder/'started.json').exists():raise RuntimeError('Already attempted '+str(folder))
    base.save(folder/'started.json',{'time':time.time(),'parameters':params,'method':method,'budget_s':budget})
    m,manifest=prepare(raw,params)
    if primary_only:m.pending.clear()
    base.save(folder/'rule_manifest.json',manifest)
    run(m,raw['duration_s'],10,budget,method=method)
    # Exceptions retain the most recent completed segment and most recent RHS trial.
    for label in ('last_trial_state','failed_segment_start'):
        if hasattr(m,label):
            t,y=getattr(m,label)
            np.savez_compressed(folder/(label+'.npz'),t=t,y=y)
            d=describe(m,t,y);d['state_kind']=label
            # scipy may expose a nonfinite Newton trial; serialize as strings, not valid state.
            def clean(x):
                if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
                if isinstance(x,list):return [clean(v) for v in x]
                if isinstance(x,float) and not np.isfinite(x):return str(x)
                return x
            base.save(folder/(label+'.json'),clean(d))
    r=results(m);base.save(folder/'result.json',r)
    np.savez_compressed(folder/'state.npz',t=m.sol.t,y=m.sol.y)
    audit=output_balance_diagnostic(m);base.save(folder/'balance.json',audit)
    summary={'complete':r['ok'],'integration':m.integration,'rooms':r['room_summary'],'audit':audit}
    base.save(folder/'summary.json',summary)
    print(folder.name,r['ok'],round(m.integration['wall_seconds'],2),m.integration['failure'],flush=True)
    return summary

def isolate_one(sid):
    raw=read(OLD/'samples'/sid/'sample.json')['scenario']
    return execute(raw,OUT/'isolation'/sid,{'smooth_state_bounds':False,'upper_combustion_enabled':False})

def validate():
    from run_lite_l1c import gate
    params={'smooth_state_bounds':True,'upper_combustion_enabled':True}
    b3=read(base.inputs()['B3']);b3['duration_s']=1200
    execute(b3,OUT/'validation/B3',params,primary_only=True)
    # Keep the old standard geometry/door classes for a controlled physics
    # comparison. Classified doors are applied only to the subsequent MC batch.
    raw=read(base.inputs()['3F']);raw['room_rule_r8']={'preset':'standard','room_supply':'item_peak'}
    execute(raw,OUT/'validation/3F',params)
    r=read(OUT/'validation/3F/result.json');g=gate(r)
    base.save(OUT/'validation/gate.json',g)
    print('GATE',json.dumps(g,ensure_ascii=False),flush=True)

def sample_worker(sample):
    folder=OUT/'mc'/sample['id'];params={'smooth_state_bounds':True,'upper_combustion_enabled':True}
    start=time.perf_counter()
    first=execute(sample['scenario'],folder/'BDF',params)
    attempt='BDF';fallback=False
    if not first['complete'] and 'singular' in (first['integration']['failure'] or '').lower():
        execute(sample['scenario'],folder/'Radau',params,method='Radau')
        attempt='Radau';fallback=True
    r=read(folder/attempt/'result.json');m,_=prepare(sample['scenario'],params)
    for event in r['events']:
        m.activation[event['room']]=event['condition_time_s'];m.pending.discard(event['room'])
    state=np.load(folder/attempt/'state.npz');m.sol=SimpleNamespace(t=state['t'],y=state['y'],success=r['ok'])
    r['shared_conditions']=shared_conditions(m,r)
    r.update(lite_revision='L1e_section1.5',solver_fallback=fallback,seed=sample['seed'],mc_sample_id=sample['id'])
    s=condition_summary(m,r,sample);s.update(solver_fallback=fallback,selected_attempt=attempt,
        balance_diagnostic=read(folder/attempt/'balance.json'),failure=r['integration']['failure'],
        times={'total_s':time.perf_counter()-start,'integration_s':r['integration']['wall_seconds'],
               'preprocess_s':None,'postprocess_s':r['postprocess_wall_seconds']})
    base.save(folder/'result.json',r);base.save(folder/'summary.json',s)
    return s

def mc():
    if not read(OUT/'validation/gate.json')['passed']:raise RuntimeError('L3 failed: no MC')
    if (OUT/'mc-started.json').exists():raise RuntimeError('MC already attempted')
    raw=read(OUT/'classified-source.json');samples=make_samples(raw)
    for s in samples:base.save(OUT/'mc'/s['id']/'sample.json',s)
    start=time.perf_counter();base.save(OUT/'mc-started.json',{'time':time.time(),'seed':20261025,'workers':4,
        'changes_from_L1d':['door automatic classification','passages always open','smooth bounds','upper inventory reaction','shared condition table'],
        'same_seed_not_identical_combinations':'class probabilities changed; no claim of one-factor speed comparison'})
    rows=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
        jobs=[pool.submit(sample_worker,s) for s in samples]
        for f in concurrent.futures.as_completed(jobs):
            s=f.result();rows.append(s)
            base.save(OUT/'mc-progress.json',{'finished':len(rows),'wall_seconds':time.perf_counter()-start,
                'cases':[{k:r.get(k) for k in ('sample_id','complete','failure','solver_fallback','times')} for r in rows]})
            print('MC',s['sample_id'],s['complete'],round(s['times']['total_s'],2),'fallback',s['solver_fallback'],flush=True)
    a=aggregate(sorted(rows,key=lambda s:s['sample_id']));a['wall_seconds']=time.perf_counter()-start
    a['numerical_gate_passed']=a['failed_or_incomplete']<=1
    a['solver_fallback_count']=sum(s['solver_fallback'] for s in rows)
    for best in a['worst_including_mandatory'].values():
        if best and best.get('sample_id'):best['opening_combination']=next(s['openings'] for s in samples if s['id']==best['sample_id'])
    base.save(OUT/'mc-aggregate.json',a)
    print('MC FINISHED',a['completed'],a['failed_or_incomplete'],a['wall_seconds'],flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['reaggregate','doors','isolate','validate','mc']);a=p.parse_args()
    if a.stage=='reaggregate':reaggregate()
    elif a.stage=='doors':doors()
    elif a.stage=='validate':validate()
    elif a.stage=='mc':mc()
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
            for x in pool.map(isolate_one,['S00','S04','S10','S13','S15']):pass
if __name__=='__main__':main()
