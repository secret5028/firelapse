"""Authorized v8 stage5: R2, ten samples, strictly serial, 1200s/sample."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import json,time,hashlib
from pathlib import Path
import numpy as np
import run_lite_l1 as base
from pyrocast_lite.adapter import prepare
from pyrocast_lite.runner import run,results
from pyrocast_lite.montecarlo import make_samples,condition_summary,output_balance_diagnostic,aggregate
from pyrocast_lite.visualization import package

ROOT=base.ROOT;OUT=ROOT/'simulation/results/lite_v8_mc_R2_10_20261026'
PARAMS=dict(smooth_state_bounds=True,upper_combustion_enabled=True,door_jet_enabled=True,
            oxygen_inventory_mode=False,remove_cumulative_state=True)
def read(p):return json.loads(p.read_text('utf-8'))
def current_hashes():
    from execution_evidence import engine_hashes
    return engine_hashes()

def summarize(m,r,sample):
    s=condition_summary(m,r,sample);dt=np.diff(m.sol.t);duration=float(m.sol.t[-1]-m.sol.t[0]);mapping={}
    for row in r['room_summary']:mapping.setdefault(row['original_room'],[]).append(row['cell'])
    for kind,p in s['phenomena'].items():
        p.pop('score_median',None)
        fractions={}
        for rid,cells in mapping.items():
            masks=[]
            for c in cells:
                rec=r['shared_conditions']['rooms'][c][kind]
                masks.append([v is True for v in rec['scores'].get('all_met',rec['all_met'])])
            hit=np.any(masks,axis=0)
            fractions[rid]=float(np.sum(hit[:-1]*dt)/duration) if duration else None
        p['met_time_fraction_by_room']=fractions
        p['met_room_time_fraction']=float(np.mean([x for x in fractions.values() if x is not None])) if duration else None
        p['score_basis']='maximum cell-time degree; duration ratio uses original-room union over cells, left10s intervals; no time median'
    for threshold,key in [(70,'smoke_caution_rooms'),(100,'smoke_risk_rooms')]:
        s[key]=sorted(rid for rid,cells in mapping.items() if any(any(v is not None and v*100>=threshold for v in r['shared_conditions']['rooms'][c][kind]['scores']['degree']) for c in cells for kind in ('FO','FGI','backdraft')))
    s['boundary_room_count']=sum(any(np.any(np.abs(m.sol.y[2*m.N+m.rmap[c]]-273.15-m.manifest['rule_settings']['values']['temperature_C'])<=30) for c in cells) for cells in mapping.values())
    s['boundary_basis']='any saved time within transition threshold ±30C, original-room union'
    s['door_jet_heat_MJ']=r['door_jet']['cumulative_heat_MJ']
    return s

def execute(sample, out=None, publish=True):
    destination=Path(out) if out is not None else OUT
    folder=destination/sample['id'];base.save(folder/'sample.json',sample);start=time.perf_counter();attempts=[]
    for method in ('BDF','Radau'):
        budget=1200-sum(a['integration_s'] for a in attempts)
        if budget<=0:break
        st=time.perf_counter();m,manifest=prepare(sample['scenario'],PARAMS);prep=time.perf_counter()-st
        dest=folder/method;base.save(dest/'rule_manifest.json',manifest);base.save(dest/'contract.json',m.contract)
        run(m,sample['scenario'].get('duration_s',3600),10,budget,method=method);r=results(m)
        base.save(dest/'result.json',r);np.savez_compressed(dest/'state.npz',t=m.sol.t,y=m.sol.y)
        attempts.append(dict(solver=method,complete=r['ok'],integration_s=m.integration['wall_seconds'],preprocess_s=prep,
                             postprocess_s=r['postprocess_wall_seconds'],failure=m.integration['failure']))
        if r['ok'] or 'budget' in (m.integration['failure'] or '').lower():break
    s=summarize(m,r,sample);s.update(attempts=attempts,solver_fallback=len(attempts)>1,selected_attempt=attempts[-1]['solver'],
        balance_diagnostic=output_balance_diagnostic(m),failure=m.integration['failure'],
        times=dict(total_s=time.perf_counter()-start,integration_s=sum(a['integration_s'] for a in attempts)))
    r.update(seed=sample['seed'],mc_sample_id=sample['id'],lite_revision='v8_door_jet_adopted',physical_parameters=m.P)
    base.save(folder/'result.json',r);base.save(folder/'summary.json',s)
    if r['ok']:
        pb=package(m,r,sample['scenario'],f"{sample['scenario'].get('fire_room', sample.get('source_room', 'R2'))} MC {sample['id']} · {sample['kind']}")
        base.save(folder/'playback.json',pb)
        if publish:
            p=ROOT/'simulation/config/lite-viewer.json';cfg=read(p)
            cfg['cases'].append(dict(id=sample['id'],label=pb['label'],path=str(folder/'playback.json')))
            base.save(p,cfg)
    return s

def main():
    if (OUT/'started.json').exists():raise RuntimeError('Already attempted; no automatic rerun')
    raw=read(ROOT/'simulation/results/lite_v8_stage4_R2_20261026/input.json')
    samples=make_samples(raw,seed=20261025,count=10)
    hashes=current_hashes();base.save(OUT/'started.json',dict(time=time.time(),count=10,seed=20261025,workers=1,
        source_room='CAD_3F_R2',duration_s=3600,parameters=PARAMS,budget_s_per_sample=1200,sha256=hashes,
        mandatory=2,random=8,fallback='one Radau only on numerical failure, within remaining integration budget'))
    rows=[];start=time.perf_counter()
    for sample in samples:
        progress=dict(state='running',completed=len(rows),total=10,current=sample['id'],wall_s=time.perf_counter()-start)
        base.save(OUT/'progress.json',progress)
        p=ROOT/'simulation/config/lite-viewer.json';cfg=read(p);cfg['progress_text']=f"R2 MC10 직렬 · {len(rows)}/10 처리 · {sample['id']} 계산 중";base.save(p,cfg)
        print('START',sample['id'],sample['kind'],flush=True)
        try:s=execute(sample)
        except Exception as exc:
            s=dict(sample_id=sample['id'],kind=sample['kind'],complete=False,failure=f'{type(exc).__name__}: {exc}')
            base.save(OUT/sample['id']/'summary.json',s)
        rows.append(s);base.save(OUT/'summaries.json',rows)
        print('END',json.dumps({k:s.get(k) for k in ('sample_id','complete','smoke_risk_rooms','burning_original_rooms','times','failure')},ensure_ascii=False),flush=True)
    a=aggregate(rows)
    for kind,v in a['condition_sample_rates_random_only'].items():
        v.pop('median_of_sample_medians',None)
        maxima=[s['phenomena'][kind]['score_max'] for s in rows if s.get('complete') and s['kind']=='random' and s['phenomena'][kind].get('score_max') is not None]
        v['median_of_sample_maxima']=float(np.median(maxima)) if maxima else None
    a.update(wall_s=time.perf_counter()-start,seed=20261025,workers=1,source_room='CAD_3F_R2',budget_s_per_sample=1200,
        code_unchanged_during_batch=hashes==current_hashes(),
        gate_note='10-sample pilot; original <=1/20 failure criterion not silently rescaled; failures and ledger errors reported explicitly')
    for v in a['worst_including_mandatory'].values():
        if v and v.get('sample_id'):v['openings']=next(s['openings'] for s in samples if s['id']==v['sample_id'])
    base.save(OUT/'aggregate.json',a);base.save(OUT/'progress.json',dict(state='completed',completed=10,total=10,aggregate=a))
    cfg=read(ROOT/'simulation/config/lite-viewer.json');cfg['progress_text']=f"R2 MC10 완료: 완주{a['completed']} / 실패·미완료{a['failed_or_incomplete']} · 발생확률 아님"
    base.save(ROOT/'simulation/config/lite-viewer.json',cfg)
    print('FINISHED',json.dumps({k:a[k] for k in ('completed','failed_or_incomplete','wall_s','output_diagnostic_failures')},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
