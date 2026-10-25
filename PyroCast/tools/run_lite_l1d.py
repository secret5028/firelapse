"""Section1.4: 20 samples (18 random +2 mandatory), four process workers."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import concurrent.futures
import hashlib
import json
from pathlib import Path
import time
import traceback
import run_lite_l1 as base
import numpy as np
from pyrocast_lite.adapter import prepare
from pyrocast_lite.runner import run,results
from pyrocast_lite.montecarlo import make_samples,condition_summary,output_balance_diagnostic,aggregate

ROOT=base.ROOT;OUT=ROOT/'simulation/results/lite_l1d_20261025'
def read(p):return json.loads(p.read_text('utf-8'))

def worker(sample):
    folder=OUT/'samples'/sample['id'];start=time.perf_counter()
    if (folder/'started.json').exists():raise RuntimeError('Already attempted: '+sample['id'])
    base.save(folder/'started.json',{'time':time.time(),'seed':sample['seed'],'seed_index':sample['seed_index'],'budget_s':600})
    try:
        m,manifest=prepare(sample['scenario'],{'gas_radiation_enabled':False});prep=time.perf_counter()-start
        base.save(folder/'rule_manifest.json',manifest)
        run(m,sample['scenario']['duration_s'],10,600)
        r=results(m);r['seed']=sample['seed'];r['seed_index']=sample['seed_index'];r['mc_sample_id']=sample['id']
        r['lite_revision']='L1d_section_1.4_exploration';r['preprocess_wall_seconds']=prep
        summary=condition_summary(m,r,sample)
        r['known_bias']=summary['known_bias'];r['bias_scope']=summary['bias_scope']
        r['limits'].append('셀 상층 조건은 부모 셀의 자체 연소 전에도 유입열로 충족될 수 있다.')
        auditstart=time.perf_counter();audit=output_balance_diagnostic(m);audit_s=time.perf_counter()-auditstart
        r['balance_audit']=audit;summary['balance_diagnostic']=audit
        summary['times']={'preprocess_s':prep,'integration_s':m.integration['wall_seconds'],
            'postprocess_s':r['postprocess_wall_seconds'],'balance_diagnostic_s':audit_s,'total_s':time.perf_counter()-start}
        summary['failure']=m.integration.get('failure');summary['openings_file']='sample.json'
        r['boundary_rooms']=summary['room_boundaries'];r['boundary_cells']=summary['cell_boundaries']
        base.save(folder/'result.json',r);base.save(folder/'summary.json',summary)
        np.savez_compressed(folder/'state.npz',t=m.sol.t,y=m.sol.y)
    except Exception as exc:
        summary={'sample_id':sample['id'],'kind':sample['kind'],'complete':False,'failure':str(exc),
            'traceback':traceback.format_exc(),'times':{'total_s':time.perf_counter()-start}}
        base.save(folder/'summary.json',summary)
    return summary

def main():
    if (OUT/'started.json').exists():raise RuntimeError('MC batch already attempted; no automatic repeat')
    old=read(ROOT/'simulation/results/lite_l1c_20261025/trigger_only/standard/balance-diagnostic.json')
    gate={'source':'L1c trigger_only/standard/balance-diagnostic.json','basis':'output diagnostic only',
        'mass_percent':old['mass_max_cumulative_relative_percent'],'energy_percent':old['energy_max_cumulative_relative_percent'],
        'mass_limit_percent':.5,'energy_limit_percent':.1,
        'passed':old['mass_max_cumulative_relative_percent']<=.5 and old['energy_max_cumulative_relative_percent']<=.1,
        'scope':'section1.4 supersedes old0.1%/accepted-step requirement; no new cumulative state'}
    base.save(OUT/'L4-output-gate.json',gate)
    if not gate['passed']:raise RuntimeError('Output gate failed')
    raw=read(base.inputs()['3F']);samples=make_samples(raw)
    for s in samples:base.save(OUT/'samples'/s['id']/'sample.json',s)
    base.save(OUT/'sampling-plan.json',{'seed':20261025,'count':20,'random_count':18,'mandatory_count':2,'workers':4,
        'duration_s':raw['duration_s'],'configuration':'standard/cell upper300C/radiationOFF',
        'probabilities':samples[0]['probabilities'],'kind_counts':{c:sum(o['class']==c for o in samples[0]['openings']) for c in sorted({o['class'] for o in samples[0]['openings']})},
        'source_sha256':hashlib.sha256(base.inputs()['3F'].read_bytes()).hexdigest(),
        'limits':samples[0]['limits'],'sample_ids':[s['id'] for s in samples]})
    base.save(OUT/'started.json',{'time':time.time(),'workers':4,'max_per_case_wall_s':600,
        'no_automatic_retries':True,'code_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'simulation/pyrocast_lite').glob('*.py')}})
    start=time.perf_counter();summaries=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
        jobs={pool.submit(worker,s):s['id'] for s in samples}
        for f in concurrent.futures.as_completed(jobs):
            s=f.result();summaries.append(s)
            base.save(OUT/'progress.json',{'finished':len(summaries),'total':20,'wall_seconds':time.perf_counter()-start,
                'cases':[{k:s.get(k) for k in ('sample_id','kind','complete','times','failure','boundary_room_count','burning_original_rooms')} for s in sorted(summaries,key=lambda s:s['sample_id'])]})
            print(s['sample_id'],'complete',s['complete'],'seconds',round(s['times']['total_s'],2),'burning',len(s.get('burning_original_rooms',[])),flush=True)
    summaries.sort(key=lambda s:s['sample_id']);a=aggregate(summaries)
    a['batch_wall_seconds']=time.perf_counter()-start;a['workers']=4
    a['sample_times']={s['sample_id']:s['times'] for s in summaries}
    for name,best in a['worst_including_mandatory'].items():
        if best and best.get('sample_id'):
            sample=next(s for s in samples if s['id']==best['sample_id'])
            best['opening_combination']=sample['openings']
    base.save(OUT/'aggregate.json',a)
    base.save(OUT/'status.json',{'MC_attempts':20,'finished':20,'completed':a['completed'],'failures':a['failed_or_incomplete'],
        'batch_wall_seconds':a['batch_wall_seconds'],'operating_3D_changed':False,'native_runs':0,'thermal_model_modified':False})
    print('BATCH',json.dumps({k:a[k] for k in ('completed','failed_or_incomplete','batch_wall_seconds','boundary_room_sample_pairs')},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
