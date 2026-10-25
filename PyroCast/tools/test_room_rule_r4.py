"""Frozen B1 input and bounded T0--T3 comparison. No engine edits or automatic selection."""
import argparse,json,re,sys,time
from copy import deepcopy
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'simulation'))
from pyrocast_cfbt.model import normalize
from pyrocast_cfbt.deck import candidates,active_fuels
from pyrocast_cfbt.room_rule import prepare
from pyrocast_cfbt.spread import simulate
from pyrocast_cfbt.native import read_native_csv,digest
ENGINE=ROOT/'simulation/build/adaptive_radiation_20261025/cfbt/cfast-cfbt.exe'
OUT=ROOT/'simulation/results/room_rule_r4_20261025'
FIXTURE=ROOT/'fixtures/room_rule_benchmark_3room.json'
MODES={'T1':'fuel_r4','T2':'ceiling_r4','T3':'floor_r4'}

def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),'utf-8')

def fixture():
    if FIXTURE.exists():return json.loads(FIXTURE.read_text('utf-8'))
    raw={'name':'room_rule_B1_frozen_r4','duration_s':1200,'output_step_s':5,'max_time_step_s':1,
         'rooms':[{'id':f'R{i+1}','origin_m':[5*i,0,0],'size_m':[5,5,2.7]} for i in range(3)],
         'openings':[],'fuel_groups':[],
         'gas':dict(enabled=False,bulk_enabled=False,vent_gate_enabled=False,mixture_enabled=False,mixture_smooth_enabled=False,jet_enabled=False),
         'flashover':{'enabled':False},'window_breakage':{'enabled':False},
         'spread':{'iteration_mode':'fixed_point','max_runs':3,'max_passes':3,'max_added_ignitions':2,
                   'run_timeout_s':600,'wall_time_budget_s':600},
         'benchmark_assumptions':{'primary_energy_MJ':10000,'secondary_peak_before_cap_kW':5000,
             'secondary_hrrpua_kW_m2':500,'alpha_fast_kW_s2':.0469,'secondary_ramp_s':60,
             'fuel_and_wall_material':'unchanged normalized project defaults; not a measured building',
             'windows':'full geometric area initially open as B1 explicitly specifies',
             'T0_supply':'same capped ramp/hold/decay curve as T1-T3, only ignition mechanism differs',
             'candidate_selection':'T1 first predeclared candidate in each room; no retrospective best-target selection'}}
    for i in range(1,4):
        raw['openings'].append({'id':f'W{i}','a':f'R{i}','b':'OUTSIDE','face':'FRONT','offset_m':1.6,
                                'width_m':1.8,'bottom_m':.9,'top_m':2.1,'schedule':[[0,1]],'kind':'window'})
        g={'id':'primary' if i==1 else f'reserve_R{i}','room':f'R{i}','position_m':[5*(i-1)+2.5,2.5,0],
           'energy_MJ':10000,'heat_of_combustion_kJ_kg':20000,'growth_kW_s2':.0469,
           'peak_kW':1500 if i==1 else 5000,'hrrpua_kW_m2':500,'fuel_area_m2':25}
        if i==1:g['initial_time_s']=0
        raw['fuel_groups'].append(g)
    # Internal openings first so T1 uses the existing target on the incoming-room side.
    raw['openings']=[{'id':f'D{i}{i+1}','a':f'R{i}','b':f'R{i+1}','face':'RIGHT','offset_m':2.05,
                       'width_m':.9,'bottom_m':0,'top_m':2.1,'schedule':[[0,1]]} for i in (1,2)]+raw['openings']
    model=normalize(raw);targets=candidates(model);groups={g['id']:g for g in model['fuel_groups']}
    for c in targets:
        c.update(fire_source_xyz=list(groups[c['group']]['position_m']),fire_source_base_m=0,
                 placement_basis='B1 fixed floor source independent of exposure sensor')
    model['explicit_candidates']=targets
    prepared,_=prepare({**deepcopy(model),'room_fire_rule':{'enabled':True,'trigger_mode':'fuel_r4'}})
    curves={g['id']:g for g in prepared['fuel_groups']}
    for g in model['fuel_groups']:
        if 'initial_time_s' not in g:
            g['room_rule_curve']=curves[g['id']]['room_rule_curve'];g['room_vent_cap']=curves[g['id']]['room_vent_cap']
    save(FIXTURE,model);return model

def longest(t,q,threshold=0):
    best=current=0.
    for i in range(1,len(t)):
        current=current+t[i]-t[i-1] if q[i]>threshold and q[i-1]>threshold else 0.
        best=max(best,current)
    return float(best)

def analyze(label):
    folder=OUT/label;report=json.loads((folder/'execution.json').read_text('utf-8'))
    if not (folder/'result.json').exists():return report
    r=json.loads((folder/'result.json').read_text('utf-8'));model=r['scenario'];t=np.array(r['time_s'])
    native_folder=Path(r['runs'][-1]['folder']);c=read_native_csv(native_folder/'case_compartments.csv',1200)[0]
    active=active_fuels(model,r['ignitions']);indices={g['id']:i for i,g in enumerate(active,1)}
    rows=[]
    for j,g in enumerate(model['fuel_groups'],1):
        room_index=next(i for i,room in enumerate(model['rooms'],1) if room['id']==g['room'])
        index=indices.get(g['id']);q=np.zeros(len(t)) if index is None else c[f'HRR_{index}']/1000
        event=next((e for e in r['ignitions'] if e['group']==g['id']),None)
        at=g.get('initial_time_s',event['t_ign_s'] if event else None)
        row={'room':g['room'],'ignition_s':at,'ignition_interval_s':event.get('time_interval_s') if event else None,
             'source_xyz':event['xyz'] if event else g['position_m'],'actual_source_peak_kW':float(max(q)),
             'longest_positive_HRR_s':longest(t,q),'longest_above_1kW_s':longest(t,q,1),
             'positive_total_s':float(sum(np.diff(t)*((q[:-1]>0)&(q[1:]>0)))),
             'native_vent_peak_kW':float(max(c.get(f'DJET_{room_index}',np.zeros(len(t)))))/1000}
        row['upper_C_max']=float(max(c[f'ULT_{room_index}']))
        if at is not None:
            row['at_ignition_interpolated']={name:float(np.interp(at,t,c[f'{key}_{room_index}']))*scale for name,key,scale in
                [('upper_C','ULT',1),('interface_m','HGT',1),('upper_O2_percent','ULO2',100),('lower_O2_percent','LLO2',100)]}
        rec=next((v for v in r.get('room_fire_rule',{}).get('rooms',[]) if v['group']==g['id']),None)
        if rec:row.update(sensor_xyz=rec['sensor_position_m'],sensor_setpoint=rec['setpoint'],sensor_criterion=rec['criterion'],sensor_max=rec['sensor_max'])
        elif event:row.update(sensor_xyz=event.get('surface_xyz'),sensor_criterion='existing Python plate + supplementary')
        if label=='T0':
            values=[x for v in r['candidates'] if v['group']==g['id'] and v.get('status')=='ok' for x in v['surface_C'] if x is not None]
            row['candidate_surface_max_C']=max(values) if values else None
        rows.append(row)
    stats=[]
    for run in r['runs']:
        status=(Path(run['folder'])/'case.status').read_text(errors='replace')
        match=re.search(r'STEPS\s*=\s*(\d+)',status)
        stats.append({'folder':run['folder'],'seconds':run['wall_seconds'],'steps_at_horizon':int(match[1]) if match else None})
    base=r.get('baseline_native',{}).get('run',{}).get('wall_seconds',0.)
    report.update(complete=r['simulation_complete_to_requested_horizon'],rows=rows,runs=stats,baseline_seconds=base,
                  scenario_native_seconds=sum(run['wall_seconds'] for run in r['runs'])-base,
                  total_wall_seconds=r['wall_seconds'],scenario_wall_seconds=r['wall_seconds']-base,
                  scenario_runs=len(stats)-(1 if base else 0),spread_search_complete=r['spread_search_complete'],
                  condition_consistent=r.get('iteration',{}).get('condition_consistent'),
                  engine_sha256=r['engine_sha256'])
    save(folder/'analysis.json',report);return report

def comparison():
    cases={p.parent.name:analyze(p.parent.name) for p in OUT.glob('T*/execution.json')}
    reference={v['room']:v['ignition_s'] for v in cases.get('T0',{}).get('rows',[])}
    eligible=[]
    for label,case in cases.items():
        if label=='T0':continue
        rows=[v for v in case.get('rows',[]) if v['room']!='R1']
        burning=len(rows)==2 and all(v['actual_source_peak_kW']>0 and v['longest_positive_HRR_s']>=60 for v in rows)
        timing=len(rows)==2 and all(v['ignition_s'] is not None and reference.get(v['room']) is not None and
                  (v['ignition_interval_s'][1] if v['ignition_interval_s'] else v['ignition_s'])<=reference[v['room']] for v in rows)
        case['criteria']={'both_secondary_burn_60s':burning,'not_later_than_T0':timing,
                          'complete_within_600_wall_s':case.get('complete',False) and case.get('scenario_wall_seconds',1e9)<600}
        if all(case['criteria'].values()):eligible.append(label)
    report={'fixture_sha256':digest(FIXTURE),'cases':cases,'eligible':eligible,
            'standard_selected':None,'approval_required':True,'eight_room_started':False,'floor_3F_started':False,
            'time_basis':'5 s outputs, native integer-second log brackets; positive-duration counts only intervals with both endpoints positive'}
    report['timing_comparison_available']=all(reference.get(r) is not None for r in ('R2','R3'))
    if not report['timing_comparison_available']:
        report['limitation']='T0 did not ignite both secondary rooms. No finite reference ignition times; the not-later criterion is not assessable, and no mode may be selected.'
    save(OUT/'comparison.json',report);return report

def main():
    p=argparse.ArgumentParser();p.add_argument('--case',choices=['all','T0','T1','T2','T3'],default='all');p.add_argument('--analyze-only',action='store_true');p.add_argument('--fixture-only',action='store_true');a=p.parse_args()
    model=fixture()
    if a.fixture_only:print(FIXTURE);return
    if not a.analyze_only:
        for label in ['T0','T1','T2','T3'] if a.case=='all' else [a.case]:
            folder=OUT/label
            if (folder/'execution.json').exists():raise ValueError('Existing measurement; use --analyze-only, do not silently overwrite: '+label)
            raw=deepcopy(model)
            if label!='T0':
                raw['room_fire_rule']={'enabled':True,'trigger_mode':MODES[label],'preset':'standard'}
                raw['spread']['wall_time_budget_s']=1200 # separate mandatory baseline + one scenario, 600 s each
            save(folder/'requested-scenario.json',raw);print('START '+label,flush=True);start=time.monotonic()
            try:
                simulate(raw,ENGINE,folder);execution={'complete':True,'error':None}
            except (TimeoutError,RuntimeError,ValueError) as exc:execution={'complete':False,'error':str(exc)}
            execution.update(measured_wall_seconds=time.monotonic()-start,fixture_sha256=digest(FIXTURE))
            save(folder/'execution.json',execution);print(label,json.dumps(analyze(label),ensure_ascii=False),flush=True)
    result=comparison();print('ELIGIBLE',result['eligible'],flush=True)

if __name__=='__main__':main()
