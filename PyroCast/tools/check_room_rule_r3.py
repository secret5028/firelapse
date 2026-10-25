"""Corrected input and like-for-like legacy comparison, after D1-D4 reporting."""
import json,sys,time
import numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'simulation'));sys.path.insert(0,str(ROOT/'tools'))
from pyrocast_cfbt.spread import simulate
from test_room_rule import summarize
from diagnose_room_rule_r3 import OUT,ENGINE,save
from pyrocast_cfbt.native import read_native_csv

def finalize(report):
    for name,case in report['cases'].items():
        path=OUT/name/'result.json'
        if not case.get('complete') or not path.exists():continue
        result=json.loads(path.read_text('utf-8'))
        data=read_native_csv(Path(result['runs'][-1]['folder'])/'case_compartments.csv',600)[0]
        sources=[]
        for index,group in enumerate(result['scenario']['fuel_groups'],1):
            event=next((e for e in result['ignitions'] if e['group']==group['id']),None)
            row={'room':group['room'],'actual_source_peak_kW':float(max(data[f'HRR_{index}']))/1000,
                 'supply_peak_kW':float(max(data[f'PYROL_{index}']))*group['heat_of_combustion_kJ_kg']}
            if event:
                j=int(np.searchsorted(data['Time'],event['t_ign_s']))
                room_index=next(i for i,r in enumerate(result['scenario']['rooms'],1) if r['id']==group['room'])
                row.update(source_xyz=event['xyz'],sample_time_s=float(data['Time'][j]),
                           interface_m=float(data[f'HGT_{room_index}'][j]),
                           upper_O2_vol_percent=100*float(data[f'ULO2_{room_index}'][j]))
            sources.append(row)
        case['source_audit']=sources
        case['native_vent_peak_kW']={k:float(max(v))/1000 for k,v in data.items() if k.startswith('DJET_')}
        case['condition_consistent']=result.get('iteration',{}).get('condition_consistent')
    report['position_comparison_note']='Corrected fixture reuses legacy source/candidate positions at z=1.5 m. D1-D4 r2 sources are floor-centered at z=0 m. Thus corrected-vs-D1 runtime is not an isolated trigger change.'
    new=report['cases']['corrected'];old=report['cases']['legacy_same_gas_off']
    if new.get('complete') and old.get('complete'):
        reference={e['room']:e['t_ign_s'] for e in old['ignitions']}
        order=[e['room'] for e in new['ignitions']]==[e['room'] for e in old['ignitions']]
        comparisons=[{'room':e['room'],'new_observed_interval_s':e['time_interval_s'],
                      'legacy_s':reference.get(e['room']),
                      'certain_not_later':e['room'] in reference and e['time_interval_s'][1]<=reference[e['room']]} for e in new['event_intervals']]
        burning=set(new['actual_burning_rooms'])=={'R1','R2','R3'}
        report.update(order_matches=order,timing=comparisons,all_three_source_HRR_above_1kW=burning,
                      passed=order and len(comparisons)==2 and all(c['certain_not_later'] for c in comparisons) and old['spread_search_complete'] and burning)
    else:report['passed']=False
    save(OUT/'corrected-comparison.json',report)

def main():
    if '--analyze-only' in sys.argv:
        report=json.loads((OUT/'corrected-comparison.json').read_text('utf-8'))
        finalize(report);print(json.dumps(report,ensure_ascii=False));return
    diagnostics=json.loads((OUT/'comparison.json').read_text('utf-8'))
    if {r['id'] for r in diagnostics}!={'D1','D2','D3','D4'}:raise ValueError('All four diagnoses must be recorded first')
    raw=json.loads((ROOT/'simulation/results/adaptive_radiation_20261025/spread/native/scenario.json').read_text('utf-8'))
    raw['gas'].update(enabled=False,bulk_enabled=False,vent_gate_enabled=False,mixture_enabled=False,mixture_smooth_enabled=False)
    raw['engine_optimization']={'radiation_cache':False,'wall_cache':False,'adaptive_radiation':False}
    raw['spread'].update(run_timeout_s=600,wall_time_budget_s=1200,max_runs=3)
    historical=json.loads((ROOT/'simulation/results/adaptive_radiation_20261025/spread/native/result.json').read_text('utf-8'))
    locked_candidates={e['room']:e['candidate'] for e in historical['ignitions']}
    raw['room_fire_rule']={'enabled':True,'trigger_mode':'fuel_r3','preset':'standard','vent_cap_enabled':False,
                          'candidate_ids':locked_candidates}
    report={'supply_cap_default':False,'cap_reason':'D3 cap 6.85 MW exceeds existing 5 MW; no evidence to enable as a solution',
            'no_3f_run':True,'cases':{},'locked_candidate_ids':locked_candidates,
            'candidate_basis':'Validation fixture explicitly reuses historical ignition candidate positions/materials. Not an automatic prediction of the best target for an unseen building.'}
    for label in ('corrected','legacy_same_gas_off'):
        if label=='legacy_same_gas_off':raw['room_fire_rule']={'enabled':False};raw['spread']['wall_time_budget_s']=600
        dest=OUT/label;save(dest/'requested-scenario.json',raw)
        print('START '+label,flush=True)
        try:
            result=simulate(raw,ENGINE,dest)
            report['cases'][label]={'complete':result['simulation_complete_to_requested_horizon'],**summarize(result)}
            report['cases'][label]['event_intervals']=[{k:e.get(k) for k in ('room','t_ign_s','time_interval_s')} for e in result['ignitions']]
        except (TimeoutError,RuntimeError,ValueError) as exc:
            report['cases'][label]={'complete':False,'error':str(exc)}
        save(OUT/'corrected-comparison.json',report);print(label,json.dumps(report['cases'][label],ensure_ascii=False),flush=True)
    finalize(report)

if __name__=='__main__':main()
