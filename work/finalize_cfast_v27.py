"""Complete the selected 30-minute run and compare it with the preserved v26 run."""
from pathlib import Path
import json,sys,subprocess,time,hashlib
from compare_cfast_v27 import compare,OUT,BASE

def invoke(step,force=False):
    argv=[sys.executable,str(Path(__file__).with_name('cad_cfast_multifloor.py')),
        '--ignition-config',str(Path(__file__).with_name('cfast_spread_scenario_v26.json')),
        '--output','CAD-속도검증-v27/final','--max-time-step',str(step)]
    if force:argv.append('--force')
    started=time.perf_counter();subprocess.run(argv,check=True)
    return time.perf_counter()-started

if __name__=='__main__':
    step=float(sys.argv[1]);folder=OUT/'final'
    wall=invoke(step)
    first=json.loads((folder/'cfast-demo.json').read_text('utf8'))
    result=compare(folder,'multifloor')
    old=json.loads((BASE/'cfast-demo.json').read_text('utf8'))
    assert first['building_sha256']==old['building_sha256']
    assert first['solver_members']==old['solver_members']
    assert len(first['vertical_connections'])==len(old['vertical_connections'])==36
    assert len(first['rooms'])==len(old['rooms'])==156
    assert first['prescribed_hrr']==old['prescribed_hrr']
    assert [(f['id'],f['ignition_time']) for f in first['fires']]==[(f['id'],f['ignition_time']) for f in old['fires']]
    replay=invoke(step)
    second=json.loads((folder/'cfast-demo.json').read_text('utf8'))
    assert second['runtime']['cache_hit']
    first.pop('runtime');second.pop('runtime');assert first==second
    def peak(d,k):return max(d[k])
    def energy(d):return sum((a+b)*2.5/1000 for a,b in zip(d['total_hrr'],d['total_hrr'][1:]))
    report=dict(status='completed',physical_validation=False,full_invocation_seconds=wall,cached_invocation_seconds=replay,
        native_timing=json.loads((folder/'multifloor-timing.json').read_text('utf8')),
        baseline_wall_seconds=old['elapsed_seconds'],cache_results_identical=True,
        solver_compartments=100,display_rooms=156,vertical_paths=36,
        primary_curve_unchanged=True,building_sha256=first['building_sha256'],
        baseline_peak_total_kW=peak(old,'total_hrr'),candidate_peak_total_kW=peak(first,'total_hrr'),
        baseline_energy_MJ=energy(old),candidate_energy_MJ=energy(first),
        ignition_baseline=[(f['id'],f['ignition_time']) for f in old['fires']],
        ignition_candidate=[(f['id'],f['ignition_time']) for f in first['fires']],
        comparison=result)
    (OUT/'full-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print('FULL COMPARISON AND CACHE REPLAY PASSED',flush=True)
