"""Reuse completed approved N=5, append ranks6-8 only, strictly serial."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import time,json
from pathlib import Path
import run_lite_screening_v8_approved as batch
from pyrocast_lite.screening_v8_approved import score,scenario,compare_pairs

ROOT=batch.base.ROOT
PREVIOUS=ROOT/'simulation/results/lite_v8_approved_screening_20261025'
OUT=ROOT/'simulation/results/lite_v8_approved_n8_20261025'
def main():
    if (OUT/'started.json').exists():raise RuntimeError('Already attempted; no automatic rerun')
    prior=batch.read(PREVIOUS/'comparison.json');snapshot=batch.read(PREVIOUS/'started.json')
    if prior['complete_scenarios']!=10:raise ValueError('Prior ten cases must be complete')
    if not all(batch.sha(ROOT/p)==h for p,h in snapshot['sha256'].items()):raise ValueError('Prior inputs/code changed; cannot reuse silently')
    raw=batch.read(batch.base.inputs()['3F']);overrides=ROOT/'simulation/config/lite-door-overrides.json'
    s=score(raw,8,door_overrides=batch.read(overrides) if overrides.exists() else None)
    if {r['room'] for r in s['ranked'][:5]}!={r['room'] for r in prior['rows']}:raise ValueError('Prior candidate mismatch')
    batch.base.save(OUT/'score.json',{k:v for k,v in s.items() if k!='classified_model'})
    batch.base.save(OUT/'started.json',{'workers':1,'top_n':8,'new_scenarios':6,'reused_scenarios':10,
        'prior_comparison_sha256':batch.sha(PREVIOUS/'comparison.json'),'prior_result_path':str(PREVIOUS),
        'sha256':snapshot['sha256'],'parameters':batch.PARAMS,'duration_s':3600})
    cases=[{**r,'reused':True,'result_folder':str(PREVIOUS/r['room']/r['state'])} for r in prior['cases']]
    started=time.perf_counter();new=[]
    for candidate in s['ranked'][5:8]:
        for state in s['settings']['states']:
            rid=candidate['room'];folder=OUT/rid/state
            batch.base.save(OUT/'progress.json',{'state':'running','completed':len(new),'total':6,'reused':10,'current_room':rid,'current_state':state})
            print('START NEW',len(new)+1,'/6',rid,state,flush=True)
            data=scenario(s,rid,state);batch.base.save(folder/'input.json',data)
            t=time.perf_counter()
            try:r=batch.execute(data,folder)
            except Exception as exc:r={'complete':False,'failure':str(exc),'times':{'total_s':time.perf_counter()-t}}
            r.update(room=rid,name=candidate['name'],rank1=candidate['rank1'],score=candidate['score'],state=state,
                     reused=False,result_folder=str(folder))
            batch.base.save(folder/'summary.json',r);cases.append(r);new.append(r)
            print('END',rid,state,json.dumps({k:r.get(k) for k in ('complete','burning_room_count','smoke_risk_room_count','smoke_caution_room_count','first_FO_s','times','failure')},ensure_ascii=False),flush=True)
    rows=compare_pairs(cases);elapsed=time.perf_counter()-started
    c={'revision':'v8_approved_screening','state':'completed','top_n':8,'rows':rows,'cases':cases,
       'workers':1,'new_wall_s':elapsed,'reused_wall_s':prior['total_wall_s'],'total_wall_s':elapsed+prior['total_wall_s'],
       'complete_count':sum(r['complete'] for r in rows),'complete_scenarios':sum(r['complete'] for r in cases),
       'attempted_scenarios':len(cases),'new_scenarios':6,'reused_scenarios':10,
       'default_mc_room':next((r['room'] for r in rows if r['complete']),None),'MC_started':False,
       'code_and_input_unchanged_during_batch':all(batch.sha(ROOT/p)==h for p,h in snapshot['sha256'].items())}
    batch.base.save(OUT/'comparison.json',c);batch.base.save(OUT/'progress.json',c)
    print('N8 COMPLETE',elapsed,flush=True)
if __name__=='__main__':main()
