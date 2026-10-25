"""Compare unchanged native decks with isolated r2/r3 mixture implementations."""
import argparse,csv,json,re,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'simulation'))
from pyrocast_cfbt.native import execute,digest,interruption_status,read_diagnostic

def main():
    p=argparse.ArgumentParser();p.add_argument('--scope',choices=['small','stalled','off'],required=True)
    p.add_argument('--analyze-only',action='store_true')
    p.add_argument('--output-root',type=Path,default=ROOT/'simulation/results/mixture_r3c_20261023')
    p.add_argument('--engine',type=Path,default=ROOT/'simulation/build/mixture_r3c/cfbt/cfast-cfbt.exe')
    p.add_argument('--radiation-cache',action='store_true',help='Opt-in exact native RAD4 result reuse, no numerical approximation')
    p.add_argument('--wall-cache',action='store_true',help='Opt-in exact native wall derivative result reuse')
    a=p.parse_args();out=a.output_root.resolve()/a.scope;out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'simulation/results'/('mixture_r2_20261022/native_mix' if a.scope=='small' else 'floor_spread_20261022/r2_ventilated/run_01')
    old=ROOT/'simulation/build/mixture_r2/cfbt/cfast-cfbt.exe';new=a.engine.resolve()
    deck=(source/'case.in').read_text('ascii');side=(source/'case.cfbt').read_text('ascii')
    smooth=side.rsplit('/',1)[0]+' mixture_smooth_enabled=.TRUE.\n mixture_o2_width_vol=.01\n mixture_temperature_width_C=10\n mixture_fuel_width=.0001\n mixture_mixing_time_s=10\n/\n'
    duration=180. if a.scope=='small' else 3600.
    cases=[('old',old,deck,side),('smooth',new,deck,smooth)]
    if a.scope=='off':cases=[('off',new,deck,re.sub(r'bulk_enabled\s*=\s*\.TRUE\.', 'bulk_enabled=.FALSE.',side,flags=re.I))]
    if a.scope=='small':
        cases.insert(1,('compat',new,deck,side))
        cases.append(('half_step',new,deck.replace('MAX_TIME_STEP=0.2','MAX_TIME_STEP=0.1'),smooth))
        cases.append(('half_width',new,deck,smooth.replace('width_vol=.01','width_vol=.005').replace('width_C=10','width_C=5').replace('mixture_fuel_width=.0001','mixture_fuel_width=.00005')))
    report={'scope':a.scope,'source':str(source),'radiation_cache_enabled':a.radiation_cache,'wall_cache_enabled':a.wall_cache,'engines':{'old':digest(old),'new':digest(new)},
              'small_step_acceptance':{'max_T_difference_C':5.,'max_O2_difference_percentage_points':.5,'cumulative_bulk_relative_error':.03},
            'cases':{},'comparison_scope':'completed common output samples; incomplete runs are not completed scenarios'}
    reportpath=out/'comparison.json'
    if a.analyze_only:
        report=json.loads(reportpath.read_text('utf-8'))
        for name,engine,_,_ in cases:
            if name=='old':continue
            actual=(out/name/'case.cfbt').read_text('ascii')
            cache_on=bool(re.search(r'radiation_cache_enabled\s*=\s*\.TRUE\.',actual,re.I))
            if cache_on!=a.radiation_cache:raise ValueError('Requested analysis cache policy does not match saved input')
            wall_on=bool(re.search(r'wall_cache_enabled\s*=\s*\.TRUE\.',actual,re.I))
            if wall_on!=a.wall_cache:raise ValueError('Wall cache policy does not match saved input')
        report['radiation_cache_enabled']=a.radiation_cache
        report['wall_cache_enabled']=a.wall_cache
    folders={}
    for name,engine,text,settings in cases:
        if a.radiation_cache and name!='old':
            settings=settings.rsplit('/',1)[0]+' radiation_cache_enabled=.TRUE.\n/\n'
        if a.wall_cache and name!='old':
            settings=settings.rsplit('/',1)[0]+' wall_cache_enabled=.TRUE.\n/\n'
        folder=out/name
        folders[name]=folder
        if name=='old':
            previous=ROOT/'simulation/results/mixture_r3b_20261023'/a.scope
            saved=json.loads((previous/'comparison.json').read_text('utf-8'))
            prior=previous/'old'
            if saved['engines']['old']!=digest(old) or (prior/'case.in').read_text('ascii')!=text or (prior/'case.cfbt').read_text('ascii')!=settings:
                raise RuntimeError('Cannot reuse mismatched old baseline')
            report['cases'][name]={**saved['cases']['old'],'evidence_reused_from':str(prior)}
            folders[name]=prior
            continue
        if a.analyze_only:continue
        try:
            result=execute(engine,folder,text,settings,duration,60. if a.scope=='small' else 600.)
            record={'status':'completed',**result['run']}
        except (TimeoutError,RuntimeError,ValueError) as exc:
            record={'status':interruption_status(exc) if isinstance(exc,TimeoutError) else 'failed','error':str(exc)}
            state=folder/'execution-state.json'
            if state.exists():record['execution']=json.loads(state.read_text())
        report['cases'][name]=record
        reportpath.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
        print(json.dumps({name:record},ensure_ascii=False),flush=True)
        if a.scope=='small' and record['status']!='completed':break
    series={}
    for name,_,_,_ in cases:
        if name not in folders:continue
        path=folders[name]/'case_cfbt_rooms.csv'
        if not path.exists():continue
        rows=read_diagnostic(path)
        if any(abs(r['time_s']-round(r['time_s']))>1e-3 for r in rows if r['time_s']<=duration):
            raise ValueError('Output outside nominal comparison grid')
        series[name]={(float(round(r['time_s'])),r['room_index']):r for r in rows if r['time_s']<=duration}
        if rows:
            report['cases'][name]['peak_bulk_kW']=max(r['bulk_HRR_W'] for r in rows)/1000
            report['cases'][name]['peak_T_C']=max(r['T_upper_C'] for r in rows)
            summed={}
            for r in rows:
                if r['time_s']<=duration:summed[r['time_s']]=summed.get(r['time_s'],0.)+r['bulk_HRR_W']
            times=np.array(sorted(summed));q=np.array([summed[x] for x in times])
            report['cases'][name]['sampled_cumulative_bulk_MJ']=float(np.sum(np.diff(times)*(q[:-1]+q[1:])/2)/1e6)
        guard=folders[name]/'case_cfbt_reaction_steps.csv'
        if guard.exists():
            records=list(csv.DictReader(guard.read_text().splitlines()))
            if records:report['cases'][name]['accepted_step_diagnostics']=records[-1]
    comparisons={}
    for left,right in [('old','compat'),('old','smooth'),('smooth','half_step'),('smooth','half_width')]:
        if left not in series or right not in series:continue
        keys=series[left].keys()&series[right].keys()
        if not keys:continue
        d={f:max(abs(series[left][k][f]-series[right][k][f]) for k in keys)*scale
           for f,scale in [('T_upper_C',1),('T_lower_C',1),('o2_upper_vol',100),('k_upper_m_inv',1),('bulk_HRR_W',.001)]}
        d['common_until_s']=max(k[0] for k in keys)
        if right=='half_step':
            energies=[report['cases'][x]['sampled_cumulative_bulk_MJ'] for x in (left,right)]
            d['cumulative_bulk_relative_error']=abs(energies[0]-energies[1])/max(abs(energies[1]),1.e-9)
            d['accepted']=(all(report['cases'].get(n,{}).get('status')=='completed' for n in (left,right))
                and d['common_until_s']>=duration and max(d['T_upper_C'],d['T_lower_C'])<=5 and d['o2_upper_vol']<=.5
                and d['cumulative_bulk_relative_error']<=.03)
        comparisons[left+'_vs_'+right]=d
    report['differences']=comparisons
    report['time_alignment']='Nominal output grid, only native timestamp deviations <= 0.001 s accepted; no interpolated missing samples'
    report['difference_units']={'T_upper_C':'degC','T_lower_C':'degC',
        'o2_upper_vol':'percentage_points','k_upper_m_inv':'1/m',
        'bulk_HRR_W':'kW (converted difference, despite source field name)'}
    reportpath.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(comparisons,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
