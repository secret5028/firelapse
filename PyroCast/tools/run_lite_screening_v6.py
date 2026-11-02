"""v6 stage2 only: cheap scoring followed by N serial cases, no MC."""
from lite_fixed_openings import classifications
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import argparse,json,time,hashlib
from pathlib import Path
import numpy as np
import run_lite_l1 as base
from pyrocast_lite.screening import score,scenario,summarize,rank_simulations
from pyrocast_lite.adapter import prepare
from pyrocast_lite.runner import run,results
from pyrocast_lite.montecarlo import output_balance_diagnostic

DEFAULT_OUT=base.ROOT/'simulation/results/lite_v6_screening_20261025'
PARAMS={'oxygen_inventory_mode':False,'remove_cumulative_state':True,'smooth_state_bounds':True,'upper_combustion_enabled':True}
def read(p):return json.loads(p.read_text('utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def run_batch(top_n=3,out=DEFAULT_OUT):
    out=Path(out).resolve()
    if not out.is_relative_to((base.ROOT/'simulation/results').resolve()):raise ValueError('Output outside results')
    if (out/'started.json').exists():raise RuntimeError('Batch already attempted; no automatic rerun')
    raw=read(base.inputs()['3F']);overrides=base.ROOT/'simulation/config/lite-door-overrides.json'
    scored=score(raw,top_n,door_overrides=classifications(read(overrides) if overrides.exists() else None))
    public={k:v for k,v in scored.items() if k!='representative_model'}
    base.save(out/'score.json',public)
    source_code={str(p.relative_to(base.ROOT)):sha(p) for p in (base.ROOT/'simulation/pyrocast_lite').glob('*.py')}
    base.save(out/'started.json',{'time':time.time(),'top_n':top_n,'duration_s':3600,'workers':1,'budget_s_per_case':1200,
        'parameters':PARAMS,'code_sha256':source_code,'spec_sha256':sha(base.ROOT/'specs/Claude명세-확정상태-v6-20261025.md'),
        'ranking':'burning desc, smoke-risk desc, firstFO asc; ties share rank; incomplete unranked',
        'new_native_runs':0,'MC_runs':0,'fallback':'not used: one attempt per selected source in this batch'})
    rows=[];start=time.perf_counter()
    for candidate in scored['ranked'][:top_n]:
        rid=candidate['room'];folder=out/rid
        base.save(out/'progress.json',{'state':'running','current_room':rid,'completed':len(rows),'top_n':top_n,'rows':rows})
        print('START',rid,'score',round(candidate['score'],6),flush=True)
        data=scenario(scored,rid);base.save(folder/'input.json',data)
        before=time.perf_counter()
        try:
            m,manifest=prepare(data,PARAMS);preprocess=time.perf_counter()-before
            base.save(folder/'rule_manifest.json',manifest);base.save(folder/'contract.json',m.contract)
            run(m,3600,10,1200)
            result=results(m);base.save(folder/'result.json',result)
            np.savez_compressed(folder/'state.npz',t=m.sol.t,y=m.sol.y)
            summary=summarize(m,result);summary['balance']=output_balance_diagnostic(m)
            summary.update(times={'preprocess_s':preprocess,'integration_s':m.integration['wall_seconds'],
                'postprocess_s':result['postprocess_wall_seconds']},failure=m.integration['failure'])
        except Exception as exc:
            summary={'complete':False,'failure':f'{type(exc).__name__}: {exc}','safe_end_s':None,
                'burning_room_count':None,'smoke_risk_room_count':None,'first_FO_s':None,'times':{'total_s':time.perf_counter()-before}}
        summary.update(room=rid,name=candidate['name'],rank1=candidate['rank1'],score=candidate['score'])
        base.save(folder/'summary.json',summary);rows.append(summary)
        print('END',rid,json.dumps({k:summary.get(k) for k in ('complete','burning_room_count','smoke_risk_room_count','first_FO_s','times','failure')},ensure_ascii=False),flush=True)
    ranked=rank_simulations(rows)
    summary={'state':'completed','top_n':top_n,'rows':ranked,'total_wall_s':time.perf_counter()-start,
        'complete_count':sum(r['complete'] for r in rows),'attempted_scenarios':len(rows),'workers':1,
        'default_mc_room':next((r['room'] for r in ranked if r['complete']),None),'MC_started':False,
        'ranking_order':['burning_room_count descending','smoke_risk_room_count descending','first_FO_s ascending'],
        'physics_code_unchanged_during_batch':all(sha(base.ROOT/p)==v for p,v in source_code.items()),
        'stopped_after_stage2':True}
    base.save(out/'comparison.json',summary);base.save(out/'progress.json',summary)
    print('BATCH COMPLETE; STOP',flush=True)
    return summary

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--top-n',type=int,default=3);ap.add_argument('--out',type=Path,default=DEFAULT_OUT)
    args=ap.parse_args();run_batch(args.top_n,args.out)
