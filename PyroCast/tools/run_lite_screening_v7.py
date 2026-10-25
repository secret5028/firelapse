"""v7 stage3: N sources x two extreme states, strictly serial, then stop."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import argparse,json,time,hashlib
from pathlib import Path
import numpy as np
import run_lite_l1 as base
from pyrocast_lite.screening_v7 import score,scenario,summarize,compare_pairs
from pyrocast_lite.adapter import prepare
from pyrocast_lite.runner import run,results
from pyrocast_lite.montecarlo import output_balance_diagnostic

DEFAULT_OUT=base.ROOT/'simulation/results/lite_v7_screening_20261025'
PARAMS={'oxygen_inventory_mode':False,'remove_cumulative_state':True,'smooth_state_bounds':True,'upper_combustion_enabled':True}
def read(p):return json.loads(p.read_text('utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def execute(data,folder):
    case_start=time.perf_counter();attempts=[];budget=1200.;result=None;m=None;summary=None
    for method in ('BDF','Radau'):
        remaining=budget-sum(a.get('integration_s',0) for a in attempts)
        if remaining<=0:break
        t=time.perf_counter();m,manifest=prepare(data,PARAMS);prep=time.perf_counter()-t
        dest=folder/method;base.save(dest/'rule_manifest.json',manifest);base.save(dest/'contract.json',m.contract)
        run(m,3600,10,remaining,method=method)
        result=results(m);result['solver_fallback']=method=='Radau'
        base.save(dest/'result.json',result);np.savez_compressed(dest/'state.npz',t=m.sol.t,y=m.sol.y)
        summary=summarize(m,result);summary['balance']=output_balance_diagnostic(m)
        attempts.append({'method':method,'complete':result['ok'],'integration_s':m.integration['wall_seconds'],
                         'preprocess_s':prep,'postprocess_s':result['postprocess_wall_seconds'],'failure':m.integration['failure']})
        base.save(dest/'summary.json',{**summary,'execution':attempts[-1]})
        if result['ok'] or 'budget' in (m.integration['failure'] or '').lower():break
    if summary is None:raise RuntimeError('No integration result')
    summary.update(attempts=attempts,solver_fallback=len(attempts)>1,selected_attempt=attempts[-1]['method'],
        times={'integration_s':sum(a['integration_s'] for a in attempts),'preprocess_s':sum(a['preprocess_s'] for a in attempts),
               'postprocess_s':sum(a['postprocess_s'] for a in attempts),'total_s':time.perf_counter()-case_start},failure=attempts[-1]['failure'])
    return summary

def run_batch(top_n=3,out=DEFAULT_OUT):
    out=Path(out).resolve()
    if not out.is_relative_to((base.ROOT/'simulation/results').resolve()):raise ValueError('Output outside results')
    if (out/'started.json').exists():raise RuntimeError('Already attempted; no automatic rerun')
    raw=read(base.inputs()['3F']);overrides=base.ROOT/'simulation/config/lite-door-overrides.json'
    scored=score(raw,top_n,door_overrides=read(overrides) if overrides.exists() else None)
    base.save(out/'score.json',{k:v for k,v in scored.items() if k!='classified_model'})
    paths=[*sorted((base.ROOT/'simulation/pyrocast_lite').glob('*.py')),*sorted((base.ROOT/'simulation/pyrocast_lite').glob('*.json')),
           *sorted((base.ROOT/'simulation/pyrocast_cfbt').glob('*.py')),base.inputs()['3F'],base.ROOT/'specs/Claude명세-확정상태-v7-20261025.md']
    hashes={str(p.relative_to(base.ROOT)):sha(p) for p in paths}
    base.save(out/'started.json',{'time':time.time(),'top_n':top_n,'scenario_count':2*top_n,'duration_s':3600,'workers':1,
        'integration_budget_s_per_case':1200,'parameters':PARAMS,'sha256':hashes,'MC_runs':0,'new_native_runs':0,
        'fallback':'one Radau on numerical failure, within remaining integration budget; no timeout retry'})
    cases=[];start=time.perf_counter()
    for candidate in scored['ranked'][:top_n]:
        for state in scored['settings']['states']:
            rid=candidate['room'];folder=out/rid/state
            base.save(out/'progress.json',{'state':'running','current_room':rid,'current_state':state,'completed':len(cases),'total':2*top_n,'top_n':top_n,'rows':cases})
            print('START',len(cases)+1,'/',2*top_n,rid,state,flush=True)
            data=scenario(scored,rid,state);base.save(folder/'input.json',data);t=time.perf_counter()
            try:summary=execute(data,folder)
            except Exception as exc:
                summary={'complete':False,'failure':f'{type(exc).__name__}: {exc}','safe_end_s':None,
                    'burning_room_count':None,'smoke_risk_room_count':None,'first_FO_s':None,'times':{'total_s':time.perf_counter()-t}}
            summary.update(room=rid,name=candidate['name'],rank1=candidate['rank1'],score=candidate['score'],state=state)
            base.save(folder/'summary.json',summary);cases.append(summary)
            print('END',rid,state,json.dumps({k:summary.get(k) for k in ('complete','burning_room_count','smoke_risk_room_count','first_FO_s','times','failure')},ensure_ascii=False),flush=True)
    ranked=compare_pairs(cases)
    output={'revision':'v7_screening','state':'completed','top_n':top_n,'rows':ranked,'cases':cases,'workers':1,
        'total_wall_s':time.perf_counter()-start,'complete_count':sum(r['complete'] for r in ranked),
        'complete_scenarios':sum(r['complete'] for r in cases),'attempted_scenarios':len(cases),
        'default_mc_room':next((r['room'] for r in ranked if r['complete']),None),'MC_started':False,
        'code_and_input_unchanged_during_batch':all(sha(base.ROOT/p)==v for p,v in hashes.items()),'stopped_after_stage3':True}
    base.save(out/'comparison.json',output);base.save(out/'progress.json',output)
    print('BATCH COMPLETE; STOP',flush=True);return output

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--top-n',type=int,default=3);ap.add_argument('--out',type=Path,default=DEFAULT_OUT)
    args=ap.parse_args();run_batch(args.top_n,args.out)
