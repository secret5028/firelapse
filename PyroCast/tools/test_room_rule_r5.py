"""Authorized nine-case B1 sweep. Fixed thresholds; bounded serial native runs."""
import argparse,json,sys,time
from copy import deepcopy
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'simulation'));sys.path.insert(0,str(ROOT/'tools'))
import test_room_rule_r4 as b4
from pyrocast_cfbt.spread import simulate
from pyrocast_cfbt.native import digest,load_result
OUT=ROOT/'simulation/results/room_rule_r5_20261025'

def save(path,obj):b4.save(path,obj)

def crossing(t,values,point):
    hits=np.flatnonzero(np.asarray(values)>=point)
    if not len(hits):return None
    i=int(hits[0]);return [float(t[max(0,i-1)]),float(t[i])]

def summarize(folder):
    b4.OUT=folder.parent
    report=b4.analyze(folder.name)
    if report.get('complete') and (folder/'result.json').exists():
        r=json.loads((folder/'result.json').read_text('utf-8'))
        report.update(terminated=r['terminated'],error=r.get('error'),native_horizon_complete=r['simulation_complete_to_requested_horizon'])
        report['complete']=r['simulation_complete_to_requested_horizon'] and r.get('error') is None
        report['R1_600C_bracket_s']=crossing(r['time_s'],r['rooms']['R1']['T_upper_C'],600)
        report['parameters']=json.loads((folder/'parameters.json').read_text('utf-8'))
        report['selection_basis']='Relative lateness among nine, as clarified by user; no 600 s cutoff'
        report['total_wall_seconds']=report['measured_wall_seconds']
        save(folder/'analysis.json',report)
    return report

def repair_reader_cases():
    """Validate normal-exit raw output and cache it; never rerun those native jobs."""
    for folder in sorted((OUT/'sweep').glob('P*')):
        result_path=folder/'result.json'
        if not result_path.exists():continue
        result=json.loads(result_path.read_text('utf-8'))
        if 'could not convert string to float' not in (result.get('error') or ''):continue
        repaired=[]
        for run_folder in sorted(folder.glob('run_*')):
            if (run_folder/'completed.json').exists():continue
            state=json.loads((run_folder/'execution-state.json').read_text('utf-8'))
            if state.get('reason')!='invalid_native_output':continue
            if 'NORMAL EXIT' not in (run_folder/'case.log').read_text(errors='replace').upper():continue
            sig=json.loads((run_folder/'planned-execution.json').read_text('utf-8'))
            if sig['engine']!=digest(b4.ENGINE) or sig['input']!=digest(run_folder/'case.in') or sig['sidecar']!=digest(run_folder/'case.cfbt'):
                raise ValueError('Recovery provenance differs')
            run={'folder':str(run_folder),'engine_sha256':sig['engine'],'input_sha256':sig['input'],
                 'wall_seconds':state['wall_seconds'],'cache_hit':False,'normal_exit':True,
                 'timing_basis':'saved wall time through original parse failure; no rerun'}
            load_result(run_folder,1200,run)
            files=[*run_folder.glob('case*.csv'),run_folder/'case.log',run_folder/'execution.log']
            save(run_folder/'completed.json',{'signature':sig,'run':run,'files':{p.name:digest(p) for p in files}})
            save(run_folder/'reader-recovery.json',{'previous_execution_state':state,'correction':'parse native E-less 3-digit exponent; bytes of native files unchanged'})
            repaired.append(run_folder.name)
        if not repaired:continue
        print('RECOVER',folder.name,repaired,flush=True)
        previous=json.loads((folder/'execution.json').read_text('utf-8'))
        save(folder/'execution-before-reader-repair.json',previous)
        (folder/'result-before-reader-repair.json').write_bytes(result_path.read_bytes())
        raw=json.loads((folder/'requested-scenario.json').read_text('utf-8'))
        # execute() reuses exact cached decks; only a genuinely new next pass is run.
        remaining=max(1.,600-previous['measured_wall_seconds'])
        raw['spread']['wall_time_budget_s']=remaining
        start=time.monotonic();r=simulate(raw,b4.ENGINE,folder)
        execution={'complete':r['simulation_complete_to_requested_horizon'] and r.get('error') is None,
                   'error':r.get('error'),'measured_wall_seconds':previous['measured_wall_seconds']+time.monotonic()-start,
                   'fixture_sha256':digest(b4.FIXTURE),'reader_recovery_reused_runs':repaired}
        save(folder/'execution.json',execution)

def sweep(analyze_only=False):
    base=json.loads(b4.FIXTURE.read_text('utf-8'));base_hash=digest(b4.FIXTURE)
    cases=[]
    for peak in (2000,3000,4000):
        for window in ('closed','small','large'):
            label=f'P{peak}_{window}';folder=OUT/'sweep'/label
            raw=deepcopy(base);raw['fuel_groups'][0]['peak_kW']=peak
            w=next(v for v in raw['openings'] if v['id']=='W1')
            if window=='closed':w['schedule']=[[0,0]]
            if window=='small':w.update(width_m=1.,bottom_m=1.,top_m=2.,offset_m=2.)
            if not analyze_only:
                if (folder/'execution.json').exists():raise ValueError('Existing measurement: use --analyze-only, no overwrite '+label)
                save(folder/'requested-scenario.json',raw)
                save(folder/'parameters.json',{'R1_peak_kW':peak,'R1_window':window,'late_definition':'relative among nine',
                     'window_small_center_preserved':True,'B1_sha256':base_hash})
                print('START '+label,flush=True);start=time.monotonic()
                try:simulate(raw,b4.ENGINE,folder);execution={'complete':True,'error':None}
                except (TimeoutError,RuntimeError,ValueError) as exc:execution={'complete':False,'error':str(exc)}
                execution.update(measured_wall_seconds=time.monotonic()-start,fixture_sha256=base_hash)
                save(folder/'execution.json',execution)
            report=summarize(folder);cases.append(report)
            print(label,json.dumps({k:report.get(k) for k in ('complete','error','total_wall_seconds','scenario_runs','rows','R1_600C_bracket_s')},ensure_ascii=False),flush=True)
            save(OUT/'sweep-progress.json',cases)
    positive=[];boundary=[]
    for c in cases:
        if not c.get('complete'):continue
        rows={v['room']:v for v in c['rows']};r2=rows['R2'];r3=rows['R3']
        if r2['ignition_s'] is not None:
            if r3['ignition_s'] is None:boundary.append(c)
        if all(rows[r]['ignition_s'] is not None and rows[r]['longest_positive_HRR_s']>=60 for r in ('R2','R3')):positive.append(c)
    delayed=[c for c in cases if c.get('complete') and c['rows'][1]['ignition_s'] is not None]
    b2=(boundary[0] if boundary else max(delayed,key=lambda c:c['rows'][1]['ignition_s'],default=None))
    b3=next((c for c in positive if c is not b2),None)
    selected={}
    for name,c in [('B2',b2),('B3',b3)]:
        if c:
            key=f"P{c['parameters']['R1_peak_kW']}_{c['parameters']['R1_window']}"
            raw=json.loads((OUT/'sweep'/key/'requested-scenario.json').read_text('utf-8'))
            dest=ROOT/f'fixtures/room_rule_benchmark_3room_{name.lower()}.json'
            if dest.exists() and json.loads(dest.read_text('utf-8'))!=raw:raise ValueError('Refusing to replace frozen '+name)
            save(dest,raw);selected[name]={'sweep_case':key,'path':str(dest),'sha256':digest(dest),
                'reference_search_complete':c['spread_search_complete'],'condition_consistent':c['condition_consistent']}
    report={'cases':cases,'selected':selected,'ready_for_comparison':len(selected)==2,'B1_sha256_unchanged':digest(b4.FIXTURE)==base_hash,
            'selection_rule':'User clarified B2: R2-only preferred, otherwise latest relative R2 ignition among all nine. B3 first both-source-HRR>=60s in peak/window order, distinct from B2.',
            'no_threshold_tuning':True,'standard_selected':None}
    save(OUT/'sweep-comparison.json',report);print('SELECTED',selected,'READY',report['ready_for_comparison'],flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--analyze-only',action='store_true');p.add_argument('--repair-reader-cases',action='store_true');a=p.parse_args()
    if a.repair_reader_cases:repair_reader_cases()
    sweep(a.analyze_only or a.repair_reader_cases)
