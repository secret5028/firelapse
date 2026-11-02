"""One authorized S09 radial run. Cache hit reuses; interrupted runs never retry."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import hashlib,json,time
from copy import deepcopy
import run_lite_l1 as base
import numpy as np
from run_lite_mc_v8_r2 import PARAMS,summarize
from run_lite_l1c import gate
from pyrocast_lite.adapter import prepare
from pyrocast_lite.radial_cells import cache_key,settings
from pyrocast_lite.runner import run,results
from pyrocast_lite.visualization import package

ROOT=base.ROOT
OUT=ROOT/'simulation/results/ui_C9_20261102'


def display_labels(playback, raw):
    # Same approved-use metadata as publish_lite_mc_v8_r2, for the unchanged
    # HRR renderer's fire_load_table lookup. No simulation data is modified.
    rooms={r['id']:r for r in raw['rooms']}
    for row in playback['rooms']:
        source=rooms[row['original_room']]
        use=source.get('approved_fuel_class',{})
        if use.get('label'):row['display_name']=use['label']+' (승인 용도)'
        if use.get('class'):row['approved_fuel_class']=use['class']
    return playback


def main():
    sample=json.loads((ROOT/'simulation/results/lite_v8_mc_R2_10_20261026/S09/sample.json').read_text('utf-8'))
    sample=deepcopy(sample);sample['id']='C9_S09_RADIAL';raw=sample['scenario']
    raw.update(cell_mode='radial',radial_r1_m=6.,radial_r2_m=12.)
    assert raw['duration_s']==3600
    files=sorted((ROOT/'simulation/pyrocast_lite').glob('*.py'))+sorted((ROOT/'simulation/pyrocast_cfbt').glob('*.py'))
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    engine=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()
    key=cache_key(raw,PARAMS,engine)
    folder=OUT/'radial';meta=folder/'cache.json'
    if meta.exists() and json.loads(meta.read_text('utf-8'))['execution_key']==key and (folder/'playback.json').exists():
        print('CACHE HIT',key);return
    if (folder/'started.json').exists():raise RuntimeError('Already attempted; no automatic retry')
    base.save(folder/'started.json',dict(execution_key=key,engine_hashes=hashes,cell_settings=settings(raw),started=time.time(),budget_s=1200,attempts=1))
    base.save(folder/'sample.json',sample)
    start=time.perf_counter();m,manifest=prepare(raw,PARAMS);prep=time.perf_counter()-start
    base.save(folder/'rule_manifest.json',manifest);base.save(folder/'contract.json',m.contract)
    print('START RADIAL S09 3600s / BDF / one attempt',flush=True)
    run(m,3600,10,1200,method='BDF');r=results(m)
    base.save(folder/'result.json',r);np.savez_compressed(folder/'state.npz',t=m.sol.t,y=m.sol.y)
    summary=summarize(m,r,sample)
    summary.update(times=dict(preprocess_s=prep,integration_s=m.integration['wall_seconds'],postprocess_s=r['postprocess_wall_seconds'],total_s=time.perf_counter()-start),gate=gate(r),execution_key=key)
    base.save(folder/'summary.json',summary)
    if r['ok']:
        pb=display_labels(package(m,r,raw,'C9 S09 · R2 radial · 6/12 m · 1시간'),raw)
        pb['provenance'].update(execution_key=key,cell_settings=settings(raw))
        base.save(folder/'playback.json',pb)
        base.save(meta,dict(execution_key=key,engine_sha256=engine,cell_settings=settings(raw),input_sha256=hashlib.sha256(json.dumps(raw,sort_keys=True).encode()).hexdigest()))
    print(json.dumps(dict(complete=r['ok'],times=summary['times'],burning=summary.get('burning_original_rooms'),gate=summary['gate']),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
