"""Confirmed spec8.1 step1 only: four serial BDF runs, no MC/native run."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import json,time,hashlib
import numpy as np
import run_lite_l1 as base
from run_lite_l1c import gate,grouped
from pyrocast_lite.adapter import prepare
from pyrocast_lite.runner import run,results
from pyrocast_lite.montecarlo import output_balance_diagnostic

OUT=base.ROOT/'simulation/results/lite_room_oxygen_stage1_20261025'
PARAMS={'oxygen_inventory_mode':True,'smooth_state_bounds':True,'upper_combustion_enabled':True}
def read(p):return json.loads(p.read_text('utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    if (OUT/'started.json').exists():raise RuntimeError('Stage1 already attempted; no automatic repeat')
    files=list((base.ROOT/'simulation/pyrocast_lite').glob('*.py'))
    frozen=read(base.ROOT/'simulation/results/lite_l1_20261025/source-guard.json')
    frozen={p:sha(base.Path(p)) for p in frozen}
    base.save(OUT/'started.json',{'time':time.time(),'workers':1,'runs':['B1','B2','B3','3F'],
        'spec_sha256':sha(base.ROOT/'specs/Claude명세-확정상태-20261025.md'),
        'code_sha256':{str(p.relative_to(base.ROOT)):sha(p) for p in files},
        'frozen_sha256_before':frozen,'parameters':PARAMS,'budget_s_per_run':1200,
        'scope':'only section3.0; no door jets, classification, MC, UI or native execution'})
    rows=[]
    for name in ('B1','B2','B3','3F'):
        folder=OUT/name;raw=read(base.inputs()[name]);raw['duration_s']=3600 if name=='3F' else 1200
        raw['room_rule_r8']={'preset':'standard','room_supply':'item_peak'}
        base.save(folder/'input.json',raw)
        t=time.perf_counter();m,manifest=prepare(raw,PARAMS);prep=time.perf_counter()-t
        base.save(folder/'rule_manifest.json',manifest);base.save(folder/'contract.json',m.contract)
        print('START',name,'states',len(m.y0()),'oxygen states',m.N,flush=True)
        run(m,raw['duration_s'],10,1200)
        r=results(m);r['preprocess_wall_seconds']=prep
        base.save(folder/'result.json',r)
        np.savez_compressed(folder/'state.npz',t=m.sol.t,y=m.sol.y)
        diag=output_balance_diagnostic(m)
        diagnostics=[m.rhs(float(ts),m.sol.y[:,j],True) for j,ts in enumerate(m.sol.t)]
        stock=m.sol.y[4*m.N:5*m.N].sum(axis=0)
        rates=np.array([d['room_oxygen_rate_kg_s'].sum() for d in diagnostics])
        integrated=np.r_[0.,np.cumsum((rates[1:]+rates[:-1])/2*np.diff(m.sol.t))]
        oxygen_error=stock-stock[0]-integrated
        diag['oxygen_output_residual_percent_initial_stock']=float(np.max(abs(oxygen_error))/stock[0]*100)
        diag['oxygen_stock_min_kg']=float(m.sol.y[4*m.N:5*m.N].min())
        base.save(folder/'balance.json',diag)
        summary={'case':name,'complete':r['ok'],'safe_end_s':float(m.sol.t[-1]),
            'times':{'preprocess_s':prep,'integration_s':m.integration['wall_seconds'],'postprocess_s':r['postprocess_wall_seconds']},
            'state_count':len(m.y0()),'oxygen_state_count':m.N,'solver':m.integration,
            'rooms':r['room_summary'],'burning_rooms':grouped(r['room_summary'],raw['duration_s']),
            'upper_heat_MJ':r['upper_combustion']['cumulative_heat_MJ'],'balance':diag}
        if name=='3F':summary['L3_gate']=gate(r)
        base.save(folder/'summary.json',summary);rows.append(summary)
        base.save(OUT/'progress.json',{'completed_attempts':len(rows),'rows':rows})
        print('END',name,r['ok'],round(m.integration['wall_seconds'],3),summary['burning_rooms'],flush=True)
    same=all(sha(base.Path(p))==v for p,v in frozen.items())
    base.save(OUT/'completed.json',{'rows':rows,'frozen_native_and_shared_conditions_unchanged':same,
        'workers':1,'new_native_runs':0,'MC_runs':0,'stage2_started':False})
    print('STAGE1 FINISHED; STOP',flush=True)
if __name__=='__main__':main()
