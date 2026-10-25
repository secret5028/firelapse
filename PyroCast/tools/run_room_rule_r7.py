"""r7 fixed input tests. No retries, no solver changes, isolated result folders."""
import argparse,json,math,re,sys,threading
from copy import deepcopy
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'simulation'));sys.path.insert(0,str(ROOT/'tools'))
from pyrocast_cfbt.room_rule_r7 import prepare
from pyrocast_cfbt.deck import make_deck
from pyrocast_cfbt.native import execute,load_result,digest,NativeRunInterrupted
from run_room_rule_r6a_floor import observe,ENGINE,SOURCE
from test_room_rule_r4 import save
OUT=ROOT/'simulation/results/room_rule_r7_20261025'

def analyze(model,native,manifest,baseline):
    report=observe(model,native,manifest,baseline)
    report.pop('target_16_rooms_met',None);report.pop('target_basis',None)
    parents=manifest['parents'];passing=set(manifest['graph']['passing_rooms'])
    for row in report['rows']:
        rid=row['cell'];depth=0;fire_depth=0;cursor=rid
        while parents.get(cursor):
            cursor=parents[cursor]['room'];depth+=1;fire_depth+=cursor not in passing
        row.update(graph_depth=depth,combustible_generation=fire_depth,
            sensor_threshold_C=next(g for g in model['fuel_groups'] if g['room']==rid).get('room_rule_trigger',{}).get('setpoint'),
            supply_details=manifest['supplies'].get(rid))
        if not baseline and row['parent'] and row['parent']['room'] in passing and row['trigger_estimate_s'] is None:
            row['status']='복도 미가열로 전이 정지'
    report['fallback_sensors']=manifest['fallback_sensors']
    report['passage_stops']=[r for r in report['rows'] if r['status']=='복도 미가열로 전이 정지']
    report['threshold_note']='Native triggers use strict exceedance; 5s samples bracket event time, not exact time'
    report['no_room_count_acceptance_target']=True
    return report

def run_case(folder,model,targets,manifest,baseline=False,timeout=1800,display_root=None):
    if (folder/'planned-execution.json').exists():raise ValueError('Already attempted; no automatic rerun: '+str(folder))
    deck=make_deck(model,[],targets);assert '&CFBT' not in deck
    save(folder/'scenario.json',model);save(folder/'rule_manifest.json',manifest)
    snapshots=[];stop=threading.Event()
    def monitor():
        previous=None
        while not stop.wait(1):
            try:
                line=(folder/'case.status').read_text(errors='replace').splitlines()[0]
                hit=re.search(r'T\s*=\s*([\d.Ee+-]+)\s+DT\s*=\s*([\d.Ee+-]+)\s+STEPS\s*=\s*(\d+)',line)
                if hit and line!=previous:
                    snapshots.append(dict(native_time_s=float(hit[1]),dt_s=float(hit[2]),steps=int(hit[3])));previous=line
            except (OSError,IndexError):pass
    thread=threading.Thread(target=monitor,daemon=True);thread.start();print('START',folder.relative_to(display_root or OUT),flush=True)
    try:
        # A slow native output interval must not override r7's full wall budget.
        native=execute(ENGINE,folder,deck,'',model['duration_s'],timeout,stall_timeout_s=0)
        report=analyze(model,native,manifest,baseline)
    except (NativeRunInterrupted,RuntimeError,ValueError) as exc:
        report=dict(complete=False,error=str(exc),native_time_s=getattr(exc,'native_time_s',None),native_wall_seconds=getattr(exc,'wall_seconds',None))
        if report['native_time_s']:
            safe=math.floor(report['native_time_s']/model['output_step_s'])*model['output_step_s']-2*model['output_step_s']
            try:
                native=load_result(folder,safe,{'folder':str(folder),'wall_seconds':report['native_wall_seconds']},allow_prefix=True)
                partial=analyze(model,native,manifest,baseline);partial.update(complete=False,partial_output=True)
                save(folder/'partial-analysis.json',partial)
            except (ValueError,KeyError,OSError) as secondary:report['partial_analysis_error']=str(secondary)
    finally:stop.set();thread.join()
    positive=[r['dt_s'] for r in snapshots if r['dt_s']>0]
    report['status_sample_statistics']={'samples':len(snapshots),'positive_min_dt_s':min(positive,default=None),
        'positive_median_dt_s':float(np.median(positive)) if positive else None,'last':snapshots[-1] if snapshots else None,
        'basis':'distinct snapshots at 1 wall second, NOT every solver step'}
    report['engine_sha256']=digest(ENGINE)
    save(folder/'status_samples.json',snapshots);save(folder/'analysis.json',report)
    print('DONE',folder.relative_to(display_root or OUT),json.dumps({k:report.get(k) for k in ('complete','horizon_s','native_wall_seconds','actual_burning_original_rooms','error')},ensure_ascii=False),flush=True)
    return report

def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['B','C','item','all','preflight'],default='all');args=p.parse_args()
    raw=json.loads(SOURCE.read_text('utf-8'));first=next(g for g in raw['fuel_groups'] if 'initial_time_s' in g)
    save(OUT/'stage0-origin.json',{'source':str(SOURCE),'source_sha256':digest(SOURCE),'initial_input':first,
        'generator':'tools/run_floor_spread_scenario.py:21,47','finding':'50000kW is explicitly present in input and generator default, not introduced by summation. r6 retained whole curve in one cell.',
        'engine_sha256':digest(ENGINE),'engine_modified':False})
    results={}
    if args.stage in ('B','all'):
        for name in ('B1','B2','B3'):
            path=ROOT/('fixtures/room_rule_benchmark_3room.json' if name=='B1' else f'fixtures/room_rule_benchmark_3room_{name.lower()}.json')
            m,t,manifest=prepare(json.loads(path.read_text('utf-8')));manifest.update(source_sha256=digest(path),engine_sha256=digest(ENGINE))
            r=run_case(OUT/'B'/name,m,t,manifest,timeout=600)
            secondary=[x for x in r.get('rows',[]) if x['parent']]
            passed=r['complete'] and (all(x['trigger_estimate_s'] is None and x['actual_peak_kW']==0 for x in secondary) if name=='B1' else all(x['longest_positive_HRR_s']>=60 for x in secondary))
            r['passed']=passed;save(OUT/'B'/name/'analysis.json',r);results[name]=r
            save(OUT/'B/verification.json',{'cases':results,'passed':len(results)==3 and all(x['passed'] for x in results.values())})
            if not passed:print('STOP B acceptance failed',name,flush=True);return
    if args.stage=='B':return
    if args.stage!='preflight':
        assert json.loads((OUT/'B/verification.json').read_text('utf-8'))['passed'],'Fresh r7 B required'
    m,t,manifest=prepare(raw)
    manifest.update(source_path=str(SOURCE),source_sha256=digest(SOURCE),engine_sha256=digest(ENGINE),run_timeout_s=1800,
        original_rooms=len(raw['rooms']),native_cells=len(m['rooms']),registered_sources=len(m['fuel_groups']))
    save(OUT/'C/prepared-scenario.json',m);save(OUT/'C/rule_manifest.json',manifest)
    if args.stage=='preflight':print('preflight ok',flush=True);return
    cases={}
    if args.stage in ('C','all'):
        base=deepcopy(m)
        for g in base['fuel_groups']:
            if 'room_rule_trigger' in g:g['room_rule_trigger']['setpoint']=1e20
        for name,case in [('baseline_native',base),('room_involvement',m)]:
            cases[name]=run_case(OUT/'C'/name,case,t,manifest,baseline=name=='baseline_native')
            save(OUT/'C/comparison.json',cases)
    if args.stage in ('item','all'):
        raw['room_rule_r7']={'room_supply':'item_peak'};mi,ti,mani=prepare(raw)
        mani.update(source_path=str(SOURCE),source_sha256=digest(SOURCE),engine_sha256=digest(ENGINE),run_timeout_s=1800)
        cases['item_peak']=run_case(OUT/'C/item_peak',mi,ti,mani)
        comparison=OUT/'C/comparison.json';existing=json.loads(comparison.read_text('utf-8')) if comparison.exists() else {}
        save(comparison,{**existing,**cases})
if __name__=='__main__':main()
