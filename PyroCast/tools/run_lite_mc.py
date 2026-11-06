"""Parameterized CLI wrapper around the adopted serial MC runner (1200 s/sample)."""
import argparse
import time
from pathlib import Path
import run_lite_mc_v8_r2 as adopted
from result_catalog import atomic_json, read
from lite_fixed_openings import sample_fixed_states
from execution_evidence import write_mc, rule_dependency_hashes


def run_batch(request_path, out):
    request=read(request_path);out=Path(out).resolve()
    from runtime_storage import is_result_path, result_relative
    if not is_result_path(out):raise ValueError('Output outside results')
    if (out/'started.json').exists():raise RuntimeError('Already attempted; no automatic rerun')
    raw=read(out/'input.json');count=request['samples'];seed=request['seed'];room=request['room']
    samples=adopted.make_samples(raw,seed=seed,count=count,fixed_states=sample_fixed_states(raw))
    hashes=adopted.current_hashes();start=time.perf_counter();rows=[]
    atomic_json(out/'started.json',dict(**request,workers=1,budget_s_per_sample=1200,parameters=adopted.PARAMS,
        sha256=hashes,shared_rule_sha256=rule_dependency_hashes(),mandatory=2,random=count-2,fallback='one Radau on numerical failure within remaining integration budget'))
    for sample in samples:
        sample['source_room']=room
        atomic_json(out/'progress.json',dict(state='running',completed=len(rows),total=count,current=sample['id'],wall_s=time.perf_counter()-start))
        try:s=adopted.execute(sample,out=out,publish=False)
        except Exception as exc:
            s=dict(sample_id=sample['id'],kind=sample['kind'],complete=False,failure=f'{type(exc).__name__}: {exc}')
            atomic_json(out/sample['id']/'summary.json',s)
        rows.append(s);atomic_json(out/'summaries.json',rows)
        if s.get('complete'):
            path=out/sample['id']/'playback.json';pb=read(path)
            labels={r['id']:r.get('approved_fuel_class',{}).get('label') for r in raw['rooms']}
            for r in pb['rooms']:
                if labels.get(r['original_room']):r['display_name']=labels[r['original_room']]+' (승인 용도)'
            pb['label']=f"{room.replace('CAD_','')} {sample['id']} · {sample['kind']} · {request['duration_s']//60}분"
            atomic_json(path,pb)
            write_mc(path.parent)
    a=adopted.aggregate(rows)
    for kind,value in a['condition_sample_rates_random_only'].items():
        value.pop('median_of_sample_medians',None)
        maxima=[s['phenomena'][kind]['score_max'] for s in rows if s.get('complete') and s['kind']=='random' and s['phenomena'][kind].get('score_max') is not None]
        value['median_of_sample_maxima']=float(adopted.np.median(maxima)) if maxima else None
    a.update(wall_s=time.perf_counter()-start,source_room=room,seed=seed,workers=1,budget_s_per_sample=1200,
        code_unchanged_during_batch=hashes==adopted.current_hashes())
    for value in a['worst_including_mandatory'].values():
        if value and value.get('sample_id'):value['openings']=next(s['openings'] for s in samples if s['id']==value['sample_id'])
    atomic_json(out/'aggregate.json',a)
    import hashlib
    root=adopted.ROOT/'simulation/results'
    summary=dict(completed=a['completed'],wall_s=a['wall_s'],source_room=room,building_sha256=request['building_sha256'],
        rates=a['condition_sample_rates_random_only'],rows=[])
    for s in rows:
        rel=result_relative(out/s['sample_id']/'playback.json').as_posix()
        summary['rows'].append(dict(id='case-'+hashlib.sha256(rel.encode()).hexdigest()[:20],complete=bool(s.get('complete')),
            burning=len(s.get('burning_original_rooms',[])),smoke_risk=len(s.get('smoke_risk_rooms',[]))))
    atomic_json(out/'mc-summary.json',summary)
    atomic_json(out/'progress.json',dict(state='completed',completed=count,total=count,failed_or_incomplete=a['failed_or_incomplete'],wall_s=a['wall_s']))
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--request',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();run_batch(args.request,args.out)
