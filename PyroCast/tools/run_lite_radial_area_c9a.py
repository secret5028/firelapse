"""Authorized C9a: one S09 radial_area solve, no retries or threshold tuning."""
import run_lite_radial_c9 as previous
import hashlib,json,time
from copy import deepcopy
from pyrocast_lite.adapter import prepare
from pyrocast_lite.radial_cells import cache_key
from pyrocast_lite.runner import run,results
from pyrocast_lite.visualization import package

ROOT=previous.ROOT
OUT=ROOT/'simulation/results/ui_C9a_20261102'


def main():
    sample=json.loads((ROOT/'simulation/results/lite_v8_mc_R2_10_20261026/S09/sample.json').read_text('utf-8'))
    sample=deepcopy(sample);sample['id']='C9A_S09_RADIAL_AREA';raw=sample['scenario']
    raw['cell_mode']='radial_area'
    assert raw['duration_s']==3600
    start=time.perf_counter();m,manifest=prepare(raw,previous.PARAMS);prep=time.perf_counter()-start
    geometry=manifest['cells']['radial']
    files=sorted((ROOT/'simulation/pyrocast_lite').glob('*.py'))+sorted((ROOT/'simulation/pyrocast_cfbt').glob('*.py'))
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    engine=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()
    key=cache_key(raw,previous.PARAMS,engine,geometry)
    folder=OUT/'radial_area';meta=folder/'cache.json'
    if meta.exists() and json.loads(meta.read_text('utf-8'))['execution_key']==key and (folder/'playback.json').exists():
        print('CACHE HIT',key);return
    if (folder/'started.json').exists():raise RuntimeError('Already attempted; no automatic retry')
    save=previous.base.save
    save(folder/'started.json',dict(execution_key=key,engine_hashes=hashes,cell_settings=geometry,started=time.time(),budget_s=1200,attempts=1))
    save(folder/'sample.json',sample);save(folder/'rule_manifest.json',manifest);save(folder/'contract.json',m.contract)
    print('START S09 radial_area / 3600s / BDF / one attempt',flush=True)
    run(m,3600,10,1200,method='BDF');r=results(m)
    save(folder/'result.json',r);previous.np.savez_compressed(folder/'state.npz',t=m.sol.t,y=m.sol.y)
    summary=previous.summarize(m,r,sample)
    summary.update(times=dict(preprocess_s=prep,integration_s=m.integration['wall_seconds'],postprocess_s=r['postprocess_wall_seconds'],total_s=time.perf_counter()-start),gate=previous.gate(r),execution_key=key)
    save(folder/'summary.json',summary)
    if r['ok']:
        pb=previous.display_labels(package(m,r,raw,'C9a S09 · R2 radial_area · legacy 셀 면적 · 1시간'),raw)
        pb['provenance'].update(execution_key=key,cell_settings=geometry)
        save(folder/'playback.json',pb)
        save(meta,dict(execution_key=key,engine_sha256=engine,cell_settings=geometry,input_sha256=hashlib.sha256(json.dumps(raw,sort_keys=True).encode()).hexdigest()))
    print(json.dumps(dict(complete=r['ok'],times=summary['times'],burning=summary.get('burning_original_rooms'),events=r['events']),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
