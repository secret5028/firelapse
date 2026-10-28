"""L1 gated evaluation; no native runs, no automatic threshold tuning or retries."""
import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'simulation/deps'))
sys.path.insert(0,str(ROOT/'simulation'))
OUT=ROOT/'simulation/results/lite_l1_20261025'
SOURCE=Path(r'C:\Users\예방\Documents\Codex\2026-09-07\2\CAD3D')


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n','utf-8')
    if path.name=='result.json' and isinstance(value,dict) and 'shared_conditions' in value and 'room_summary' in value:
        from export_ui_attention import result_index
        result_index(path)


def legacy():
    from pyrocast_lite.core import Model
    sys.path.insert(0,str(SOURCE))
    spec=importlib.util.spec_from_file_location('original_fire_zone',SOURCE/'fire_zone.py')
    original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original)
    building=json.loads((SOURCE/'out/28-200-2018-00000088/building.json').read_text('utf-8'))
    # One historical input, used identically in all three compatibility runs.
    scenario={'fire_room':'R0','door_open_default':0,'window_open_default':0,'T_break':None}
    rows={}; states={}
    for name,cls,params in [('original',original.Model,None),('copy_compatible',Model,{'pyro_feedback':True}),('copy_feedback_off',Model,{'pyro_feedback':False})]:
        t=time.perf_counter();m=cls(deepcopy(building),'4F',scenario,params);prep=time.perf_counter()-t
        t=time.perf_counter();sol=m.run(1200,10);elapsed=time.perf_counter()-t
        if not sol.success:raise RuntimeError(name+': '+sol.message)
        r=m.result();states[name]=sol.y
        rows[name]={'complete':bool(sol.success),'preprocess_s':prep,'integration_s':elapsed,
                    'nfev':sol.nfev,'HRR_peak_kW':max(r['HRR_kW']),
                    'upper_max_C':max(max(x['T_u']) for x in r['rooms'])}
        print(name,rows[name],flush=True)
    equal=np.array_equal(states['original'],states['copy_compatible'])
    report={'input':'historical hotel 4F R0 / closed doors and windows / 1200 s',
            'legacy_sha256':hashlib.sha256((SOURCE/'fire_zone.py').read_bytes()).hexdigest(),
            'runs':rows,'compatible_state_arrays_identical':bool(equal),
            'compatible_max_abs_state_difference':float(np.max(np.abs(states['original']-states['copy_compatible']))),
            'feedback_off_max_abs_state_difference':float(np.max(np.abs(states['original']-states['copy_feedback_off']))),
            'historical_5_12_seconds_reproduction':'not a fixed-time guarantee; fresh same-machine comparison above',
            'passed_copy_compatibility':bool(equal),
            'original_feedback_is_not_secondary_ignition':True,
            'historical_topology':'retained for L0 reproduction only, L1 adapter is floor-only'}
    save(OUT/'L0/report.json',report)
    if not equal:raise RuntimeError('L0 copied core changed legacy equations unexpectedly')


def inputs():
    return {'B1':ROOT/'fixtures/room_rule_benchmark_3room.json',
            'B2':ROOT/'fixtures/room_rule_benchmark_3room_b2.json',
            'B3':ROOT/'fixtures/room_rule_benchmark_3room_b3.json',
            '3F':ROOT/'simulation/results/room_rule_r8_20261025/source-scenario.json'}


def contract():
    from pyrocast_lite.adapter import prepare,digest
    from pyrocast_cfbt.room_rule_r8 import prepare as native_prepare
    rows={}
    for name,path in inputs().items():
        raw=json.loads(path.read_text('utf-8'));raw['room_rule_r8']={'preset':'standard','room_supply':'item_peak'}
        lite,manifest=prepare(raw);native,_,expected=native_prepare(raw)
        assert digest(manifest)==digest(expected)
        assert lite.contract['parents_identical']
        assert all(lite.contract['curve_hashes'][g['room']]==digest(g['room_rule_curve']) for g in native['fuel_groups'])
        rows[name]={'room_count':lite.N,'fire_count':len(lite.groups),'vent_count':len(lite.vents),**lite.contract}
    save(OUT/'L1/contracts.json',{'passed':True,'cases':rows})
    print('L1 contracts passed',flush=True)


def case(name):
    from pyrocast_lite.adapter import prepare
    from pyrocast_lite.runner import run,results
    path=inputs()[name];raw=json.loads(path.read_text('utf-8'))
    raw['room_rule_r8']={'preset':'standard','room_supply':'item_peak'}
    folder=OUT/('L3/3F' if name=='3F' else 'L2/'+name)
    folder.mkdir(parents=True,exist_ok=True)
    if (folder/'started.json').exists():raise RuntimeError('Already attempted; no automatic rerun: '+str(folder))
    save(folder/'started.json',{'input':str(path),'time':time.time()})
    t=time.perf_counter();m,manifest=prepare(raw);prep=time.perf_counter()-t
    save(folder/'rule_manifest.json',manifest);save(folder/'contract.json',m.contract)
    duration=3600 if name=='3F' else raw['duration_s']
    run(m,duration,10,600);r=results(m);r['preprocess_wall_seconds']=prep
    save(folder/'result.json',r)
    np.savez_compressed(folder/'state.npz',t=m.sol.t,y=m.sol.y)
    save(folder/'summary.json',{'complete':m.integration['complete'],'times':{'preprocess_s':prep,
        'integration_s':m.integration['wall_seconds'],'postprocess_s':r['postprocess_wall_seconds']},
        'events':r['events'],'rooms':r['room_summary'],'integration':m.integration})
    print(name, 'complete',m.integration['complete'],'seconds',m.integration['wall_seconds'],
          'burning',[(x['cell'],x['first_actual_positive_HRR_s'],x['longest_positive_HRR_s']) for x in r['room_summary'] if x['actual_peak_kW']>0],flush=True)
    return r


def gates():
    rows={}
    for name in ['B1','B2','B3']:
        r=case(name);root=r['fire_room']
        actual=[x for x in r['room_summary'] if x['cell']!=root and x['actual_peak_kW']>0]
        passed=r['ok'] and (not actual if name=='B1' else len(actual)==2 and all(x['longest_positive_HRR_s']>=60 for x in actual))
        rows[name]={'passed':bool(passed),'added_burning_cells':[x['cell'] for x in actual]}
        save(OUT/'L2/gates.json',rows)
        if name=='B1' and not passed:
            save(OUT/'status.json',{'stopped_at':'L2/'+name,'reason':'negative control additional ignition' if name=='B1' and actual else 'positive control/simulation gate failed',
                                   'L3':'not_run','L4':'not_run','MC':'not_run'})
            print('STOP at L2/'+name,flush=True);return
    if not all(x['passed'] for x in rows.values()):
        save(OUT/'status.json',{'stopped_at':'L2','reason':'positive control gate failed',
                               'L3':'not_run','L4':'not_run','MC':'not_run'})
        print('STOP after L2 positive controls',flush=True);return
    r=case('3F')
    base=json.loads((ROOT/'simulation/results/room_rule_r8_20261025/selected/analysis.json').read_text('utf-8'))
    save(OUT/'L3/reference.json',base)
    # Comparison and audit are prepared after inspecting the actual reference schema.
    save(OUT/'status.json',{'stopped_at':'L3_comparison_pending','MC':'not_run','complete':r['ok']})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['L0','L1','L2'])
    a=parser.parse_args();{'L0':legacy,'L1':contract,'L2':gates}[a.stage]()
