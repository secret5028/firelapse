"""Rebuild summaries/playbacks from saved accepted outputs; NEVER integrates."""
import json,time,hashlib
from types import SimpleNamespace
import numpy as np
import run_lite_mc_v8_r2 as batch
from pyrocast_lite.adapter import prepare
from pyrocast_lite.montecarlo import output_balance_diagnostic,aggregate
from pyrocast_lite.visualization import package

def recover(folder):
    start=time.perf_counter();sample=batch.read(folder/'sample.json')
    paths=[folder/k/'result.json' for k in ('BDF','Radau') if (folder/k/'result.json').exists()]
    if not paths:return batch.read(folder/'summary.json')
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    rp=paths[-1];r=batch.read(rp);m,manifest=prepare(sample['scenario'],batch.PARAMS)
    if m.manifest_sha256!=r['r8_manifest_sha256']:raise ValueError('Saved/input manifest mismatch')
    z=np.load(rp.parent/'state.npz');m.sol=SimpleNamespace(t=z['t'],y=z['y'],success=r['ok'],message=r['integration']['failure'] or 'Completed')
    for e in r['events']:m.activation[e['room']]=e['condition_time_s'];m.pending.discard(e['room'])
    m.events_log=r['events'];m.integration=r['integration']
    s=batch.summarize(m,r,sample)
    n=m.N
    s['numerical_output_health']=dict(all_finite=bool(np.isfinite(z['y']).all()),
        oxygen_mass_fraction_min=float(z['y'][4*n:6*n].min()),
        unburned_fuel_mass_fraction_min=float(z['y'][6*n:8*n].min()),
        basis='raw saved output, before renderer positivity clipping; no new acceptance threshold')
    attempts=[dict(solver=p.parent.name,complete=batch.read(p)['ok'],integration_s=batch.read(p)['integration']['wall_seconds'],failure=batch.read(p)['integration']['failure']) for p in paths]
    s.update(attempts=attempts,solver_fallback=len(paths)>1,selected_attempt=rp.parent.name,
        balance_diagnostic=output_balance_diagnostic(m),failure=m.integration['failure'],
        times=dict(integration_s=sum(x['integration_s'] for x in attempts),
            total_s=sum(x['integration_s'] for x in attempts)+r['postprocess_wall_seconds']+time.perf_counter()-start,
            basis='sum of recorded integration, final result postprocess, recovery; original preparation/error-report overhead unavailable'),
        postprocess_recovery=dict(reason='untenable scores use record.all_met, not scores.all_met',simulation_reruns=0,
            native_result_sha256=before,saved_result_unchanged=all(hashlib.sha256(__import__('pathlib').Path(p).read_bytes()).hexdigest()==h for p,h in before.items())))
    batch.base.save(folder/'postprocessed-summary.json',s)
    batch.base.save(folder/'result.json',dict(r,seed=sample['seed'],mc_sample_id=sample['id'],lite_revision='v8_door_jet_adopted'))
    if r['ok']:batch.base.save(folder/'playback.json',package(m,r,sample['scenario'],f"R2 MC {sample['id']} · {sample['kind']} · 1시간"))
    return s

def main():
    if batch.read(batch.OUT/'progress.json')['state']!='completed':raise ValueError('Wait for serial batch to finish')
    old=batch.read(batch.OUT/'aggregate.json');batch.base.save(batch.OUT/'aggregate-before-postprocess-fix.json',old)
    rows=[recover(batch.OUT/f'S{i:02d}') for i in range(10)];a=aggregate(rows)
    for k,v in a['condition_sample_rates_random_only'].items():
        v.pop('median_of_sample_medians',None)
        values=[s['phenomena'][k]['score_max'] for s in rows if s.get('complete') and s['kind']=='random' and s['phenomena'][k].get('score_max') is not None]
        v['median_of_sample_maxima']=float(np.median(values)) if values else None
    a.update({k:old[k] for k in ('wall_s','seed','workers','source_room','budget_s_per_sample','code_unchanged_during_batch','gate_note')})
    a.update(postprocess_corrected=True,simulation_reruns_for_correction=0,
        postprocess_note='Integration status recovered from unchanged saved BDF/Radau outputs; KeyError was reporting only')
    for v in a['worst_including_mandatory'].values():
        if v and v.get('sample_id'):v['openings']=batch.read(batch.OUT/v['sample_id']/'sample.json')['openings']
    batch.base.save(batch.OUT/'summaries-before-postprocess-fix.json',batch.read(batch.OUT/'summaries.json'))
    batch.base.save(batch.OUT/'summaries.json',rows);batch.base.save(batch.OUT/'aggregate.json',a)
    cfgpath=batch.ROOT/'simulation/config/lite-viewer.json';cfg=batch.read(cfgpath)
    cfg['cases']=[c for c in cfg['cases'] if c['id']=='stage4']
    for s in rows:
        if s['complete']:
            p=batch.OUT/s['sample_id']/'playback.json';cfg['cases'].append(dict(id=s['sample_id'],label=batch.read(p)['label'],path=str(p)))
    batch.base.save(cfgpath,cfg);print(json.dumps({k:a[k] for k in ('completed','failed_or_incomplete','wall_s','output_diagnostic_failures')},ensure_ascii=False))

if __name__=='__main__':main()
