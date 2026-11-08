"""Serial Monte Carlo: sample openings, then execute stock CFAST for every sample."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import argparse,hashlib,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'simulation'),str(ROOT/'simulation/deps')]
from result_catalog import atomic_json,read
from lite_fixed_openings import sample_fixed_states
# These two helpers only generate inputs and aggregate saved metrics; no Lite solver.
from pyrocast_lite.montecarlo import make_samples,aggregate
from cfast_calculation import run_case,execution_dependencies,runtime_settings

BUDGET_S=runtime_settings()['max_wall_s']


def summarize_batch(rows):
    eligible=[s for s in rows if s.get('complete') and s.get('ranking_eligible',True)]
    value=aggregate(eligible)
    value.pop('known_bias',None);value.pop('bias_scope',None)
    value.update(attempted=len(rows),completed=sum(bool(s.get('complete')) for s in rows),
        failed_or_incomplete=sum(not s.get('complete') for s in rows),
        excluded_physically_invalid=sum(s.get('complete',False) and not s.get('ranking_eligible',True) for s in rows),
        eligible_completed=len(eligible),engine_kind='cfast_native',
        random_attempted=sum(s['kind']=='random' for s in rows),
        failure_fraction=sum(not s.get('complete') for s in rows)/len(rows) if rows else None)
    for kind,rate in value['condition_sample_rates_random_only'].items():
        rate.pop('median_of_sample_medians',None)
        maxima=[s['phenomena'][kind]['score_max'] for s in eligible if s['kind']=='random' and s['phenomena'][kind].get('score_max') is not None]
        import statistics
        rate['median_of_sample_maxima']=statistics.median(maxima) if maxima else None
    return value


def run_batch(request_path,out):
    from runtime_storage import is_result_path,result_relative
    out=Path(out).resolve();request=read(request_path)
    if not is_result_path(out):raise ValueError('Output outside results')
    if (out/'started.json').exists():raise RuntimeError('Already attempted; completed results are never overwritten')
    raw=read(out/'input.json');samples=make_samples(raw,seed=request['seed'],count=request['samples'],fixed_states=sample_fixed_states(raw))
    hashes=execution_dependencies();start=time.perf_counter();rows=[]
    atomic_json(out/'started.json',dict(**request,engine_kind='cfast_native',workers=1,
        budget_s_per_sample=BUDGET_S,shared_rule_sha256=hashes,mandatory=2,random=len(samples)-2,
        fallback='none; no alternate thermal engine'))
    for sample in samples:
        sample['source_room']=request['room'];folder=out/sample['id']
        atomic_json(folder/'sample.json',sample)
        atomic_json(out/'progress.json',dict(state='running',engine_kind='cfast_native',completed=len(rows),total=len(samples),current=sample['id'],wall_s=time.perf_counter()-start))
        try:
            _,_,summary=run_case(sample['scenario'],folder,
                label=f"{request['room'].replace('CAD_','')} {sample['id']} · CFAST · {request['duration_s']//60}분",budget_s=BUDGET_S,sample=sample)
        except Exception as exc:
            summary=dict(sample_id=sample['id'],kind=sample['kind'],complete=False,engine_kind='cfast_native',ranking_eligible=False,failure=f'{type(exc).__name__}: {exc}')
            atomic_json(folder/'summary.json',summary)
        rows.append(summary);atomic_json(out/'summaries.json',rows)
    a=summarize_batch(rows)
    a.update(wall_s=time.perf_counter()-start,source_room=request['room'],seed=request['seed'],workers=1,
        budget_s_per_sample=BUDGET_S,code_unchanged_during_batch=hashes==execution_dependencies())
    for item in a['worst_including_mandatory'].values():
        if item and item.get('sample_id'):item['openings']=next(s['openings'] for s in samples if s['id']==item['sample_id'])
    atomic_json(out/'aggregate.json',a)
    summary=dict(completed=a['completed'],eligible_completed=a['eligible_completed'],excluded_physically_invalid=a['excluded_physically_invalid'],
        wall_s=a['wall_s'],source_room=request['room'],building_sha256=request['building_sha256'],engine_kind='cfast_native',rates=a['condition_sample_rates_random_only'],rows=[])
    for row in rows:
        rel=result_relative(out/row['sample_id']/'playback.json').as_posix()
        summary['rows'].append(dict(id='case-'+hashlib.sha256(rel.encode()).hexdigest()[:20],sample_id=row['sample_id'],
            complete=bool(row.get('complete')),ranking_eligible=row.get('ranking_eligible',False),
            burning=len(row.get('burning_original_rooms',[])),smoke_risk=len(row.get('smoke_risk_rooms',[]))))
    atomic_json(out/'mc-summary.json',summary)
    atomic_json(out/'progress.json',dict(state='completed',engine_kind='cfast_native',completed=len(rows),total=len(samples),failed_or_incomplete=a['failed_or_incomplete'],excluded_physically_invalid=a['excluded_physically_invalid'],wall_s=a['wall_s']))
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--request',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();run_batch(args.request,args.out)
