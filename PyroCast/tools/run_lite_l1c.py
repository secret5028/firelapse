"""Section 1.3 staged runs. Never invokes native CFAST or retries a case."""
import argparse
import hashlib
import json
import time
from pathlib import Path
import run_lite_l1 as base
import numpy as np
from pyrocast_lite.adapter import prepare
from pyrocast_lite.runner import run, results

ROOT=base.ROOT
OUT=ROOT/'simulation/results/lite_l1c_20261025'
def read(p):return json.loads(p.read_text('utf-8'))

def grouped(rows,horizon=2850):
    ans={}
    for r in rows:
        t=r['first_actual_positive_HRR_s']
        if t is not None and t<=horizon and r['actual_peak_kW']>0:
            room=r['original_room'];ans[room]=min(ans.get(room,float('inf')),t)
    return ans

def gate(result):
    std=read(ROOT/'simulation/results/room_rule_r8_20261025/selected/analysis.json')
    agg=read(ROOT/'simulation/results/room_rule_r8_20261025/aggressive/partial-analysis.json')
    ns=grouped(std['rows']);na=grouped(agg['rows']);lite=grouped(result['room_summary'])
    # Ties are cohorts, not alphabetic fabricated ignition order. Compare all pairs.
    def sign(x):return (x>0)-(x<0)
    order_differences=[{'a':a,'b':b,'native_times':[na[a],na[b]],'lite_times':[lite[a],lite[b]]}
        for a in sorted(lite) for b in sorted(lite) if a<b and a in na and b in na
        and sign(na[a]-na[b])!=sign(lite[a]-lite[b])]
    subset=set(ns)<=set(lite)<=set(na)
    return {'horizon_s':2850,'native_standard':ns,'native_aggressive_partial':na,
        'lite':lite,'lite_full_3600':grouped(result['room_summary'],3600),
        'subset_pass':subset,'order_pass':not order_differences,'order_differences':order_differences,
        'passed':bool(result['ok'] and subset and not order_differences),
        'native_aggressive_complete':False,'time_grid_note':'native5s/lite10s; simultaneous samples compared as cohorts'}

def floor(stage,preset='standard'):
    folder=OUT/stage/preset
    if (folder/'started.json').exists():raise RuntimeError('Already attempted; no rerun')
    raw=read(base.inputs()['3F']);raw['room_rule_r8']={'preset':preset,'room_supply':'item_peak'}
    params={'gas_radiation_enabled':stage=='radiation_on'} if stage!='trigger_only' else None
    base.save(folder/'started.json',{'stage':stage,'preset':preset,'time':time.time(),
        'code_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'simulation/pyrocast_lite').glob('*.py')}})
    start=time.perf_counter();m,manifest=prepare(raw,params);prep=time.perf_counter()-start
    base.save(folder/'rule_manifest.json',manifest);base.save(folder/'contract.json',m.contract)
    run(m,3600,10,600);r=results(m);r['preprocess_wall_seconds']=prep
    base.save(folder/'result.json',r)
    np.savez_compressed(folder/'state.npz',t=m.sol.t,y=m.sol.y)
    g=gate(r);base.save(folder/'gate.json',g)
    base.save(folder/'summary.json',{'complete':r['ok'],'times':{'preprocess_s':prep,
        'integration_s':r['integration']['wall_seconds'],'postprocess_s':r['postprocess_wall_seconds']},
        'events':r['events'],'rooms':r['room_summary'],'gate':g})
    print(json.dumps({'stage':stage,'preset':preset,'seconds':r['integration']['wall_seconds'],'gate':g},ensure_ascii=False),flush=True)

def isolation():
    import csv
    import run_lite_l1b as iso
    iso.OUT=OUT/'radiation_on';iso.base.OUT=iso.OUT
    rows=[iso.isolated(name,{'gas_radiation_enabled':True}) for name in ('B2','B3')]
    base.save(iso.OUT/'isolation/comparison.json',rows)
    def series(path):
        with path.open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
        return {k:np.array([float(r[k]) for r in rows]) for k in rows[0]}
    checks=[]
    for name in ('B2','B3'):
        before=series(ROOT/f'simulation/results/lite_l1b_20261025/isolation/{name}/overlay.csv')
        after=series(iso.OUT/f'isolation/{name}/overlay.csv')
        np.testing.assert_array_equal(before['time_s'],after['time_s'])
        metrics={}
        for label,data in [('before',before),('after',after)]:
            error=data['lite_ULT_1']-data['native_ULT_1'];early=data['time_s']<=240;late=data['time_s']>=600
            metrics[label]={'initial_max_positive_error_C':float(max(0,error[early].max())),
                'late_rms_error_C':float(np.sqrt(np.mean(error[late]**2))),
                'at_1200_error_C':float(error[-1])}
        worse=metrics['after']['initial_max_positive_error_C']>metrics['before']['initial_max_positive_error_C']+1e-6
        late_better=metrics['after']['late_rms_error_C']<metrics['before']['late_rms_error_C']
        checks.append({'case':name,**metrics,'initial_overestimate_worse':worse,'late_error_reduced':late_better,
            'retain_candidate':bool(not worse and late_better)})
    decision={'checks':checks,'retain_candidate':all(c['retain_candidate'] for c in checks),
        'criteria':'early 0..240s max positive temperature error must not grow; late600..1200s RMS must shrink',
        'default_enabled':False,'no_retuning':True}
    base.save(OUT/'radiation-decision.json',decision)
    print(json.dumps(decision,ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['trigger_only','radiation_on','isolation']);p.add_argument('--preset',default='standard',choices=['standard','aggressive'])
    a=p.parse_args()
    if a.stage=='isolation':isolation()
    else:floor(a.stage,a.preset)
