"""v8 stage2: serial sources, two extremes or one confirmed opening state."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import argparse,json,time,hashlib
from lite_fixed_openings import classifications, apply_fixed, screening_states, compare_fixed
from pathlib import Path
import numpy as np
import model_simulation as base
from pyrocast_lite.screening_v8_approved import score,scenario,summarize,compare_pairs
from cfast_calculation import run_case,runtime_settings,seal

DEFAULT_OUT=base.ROOT/'simulation/results/lite_v8_approved_screening_20261025'
def read(p):return json.loads(p.read_text('utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def execute(data,folder):
    _,_,summary=run_case(data,folder,label=f"{data['screening_source']['room']} · CFAST")
    summary['result_folder']=str(folder.resolve())
    # Invalid native runs remain available diagnostically, but never ranked.
    summary['complete']=summary['complete'] and summary['ranking_eligible']
    return summary


def source():
    from runtime_storage import RESULTS,locate
    return locate(RESULTS/'room_rule_r8_20261025/source-scenario.json')

def run_batch(top_n=3,out=DEFAULT_OUT,rooms=None):
    out=Path(out).resolve()
    from runtime_storage import is_result_path
    if not is_result_path(out):raise ValueError('Output outside results')
    if (out/'started.json').exists():raise RuntimeError('Already attempted; no automatic rerun')
    raw=read(source());overrides=base.ROOT/'simulation/config/lite-door-overrides.json'
    config=read(overrides) if overrides.exists() else {}
    scored=score(raw,top_n,door_overrides=classifications(config))
    from lite_manual_origin import validate_rooms,manual_scenario
    if rooms is not None:validate_rooms(scored,rooms)
    candidates=[r for r in scored['ranked']+scored['excluded'] if r['room'] in rooms] if rooms else scored['ranked'][:top_n]
    states=screening_states(raw,config);fixed=states==['fixed'];total=len(states)*len(candidates)
    base.save(out/'score.json',{k:v for k,v in scored.items() if k!='classified_model'})
    paths=[*sorted((base.ROOT/'simulation/pyrocast_lite').glob('*.py')),*sorted((base.ROOT/'simulation/pyrocast_lite').glob('*.json')),
           *sorted((base.ROOT/'simulation/pyrocast_cfbt').glob('*.py')),Path(__file__),source(),base.ROOT/'specs/Claude명세-확정상태-v8-20261025.md']
    hashes={str(p.resolve()):sha(p) for p in paths}
    base.save(out/'started.json',{'time':time.time(),'top_n':top_n,'scenario_count':total,'manual_rooms':rooms,'duration_s':3600,'workers':1,
        'integration_budget_s_per_case':runtime_settings()['max_wall_s'],'engine_kind':'cfast_native','sha256':hashes,'MC_runs':0,'new_native_runs':total,
        'fallback':'none'})
    cases=[];start=time.perf_counter()
    for candidate in candidates:
        for state in states:
            rid=candidate['room'];folder=out/rid/state
            base.save(out/'progress.json',{'state':'running','current_room':rid,'current_state':state,'completed':len(cases),'total':total,'top_n':top_n,'rows':cases})
            print('START',len(cases)+1,'/',total,rid,state,flush=True)
            base_state='open_except_confirmed' if fixed else state
            data=manual_scenario(scored,rid,base_state) if rooms else scenario(scored,rid,base_state);data['cad']['fire_key']=rid;apply_fixed(data,config)
            if fixed:
                data['screening_source']['state']='fixed'
                data['screening_source']['opening_states']=[{'id':key,**value} for key,value in data['fixed_openings']['states'].items()]
            base.save(folder/'input.json',data);t=time.perf_counter()
            try:summary=execute(data,folder)
            except Exception as exc:
                summary={'complete':False,'failure':f'{type(exc).__name__}: {exc}','safe_end_s':None,
                    'burning_room_count':None,'smoke_risk_room_count':None,'first_FO_s':None,'times':{'total_s':time.perf_counter()-t}}
            summary.update(room=rid,name=candidate['name'],rank1=candidate.get('rank1'),score=candidate['score'],state=state)
            base.save(folder/'summary.json',summary)
            if (folder/'playback.json').exists():seal(folder)
            cases.append(summary)
            print('END',rid,state,json.dumps({k:summary.get(k) for k in ('complete','burning_room_count','smoke_risk_room_count','first_FO_s','times','failure')},ensure_ascii=False),flush=True)
    ranked=compare_fixed(cases) if fixed else compare_pairs(cases)
    output={'engine_kind':'cfast_native','revision':'v8_approved_screening','state':'completed','top_n':len(candidates),'manual_rooms':rooms,'rows':ranked,'cases':cases,'workers':1,
        'opening_mode':'fixed' if fixed else 'extremes','states_per_room':len(states),'label':'확정 급기' if fixed else '2극단',
        'total_wall_s':time.perf_counter()-start,'complete_count':sum(r['complete'] for r in ranked),
        'complete_scenarios':sum(r['complete'] for r in cases),'attempted_scenarios':len(cases),
        'default_mc_room':next((r['room'] for r in ranked if r['complete']),None),'MC_started':False,
        'code_and_input_unchanged_during_batch':all(sha(base.ROOT/p)==v for p,v in hashes.items()),'stopped_after_stage2':True}
    base.save(out/'comparison.json',output);base.save(out/'progress.json',output)
    print('BATCH COMPLETE; STOP',flush=True);return output

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--top-n',type=int,default=3);ap.add_argument('--out',type=Path,default=DEFAULT_OUT)
    ap.add_argument('--room');args=ap.parse_args();run_batch(args.top_n,args.out,[args.room] if args.room else None)
