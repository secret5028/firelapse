"""r3 input-only diagnostics. Serial, bounded; no floor run or engine edits."""
import argparse,json,re,sys,time
from collections import Counter
from copy import deepcopy
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'simulation'))
from pyrocast_cfbt.native import execute,load_result,read_native_csv,digest
from pyrocast_cfbt.deck import make_deck,gas_sidecar
from pyrocast_cfbt.room_rule import supply_curve
from pyrocast_cfbt.openings import policy
OUT=ROOT/'simulation/results/room_rule_r3_20261025'
SOURCE=ROOT/'simulation/results/room_rule_20261025/spread/standard'
ENGINE=ROOT/'simulation/build/adaptive_radiation_20261025/cfbt/cfast-cfbt.exe'

def save(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),'utf-8')

def ventilation_cap(model,room,k=1.5):
    choices=[]
    for opening in model['openings']:
        if room not in (opening['a'],opening['b']) or opening.get('type')=='FLOOR':continue
        p=policy(model,opening)
        fraction=p['post_fraction'] if p else max(row[1] for row in opening.get('schedule',[[0,1]]))
        height=opening['top_m']-opening.get('bottom_m',0)
        area=opening['width_m']*height*fraction
        choices.append({'opening_id':opening['id'],'effective_area_m2':area,'height_m':height,
                        'fraction':fraction,'A_sqrt_H':area*np.sqrt(height)})
    best=max(choices,key=lambda c:c['A_sqrt_H']) if choices else None
    return {'room':room,'opening':best,'k':k,'cap_kW':k*1500*best['A_sqrt_H'] if best else 0.,
            'basis':'largest one geometric opening factor, future maximum/post-breakage fraction; numerical supply cap, not oxygen availability'}

def audit_inputs():
    oldpath=ROOT/'simulation/results/adaptive_radiation_20261025/spread/native/scenario.json'
    old=json.loads(oldpath.read_text('utf-8'));new=json.loads((SOURCE/'scenario.json').read_text('utf-8'))
    keys=('rooms','openings','duration_s','output_step_s','max_time_step_s','criteria','material','wall_material')
    oldresult=json.loads((oldpath.parent/'result.json').read_text('utf-8'))
    report={'old_path':str(oldpath),'old_sha256':digest(oldpath),'r2_sha256':digest(SOURCE/'scenario.json'),
        'equal_sections':{key:old.get(key)==new.get(key) for key in keys},
        'old_gas':old['gas'],'new_gas':new['gas'],'old_events':oldresult['ignitions'],
        'fuel_budget_equal':[{ 'id':g['id'],'energy_equal':g['energy_MJ']==next(x for x in new['fuel_groups'] if x['id']==g['id'])['energy_MJ'],
                              'peak_equal':g['peak_kW']==next(x for x in new['fuel_groups'] if x['id']==g['id'])['peak_kW']} for g in old['fuel_groups']],
        'interpretation':'Same geometry/fuel budgets, but gas feedback/CO reserve, target/thermal response and secondary HRR curves differ. Timing difference cannot be attributed to the trigger alone.'}
    save(OUT/'input-audit.json',report)
    return new

def analyze(folder,model,name,run=None,error=None):
    text=(folder/'case.status').read_text(errors='replace') if (folder/'case.status').exists() else ''
    report={'id':name,'complete':run is not None,'run':None if run is None else run['run'],'error':error,
        'native_status':text.strip(),'engine_sha256':digest(ENGINE),'input_sha256':digest(folder/'case.in')}
    m=re.search(r'T\s*=\s*([\d.Ee+-]+).*DT\s*=\s*([\d.Ee+-]+).*STEPS\s*=\s*(\d+)',text)
    if m:report.update(native_progress_s=float(m[1]),last_dt_s=float(m[2]),total_steps=int(m[3]))
    dt=[];n=0;phases={'before_secondary':[],'after_secondary':[]};components=Counter();take_component=False;current_time=0.
    log=(folder/'case.log').read_text(errors='replace')
    logtimes=[float(x) for x in re.findall(r'ignited at\s+(\d+) seconds',log)]
    first_secondary=min(logtimes,default=278.)
    with (folder/'execution.log').open(errors='replace') as f:
        for line in f:
            match=re.search(r'Returned from dassl at T =\s*([\d.Ee+-]+)\s*,\s*dt =\s*([\d.Ee+-]+)',line)
            if match:
                n+=1;value=float(match[2]);current_time=float(match[1])
                if 0<current_time<=600 and value>0:
                    dt.append(value);phases['before_secondary' if current_time<first_secondary else 'after_secondary'].append(value)
            if take_component and 0<current_time<=600:components[line.strip()]+=1
            take_component='Solution component with the greatest error is' in line
    report['dt_statistics']={'positive_reported_dt_count':len(dt),'dassl_returns_logged':n,
        'min_s':min(dt) if dt else None,'median_s':float(np.median(dt)) if dt else None,
        'basis':'native DIAG DASSL_DEBUG_PRINT reported dt (previous step variable at return, includes event-retry context), not an independently instrumented accepted-step distribution',
        'logging_cost':'same native debug output enabled in D1-D4; wall time includes diagnostic I/O'}
    report['dt_by_phase']={phase:{'count':len(values),'median_s':float(np.median(values)) if values else None} for phase,values in phases.items()}
    report['largest_error_component_counts']=components.most_common(5)
    # Analyze only flushed records common to standard CSVs, never publish a partial playback.
    data={}
    for kind in ('zone','compartments','devices','vents'):
        data[kind]=read_native_csv(folder/('case_'+kind+'.csv'),600)[0]
    horizon=min(d['Time'][-1] for d in data.values());report['common_output_horizon_s']=float(horizon)
    c=data['compartments'];t=c['Time'];mask=t<=horizon;report['rooms']=[]
    jet=sum((v[mask] for key,v in c.items() if key.startswith('DJET_')),np.zeros(sum(mask)))
    report['native_vent_combustion_MJ']=float(np.trapezoid(jet,t[mask])/1e6)
    report['HRR_scope']='per-fire HRR includes its native plume reactions; native DJET reported separately; not a complete building energy balance'
    for i,g in enumerate(model['fuel_groups'],1):
        ri=next(j for j,r in enumerate(model['rooms'],1) if r['id']==g['room'])
        hit=np.flatnonzero(c['IGN_'+str(i)][mask]>.5)
        curve=g.get('room_rule_curve');qcap=curve['Q_max_kW'] if curve else g['peak_kW']
        actual=c[f'HRR_{i}'][mask]/1000;pyrol=c[f'PYROL_{i}'][mask]*g['heat_of_combustion_kJ_kg']
        times=t[mask]
        report['rooms'].append({'room':g['room'],'ignition_bracket_s':None if not len(hit) else [float(times[max(0,hit[0]-1)]),float(times[hit[0]])],
            'Q_supply_cap_kW':qcap,'actual_peak_kW':float(max(actual)),'supply_peak_kW':float(max(pyrol)),
            'actual_HRR_MJ':float(np.trapezoid(actual,times)/1000),'supplied_MJ':float(np.trapezoid(pyrol,times)/1000),
            'upper_O2_min_vol_percent':100*float(min(c[f'ULO2_{ri}'][mask])),
            'lower_O2_min_vol_percent':100*float(min(c[f'LLO2_{ri}'][mask]))})
        save(folder/(g['room']+'-series.json'),{'time_s':times.tolist(),'actual_HRR_kW':actual.tolist(),'supply_kW':pyrol.tolist(),
             'upper_O2_vol_percent':(100*c[f'ULO2_{ri}'][mask]).tolist(),'lower_O2_vol_percent':(100*c[f'LLO2_{ri}'][mask]).tolist()})
    save(folder/'diagnosis.json',report);return report

def main():
    p=argparse.ArgumentParser();p.add_argument('--case',choices=['D1','D2','D3','D4','all'],default='all');p.add_argument('--analyze-only',action='store_true');a=p.parse_args()
    model=audit_inputs();rawdeck=(SOURCE/'run_00/case.in').read_text('ascii');side=(SOURCE/'run_00/case.cfbt').read_text('ascii')
    for name in ['D1','D2','D3','D4'] if a.case=='all' else [a.case]:
        current=deepcopy(model);deck=rawdeck;caps=[]
        if name!='D1':
            events=[]
            for g,at in zip(current['fuel_groups'][1:],[278.,333.]):
                g.pop('room_rule_trigger')
                events.append({'group':g['id'],'room':g['room'],'t_ign_s':at,'xyz':g['position_m']})
                if name=='D3':
                    cap=ventilation_cap(current,g['room']);caps.append(cap)
                    if cap['cap_kW']<=0:raise ValueError('No positive vent factor')
                    g['peak_kW']=min(g['peak_kW'],cap['cap_kW'])
                if name in ('D3','D4'):
                    rule={**current['room_fire_rule'],'ramp_s':180 if name=='D4' else 60}
                    room=next(r for r in current['rooms'] if r['id']==g['room'])
                    g['room_rule_curve']=supply_curve(g,room['size_m'][0]*room['size_m'][1],rule)
            deck=make_deck(current,events,current['explicit_candidates'])
        deck+="&DIAG DASSL_DEBUG_PRINT='ON' /\n"
        folder=OUT/name;folder.mkdir(parents=True,exist_ok=True);save(folder/'scenario.json',current);save(folder/'supply-caps.json',caps)
        print('START '+name,flush=True);started=time.monotonic();r=None;error=None
        try:
            if a.analyze_only:
                if (folder/'case.in').read_text('ascii')!=deck:raise ValueError('Analysis input changed')
                saved=json.loads((folder/'completed.json').read_text('utf-8')) if (folder/'completed.json').exists() else None
                if saved:r=load_result(folder,600,saved['run'])
                else:error=json.loads((folder/'execution-state.json').read_text('utf-8')).get('reason','incomplete')
            else:r=execute(ENGINE,folder,deck,side,600,600,stall_timeout_s=90)
        except (TimeoutError,RuntimeError,ValueError) as exc:error=str(exc)
        measured=time.monotonic()-started
        if a.analyze_only:measured=json.loads((folder/'diagnosis.json').read_text('utf-8'))['measured_wall_seconds']
        report=analyze(folder,current,name,r,error);report['measured_wall_seconds']=measured
        save(folder/'diagnosis.json',report)
        print(json.dumps({k:report[k] for k in ('id','complete','error','measured_wall_seconds','dt_statistics','rooms')},ensure_ascii=False),flush=True)
    results=[json.loads(p.read_text('utf-8')) for p in sorted(OUT.glob('D*/diagnosis.json'))]
    save(OUT/'comparison.json',results)

if __name__=='__main__':main()
