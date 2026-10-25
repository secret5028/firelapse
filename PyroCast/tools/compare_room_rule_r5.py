"""B1/B2/B3 x T0/T1/T2/T4, exact-output reuse and no automatic standard selection."""
import argparse,json,sys,time
from copy import deepcopy
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'simulation'));sys.path.insert(0,str(ROOT/'tools'))
import test_room_rule_r4 as b4
from test_room_rule_r5 import OUT,save
from pyrocast_cfbt.spread import simulate
from pyrocast_cfbt.native import read_native_csv,digest
from pyrocast_cfbt.reuse import prime_completed
from pyrocast_cfbt.deck import gas_sidecar,active_fuels
from pyrocast_cfbt.room_rule import prepare

def analyze(folder):
    b4.OUT=folder.parent;r=b4.analyze(folder.name)
    if not (folder/'result.json').exists():return r
    result=json.loads((folder/'result.json').read_text('utf-8'))
    r.update(error=result.get('error'),terminated=result['terminated'])
    r['complete']=result['simulation_complete_to_requested_horizon'] and result.get('error') is None
    r['recorded_native_seconds_excluding_baseline']=r['scenario_native_seconds']
    r['measured_this_invocation_seconds']=r['measured_wall_seconds']
    r['cached_native_jobs']=sum(bool(v.get('cache_hit')) for v in result['runs'])
    # Cached job durations are original measurements, not time spent re-reading them.
    r['scenario_wall_seconds']=None if r['cached_native_jobs'] else r['scenario_wall_seconds']
    r['total_wall_seconds_this_invocation']=result['wall_seconds']
    data=read_native_csv(Path(result['runs'][-1]['folder'])/'case_compartments.csv',1200)[0]
    active=active_fuels(result['scenario'],result['ignitions']);indices={g['id']:i for i,g in enumerate(active,1)}
    for row,g in zip(r['rows'],result['scenario']['fuel_groups']):
        event=next((e for e in result['ignitions'] if e['group']==g['id']),None)
        idx=indices.get(g['id']);hit=np.flatnonzero(data[f'HRR_{idx}']>0) if idx else []
        row['first_actual_positive_HRR_s']=float(data['Time'][hit[0]]) if len(hit) else None
        row['prescribed_supply_start_s']=event.get('prescribed_supply_start_s',event['t_ign_s']) if event else g.get('initial_time_s')
        if event and event.get('transition_assumption'):
            row.update(parent_room=event['trigger_room'],parent_trigger_s=event['t_ign_s'],
                       supply_start_interval_s=event['prescribed_supply_start_interval_s'])
    save(folder/'analysis.json',r);return r

def main():
    p=argparse.ArgumentParser();p.add_argument('--analyze-only',action='store_true');a=p.parse_args()
    sweep=json.loads((OUT/'sweep-comparison.json').read_text('utf-8'))
    if not sweep['ready_for_comparison']:raise ValueError('Both B2 and B3 must be frozen before comparison')
    cases={};modes={'T1':'fuel_r4','T2':'ceiling_r4','T4':'parent_r5'}
    for benchmark in ('B1','B2','B3'):
        path=b4.FIXTURE if benchmark=='B1' else Path(sweep['selected'][benchmark]['path'])
        for trigger in ('T0','T1','T2','T4'):
            folder=OUT/'compare'/benchmark/trigger
            if not a.analyze_only:
                if (folder/'execution.json').exists():raise ValueError('Existing case; analyze only '+str(folder))
                raw=json.loads(path.read_text('utf-8'))
                source=None
                if benchmark=='B1' and trigger!='T4':source=ROOT/'simulation/results/room_rule_r4_20261025'/trigger
                if benchmark!='B1' and trigger=='T0':source=OUT/'sweep'/sweep['selected'][benchmark]['sweep_case']
                if trigger!='T0':
                    raw['room_fire_rule']={'enabled':True,'trigger_mode':modes[trigger],'preset':'standard'}
                    raw['spread']['wall_time_budget_s']=1200
                if source:
                    prepared=prepare(raw)[0] if trigger!='T0' else raw
                    side=gas_sidecar(prepared)
                    for run in sorted(source.iterdir()):
                        if run.is_dir() and (run/'completed.json').exists():
                            engine=ROOT/'simulation/build/baseline/cfast-baseline.exe' if run.name=='baseline_native' else b4.ENGINE
                            prime_completed(run,folder/run.name,engine,side,1200)
                save(folder/'requested-scenario.json',raw)
                print('START',benchmark,trigger,'reuse',str(source) if source else None,flush=True);start=time.monotonic()
                try:simulate(raw,b4.ENGINE,folder);execution={'complete':True,'error':None}
                except (TimeoutError,RuntimeError,ValueError) as exc:execution={'complete':False,'error':str(exc)}
                execution.update(measured_wall_seconds=time.monotonic()-start,fixture_sha256=digest(path),reused_source=str(source) if source else None)
                save(folder/'execution.json',execution)
            r=analyze(folder);cases[benchmark+'_'+trigger]=r
            print(benchmark,trigger,json.dumps({k:r.get(k) for k in ('complete','error','recorded_native_seconds_excluding_baseline','rows')},ensure_ascii=False),flush=True)
            save(OUT/'comparison-progress.json',cases)
    eligible=[];criteria={}
    for trigger in ('T1','T2','T4'):
        negative=cases['B1_'+trigger];positive=[cases[b+'_'+trigger] for b in ('B2','B3')]
        neg=bool(negative.get('complete') and len(negative.get('rows',[]))==3 and all(v['ignition_s'] is None for v in negative['rows'][1:]))
        pos={b:bool(c.get('complete') and len(c.get('rows',[]))==3 and all(v['longest_positive_HRR_s']>=60 for v in c['rows'][1:])) for b,c in zip(('B2','B3'),positive)}
        criteria[trigger]={'negative_B1_no_transition':neg,'positive_burn_60s':pos}
        ok=neg and all(pos.values())
        if ok:eligible.append(trigger)
    save(OUT/'comparison.json',{'cases':cases,'criteria':criteria,'eligible_new_modes':eligible,'standard_selected':None,
         'user_approval_required':True,'eight_room_started':False,'floor_3F_started':False,
         'time_basis':'T4 trigger time and prescribed supply start are separate; positive HRR onset observed on 5s grid; reused durations remain original native measurements'})
    print('ELIGIBLE',eligible,flush=True)

if __name__=='__main__':main()
