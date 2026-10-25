"""Bounded experiment: identical physical settings, optional mature-room radiation."""
import argparse,csv,json,re,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'simulation'))
from pyrocast_cfbt.native import execute,digest,read_diagnostic,load_result
from pyrocast_cfbt.model import normalize
from pyrocast_cfbt.deck import candidates,gas_sidecar,make_deck,active_fuels
from pyrocast_cfbt.spread import simulate,assess,classify
from pyrocast_cfbt.flashover import proposals as fo_proposals

OUT=ROOT/'simulation/results/adaptive_radiation_20261025'
ENGINE=ROOT/'simulation/build/adaptive_radiation_20261025/cfbt/cfast-cfbt.exe'
OLD=ROOT/'simulation/build/mixture_r3f_cache/cfbt/cfast-cfbt.exe'

def diagnostics(folder):
    path=folder/'case_cfbt_adaptive.csv'
    if not path.exists():return {}
    rows=read_diagnostic(path);last={int(r['room_index']):r for r in rows}
    return {'rooms':[{'room_index':k,**{name:r[name] for name in ('builds','fallbacks','rejected','approx_calls','blend_calls','full_calls','max_closure_W')}} for k,r in last.items() if r['builds'] or r['rejected']],
            'total_approx_calls':sum(r['approx_calls'] for r in last.values()),
            'total_blend_calls':sum(r['blend_calls'] for r in last.values()),
            'max_closure_W':max((r['max_closure_W'] for r in last.values()),default=0.)}

def differences(a,b):
    left={(r['time_s'],r['room_index']):r for r in a['rooms']}
    right={(r['time_s'],r['room_index']):r for r in b['rooms']}
    if left.keys()!=right.keys():raise ValueError('Incomplete/misaligned room samples')
    delta={k:max(abs(left[t][k]-right[t][k])*scale for t in left) for k,scale in
           [('T_upper_C',1),('T_lower_C',1),('o2_upper_vol',100),('k_upper_m_inv',1),('bulk_HRR_W',.001)]}
    energy=[]
    for result in (a,b):
        sums={}
        for r in result['rooms']:sums[r['time_s']]=sums.get(r['time_s'],0.)+r['bulk_HRR_W']
        t=np.array(sorted(sums));q=np.array([sums[x] for x in t])
        energy.append(float(np.sum(np.diff(t)*(q[:-1]+q[1:])*.5)/1e6))
    delta['bulk_MJ']=energy
    delta['bulk_relative_difference']=abs(energy[1]-energy[0])/max(abs(energy[0]),1e-6)
    return delta

def sidecar(side,on):
    return side if not on else side.rsplit('/',1)[0]+' adaptive_radiation_enabled=.TRUE.\n/\n'

def main():
    p=argparse.ArgumentParser();p.add_argument('scope',choices=['compat','floor','spread','controlled'])
    p.add_argument('--analyze-only',action='store_true');a=p.parse_args()
    folder=OUT/a.scope;folder.mkdir(parents=True,exist_ok=True)
    report={'scope':a.scope,'engine_sha256':digest(ENGINE),'cases':{},
            'acceptance':{'max_temperature_difference_C':20,'max_oxygen_difference_pp':.5,'max_bulk_relative_difference':.05,
                          'ignition_rooms_must_match':True,'max_ignition_time_difference_s':10},
            'production_enabled':False}
    path=folder/'comparison.json'
    if a.analyze_only:report=json.loads(path.read_text('utf-8'))
    native={}
    if a.scope in ('compat','floor','controlled'):
        source=ROOT/('simulation/results/mixture_r3f_cache_20261023/small/smooth' if a.scope=='compat' else
                     'simulation/results/mixture_r3f_cache_20261023/floor60/run_02')
        duration=180 if a.scope=='compat' else 3600
        if a.scope=='controlled':
            # Explicit two-fire numerical fixture, not a predicted spread claim.
            model=json.loads((ROOT/'simulation/examples/three_rooms.json').read_text('utf-8'))
            model.update(duration_s=600,output_step_s=5,max_time_step_s=1)
            model['fuel_groups']=[g for g in model['fuel_groups'] if g['id'] in ('primary','reserve_R2')]
            for g in model['fuel_groups']:
                room=next(r for r in model['rooms'] if r['id']==g['room'])
                g.update(initial_time_s=0,position_m=[room['origin_m'][0]+2,2,0],energy_MJ=10000,peak_kW=500,growth_kW_s2=100)
            model['openings']=[{'id':'OUT_'+r['id'],'a':r['id'],'b':'OUTSIDE','face':'RIGHT','offset_m':.5,'width_m':3,'top_m':2.8,
                               'schedule':[[0,1],[399,1],[400,.5]] if r['id']=='R1' else [[0,1]]} for r in model['rooms']]
            model['gas'].update(mixture_enabled=True,mixture_smooth_enabled=True,vent_gate_enabled=False,activation_J_mol=0,mixture_mixing_time_s=10)
            model['engine_optimization']={'radiation_cache':True,'wall_cache':True}
            model=normalize(model);duration=600
            deck=make_deck(model,[],candidates(model),[]);side=gas_sidecar(model)
            (folder/'scenario.json').write_text(json.dumps(model,indent=2),'utf-8')
            report['source']='controlled numerical fixture: two prescribed 500 kW fires, vent change at 400s; not predicted spread'
        else:
            deck=(source/'case.in').read_text('ascii');side=(source/'case.cfbt').read_text('ascii')
            report['source']=str(source);report['input_sha256']=digest(source/'case.in')
        for name in ('native','adaptive'):
            dest=folder/name
            if a.analyze_only:
                if report['cases'].get(name,{}).get('status')=='completed':native[name]=load_result(dest,duration,{})
                continue
            try:
                result=execute(ENGINE,dest,deck,sidecar(side,name=='adaptive'),duration,1200 if a.scope=='floor' else 90)
                native[name]=result
                report['cases'][name]={'status':'completed',**result['run'],'adaptive':diagnostics(dest)}
            except (RuntimeError,ValueError,TimeoutError) as exc:
                report['cases'][name]={'status':'failed','error':str(exc)}
            path.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
            print(json.dumps({name:report['cases'][name]},ensure_ascii=False),flush=True)
        if a.scope=='compat' and 'native' in native:
            old=load_result(source,duration,{})
            report['disabled_vs_r3f']=differences(old,native['native'])
        if a.scope=='floor' and len(native)==2:
            scenario=normalize(json.loads((source.parent/'scenario.json').read_text('utf-8')))
            result=json.loads((source.parent/'result.json').read_text('utf-8'))
            # The run_02 deck is the recorded proposed schedule, not the last
            # completed schedule. Recover events from its original input audit.
            report['propagation_note']='Frozen 10-fire schedule. New candidate assessment is below; this is not a converged full-floor spread search.'
            events=[e for e in result['pending_candidates'] if e.get('kind')!='fo_transition']
            transitions=[e for e in result['pending_candidates'] if e.get('kind')=='fo_transition']
            targets=candidates(scenario)
            if make_deck(scenario,events,targets,transitions)!=deck:
                raise ValueError('Recovered propagation schedule does not reproduce frozen input')
            report['existing_committed_rooms']=[e['room'] for e in events]
            report['propagation']={}
            report['actual_burning']={};tags={}
            for name,run in native.items():
                decisions,views,states=assess(scenario,run,targets,events,transitions,reevaluate=True)
                fo=fo_proposals(scenario,run,states,events,transitions,views)
                tags[name]=classify(scenario,run,states,events,views,transitions)
                q={r['id']:np.zeros(len(run['zone']['Time'])) for r in scenario['rooms']}
                for index,group in enumerate(active_fuels(scenario,events),1):q[group['room']]+=run['zone'][f'HRR_{index}']
                observed=[rid for rid,value in q.items() if np.any(value>1000)]
                simultaneous=sum((value>1000 for value in q.values()),np.zeros(len(run['zone']['Time']),int))
                report['actual_burning'][name]={'ever_rooms':observed,'peak_concurrent_rooms':int(np.max(simultaneous))}
                report['propagation'][name]={
                    'ignitions':[{k:e[k] for k in ('group','room','t_ign_s')} for e in decisions],
                    'fo_transitions':[{k:e[k] for k in ('room','t_ign_s')} for e in fo],
                    'invalid_or_unevaluated_targets':sum(v.get('status') in ('invalid_exposure','unevaluated') for v in views)}
            report['other_condition_differences']={k:sum(int(np.sum(tags['native'][rid]['tags'][k]!=tags['adaptive'][rid]['tags'][k])) for rid in tags['native']) for k in ('RO','BD_POTENTIAL','VENT_FLAME','RAPID')}
            report['event_assessment_pending']=False
            from compare_mixture_conditions import load as condition_load
            condition={name:condition_load(folder/name,duration,scenario['criteria']) for name in native}
            report['condition_differences']={k:sum(condition['native'][p][k]!=condition['adaptive'][p][k] for p in condition['native']) for k in ('fo','fgi')}
            report['condition_room_sets']={k:{name:sorted({row['room'] for row in samples.values() if row[k]}) for name,samples in condition.items()} for k in ('fo','fgi')}
    else:
        model=json.loads((ROOT/'simulation/examples/three_rooms.json').read_text('utf-8'))
        model.update(duration_s=600,output_step_s=5,max_time_step_s=1)
        model['gas'].update(mixture_enabled=True,mixture_smooth_enabled=True,vent_gate_enabled=False,activation_J_mol=0,
                            mixture_mixing_time_s=10)
        model['engine_optimization']={'radiation_cache':True,'wall_cache':True}
        model['spread']={'iteration_mode':'fixed_point','max_runs':3,'max_passes':3,'run_timeout_s':120,
                         'wall_time_budget_s':360,'quadrature_n':4,'plate_nodes':17,'plate_dt_s':.2}
        # Test fixture changes fuel supply, not the ignition threshold (369 C).
        model['fuel_groups']=[g for g in model['fuel_groups'] if g['id']!='reserve_R1']
        for g in model['fuel_groups']:
            g.update(energy_MJ=10000,growth_kW_s2=2,peak_kW=5000)
        for name in ('native','adaptive'):
            dest=folder/name
            if a.analyze_only:continue
            model['engine_optimization']['adaptive_radiation']=name=='adaptive'
            model=normalize(model)
            dest.mkdir(exist_ok=True)
            (dest/'scenario.json').write_text(json.dumps(model,indent=2),'utf-8')
            started=time.monotonic()
            try:
                result=simulate(model,ENGINE,dest)
                record={k:result[k] for k in ('terminated','error','ignitions','fo_transitions','spread_search_complete','attempted_runs_count')}
                record['wall_seconds']=time.monotonic()-started
                record['native_seconds']=sum(r['wall_seconds'] for r in result['runs'] if not r.get('cache_hit'))
                record['adaptive']={d.name:diagnostics(d) for d in dest.glob('run_*') if d.is_dir()}
                report['cases'][name]=record
            except (RuntimeError,ValueError,TimeoutError) as exc:report['cases'][name]={'status':'failed','error':str(exc)}
            path.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
            print(json.dumps({name:report['cases'][name]},ensure_ascii=False),flush=True)
    if len(native)==2:report['differences']=differences(native['native'],native['adaptive'])
    if a.scope=='spread' and len(report['cases'])==2:
        report['propagation']={name:{'ignitions':r.get('ignitions',[]),'fo_transitions':r.get('fo_transitions',[])} for name,r in report['cases'].items()}
        for name in ('native','adaptive'):
            if (folder/name/'result.json').exists():
                final=json.loads((folder/name/'result.json').read_text('utf-8'))
                run=final['runs'][-1]
                native[name]=load_result(Path(run['folder']),600,run)
        if len(native)==2:report['differences']=differences(native['native'],native['adaptive'])
    if 'propagation' in report:
        schedules={name:{e['group']:e['t_ign_s'] for e in p['ignitions']} for name,p in report['propagation'].items()}
        x,y=schedules['native'],schedules['adaptive']
        report['ignition_comparison']={'same_groups':x.keys()==y.keys(),
            'max_time_difference_s':max((abs(x[k]-y[k]) for k in x.keys()&y.keys()),default=0.),
            'native_only':sorted(x.keys()-y.keys()),'adaptive_only':sorted(y.keys()-x.keys()),
            'same_order':sorted(x,key=x.get)==sorted(y,key=y.get)}
        fo={name:{e['room']:e['t_ign_s'] for e in p['fo_transitions']} for name,p in report['propagation'].items()}
        x,y=fo['native'],fo['adaptive']
        report['fo_proposal_comparison']={'same_rooms':x.keys()==y.keys(),
            'max_time_difference_s':max((abs(x[k]-y[k]) for k in x.keys()&y.keys()),default=0.)}
    if 'differences' in report:
        d=report['differences'];ic=report.get('ignition_comparison',{})
        physical=(max(d['T_upper_C'],d['T_lower_C'])<=20 and d['o2_upper_vol']<=.5 and d['bulk_relative_difference']<=.05)
        propagation=(ic.get('same_groups',False) and ic.get('same_order',False) and ic.get('max_time_difference_s',1e9)<=10)
        condition_rooms=all(v['native']==v['adaptive'] for v in report.get('condition_room_sets',{}).values())
        fo=report.get('fo_proposal_comparison',{})
        fo_ok=fo.get('same_rooms',False) and fo.get('max_time_difference_s',1e9)<=10
        actual=report.get('actual_burning',{})
        actual_ok=not actual or actual['native']==actual['adaptive']
        valid=physical and propagation and condition_rooms and fo_ok and actual_ok
        report['comparison_accepted']=valid
        report['selected_mode']='native'
        report['selection_reason']='Experimental only. Baseline retained unless completed propagation and speed checks both pass.'
        if valid:
            t=[report['cases'][name].get('native_seconds',report['cases'][name].get('wall_seconds',0)) for name in ('native','adaptive')]
            report['runtime_ratio_adaptive_over_native']=t[1]/t[0] if t[0] else None
            complete=(a.scope=='spread' and all(r.get('spread_search_complete') for r in report['cases'].values()))
            activated=any((r.get('adaptive',{}).get('total_approx_calls',0)>0) for r in report['cases'].values()) if a.scope!='spread' else any(
                d.get('total_approx_calls',0)>0 for r in report['cases'].values() for d in r.get('adaptive',{}).values())
            report['reduced_operator_exercised']=activated
            if t[0] and t[1]<t[0] and complete and activated:
                report.update(selected_mode='adaptive_candidate',selection_reason='Completed local propagation comparison passed; production still disabled pending larger verification.')
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print(str(path),flush=True)

if __name__=='__main__':main()
