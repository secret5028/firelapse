"""r6a B provenance check then one stock baseline and one real-floor rule run."""
import argparse,io,json,math,re,sys,threading,time
from copy import deepcopy
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'simulation'));sys.path.insert(0,str(ROOT/'tools'))
from pyrocast_cfbt.room_rule_r6 import prepare
from pyrocast_cfbt.deck import make_deck,fire_curve
from pyrocast_cfbt.model import normalize
from pyrocast_cfbt.native import execute,load_result,digest,NativeRunInterrupted
from test_room_rule_r4 import longest,save
ENGINE=ROOT/'simulation/build/baseline/cfast-baseline.exe'
OUT=ROOT/'simulation/results/room_rule_r6a_20261025'
SOURCE=ROOT/'simulation/results/mixture_r3f_cache_20261023/floor60/scenario.json'


def verify_b():
    assert json.loads((OUT/'A/analysis.json').read_text('utf-8'))['passed']
    checks={}
    for name in ('B1','B2','B3'):
        path=ROOT/('fixtures/room_rule_benchmark_3room.json' if name=='B1' else f'fixtures/room_rule_benchmark_3room_{name.lower()}.json')
        m,targets,manifest=prepare(json.loads(path.read_text('utf-8')))
        folder=OUT/'B'/name;deck=make_deck(m,[],targets)
        assert deck==(folder/'case.in').read_text('ascii'),name+' changed input: fresh B required'
        buffer=io.BytesIO();writer=io.TextIOWrapper(buffer,encoding='ascii',newline=None)
        writer.write(deck);writer.flush()
        assert buffer.getvalue()==(folder/'case.in').read_bytes(),name+' native input bytes changed'
        cache=json.loads((folder/'completed.json').read_text('utf-8'))
        assert cache['signature']['engine']==digest(ENGINE)
        assert all(digest(folder/f)==sha for f,sha in cache['files'].items())
        report=json.loads((folder/'analysis.json').read_text('utf-8'));assert report['passed']
        checks[name]={'passed':True,'deck_byte_identical':True,'all_output_hashes_verified':True,
            'input_sha256':digest(folder/'case.in'),'native_wall_seconds':cache['run']['wall_seconds'],
            'rows':report['rows'],'general_generator_manifest':manifest}
    save(OUT/'B/post_coordinate_fix_verification.json',checks)
    return checks


def observe(model,native,manifest,baseline=False):
    t=native['zone']['Time'];c=native['compartments'];ids=native['compartments_ids']
    rooms={r['id']:r for r in model['rooms']};ri={r['id']:i for i,r in enumerate(model['rooms'],1)}
    log=(Path(native['run']['folder'])/'case.log').read_text(errors='replace')
    logged={m[1]:float(m[2]) for m in re.finditer(r'\((F_[A-Za-z0-9_]+)\) ignited at\s+(\d+) seconds',log)}
    aggregate={};rows=[]
    for i,g in enumerate(model['fuel_groups'],1):
        rid=g['room'];parent=manifest['parents'].get(rid);original=rooms[rid]['parent_room']
        assert ids[f'HRR_{i}'].strip()=='F_'+g['id']
        q=c[f'HRR_{i}']/1000;hit=np.flatnonzero(q>0);flags=np.flatnonzero(c[f'IGN_{i}']>.5)
        interval=None;trigger=None;delay=parent['delay_s'] if parent else 0
        if 'initial_time_s' in g:trigger=g['initial_time_s'];interval=[trigger,trigger]
        elif len(flags):
            j=int(flags[0]);lo=float(t[max(0,j-1)]);hi=float(t[j]);rounded=logged.get('F_'+g['id'])
            if rounded is not None:lo=max(lo,rounded-.5);hi=min(hi,rounded+.5)
            assert lo<=hi
            interval=[lo,hi];trigger=(lo+hi)/2
        sensor_id=g.get('room_rule_trigger',{}).get('target_id');sensor=None
        if sensor_id:
            key=next(k for k,v in native['devices_ids'].items() if k.startswith('TRGSURT_') and v.strip()==sensor_id)
            sensor=native['devices'][key]
        duration=longest(t,q);roomidx=ri[rid]
        reason=('initial_source' if parent is None else 'actual_source_burning' if len(hit) else
                'baseline_standby_disabled' if baseline else 'parent_sensor_threshold_not_reached' if trigger is None else
                'delay_not_elapsed_by_horizon' if trigger+delay>=t[-1] else
                'zero_supply_cap' if max(g['room_rule_curve']['q'])==0 else 'triggered_but_no_actual_source_HRR; oxygen/mixing check required')
        rows.append({'cell':rid,'original_room':original,'group':g['id'],'parent':parent,
            'trigger_estimate_s':trigger,'trigger_interval_s':interval,'delay_s':delay,
            'supply_start_estimate_s':None if trigger is None else trigger+delay,
            'first_actual_positive_HRR_s':None if not len(hit) else float(t[hit[0]]),
            'actual_peak_kW':float(max(q)),'longest_positive_HRR_s':duration,'longest_over_1kW_s':longest(t,q,1),
            'sensor_id':sensor_id,'sensor_max_C':None if sensor is None else float(max(sensor)),
            'sensor_at_trigger_interpolated_C':None if sensor is None or trigger is None else float(np.interp(trigger,t,sensor)),
            'fire_position_m':g.get('solver_position_m',g['position_m']),
            'Q_supply_max_kW':float(max(g['room_rule_curve']['q'])),'supply_cap':g.get('room_vent_cap'),
            'supply_basis':g['room_rule_curve'].get('limiting_cap','unchanged_initial_curve'),
            'upper_max_C':float(max(c[f'ULT_{roomidx}'])),
            'upper_O2_min_vol_percent':float(min(c[f'ULO2_{roomidx}'])*100),
            'vent_combustion_peak_kW':float(max(c[f'DJET_{roomidx}']))/1000,'status':reason})
        aggregate.setdefault(original,np.zeros_like(t));aggregate[original]+=q
    actual=[r for r,q in aggregate.items() if np.max(q)>0]
    sustained=[r for r,q in aggregate.items() if longest(t,q)>=60]
    over1=[r for r,q in aggregate.items() if np.max(q)>1]
    steps=re.search(r'Total time steps\s*=\s*(\d+)',log)
    return {'complete':True,'engine_sha256':digest(ENGINE),'native_wall_seconds':native['run']['wall_seconds'],
        'horizon_s':float(t[-1]),'total_steps':int(steps[1]) if steps else None,'rows':rows,
        'actual_burning_original_rooms':actual,'sustained_60s_original_rooms':sustained,'over_1kW_original_rooms':over1,
        'max_concurrent_original_rooms_over_1kW':int(np.max(sum((q>1 for q in aggregate.values()),np.zeros_like(t)))),
        'target_16_rooms_met':len(sustained)>=16,'target_basis':'distinct original rooms with >0 actual source HRR for >=60s, not cells or IGN',
        'no_vertical_vents_in_this_input':not any(v.get('type')=='FLOOR' for v in model['openings'])}


def run_case(name,model,targets,manifest,analyze_only=False):
    folder=OUT/'C'/name;deck=make_deck(model,[],targets)
    assert '&CFBT' not in deck and model['duration_s']==3600 and model['output_step_s']==5
    if analyze_only:
        assert (folder/'case.in').read_text('ascii')==deck
        cache=json.loads((folder/'completed.json').read_text('utf-8'))
        assert cache['signature']['engine']==digest(ENGINE)
        native=load_result(folder,3600,cache['run'])
        return observe(model,native,manifest,name=='baseline_native')
    if (folder/'planned-execution.json').exists():raise ValueError('C already attempted; do not automatically rerun '+name)
    save(folder/'scenario.json',model);save(folder/'rule_manifest.json',manifest)
    snapshots=[];stop=threading.Event()
    def monitor():
        previous=None
        while not stop.wait(1):
            try:
                line=(folder/'case.status').read_text(errors='replace').splitlines()[0]
                m=re.search(r'T\s*=\s*([\d.Ee+-]+)\s+DT\s*=\s*([\d.Ee+-]+)\s+STEPS\s*=\s*(\d+)',line)
                if m and line!=previous:
                    snapshots.append({'native_time_s':float(m[1]),'dt_s':float(m[2]),'steps':int(m[3])});previous=line
            except (OSError,IndexError):pass
    thread=threading.Thread(target=monitor,daemon=True);thread.start();print('START C '+name,flush=True)
    try:
        native=execute(ENGINE,folder,deck,'',3600,1200)
        report=observe(model,native,manifest,name=='baseline_native')
    except (NativeRunInterrupted,RuntimeError,ValueError) as exc:
        report={'complete':False,'error':str(exc),'engine_sha256':digest(ENGINE),
            'native_time_s':getattr(exc,'native_time_s',None),'native_wall_seconds':getattr(exc,'wall_seconds',None)}
    finally:stop.set();thread.join()
    report['status_sample_statistics']={'samples':len(snapshots),
        'min_dt_s':min((r['dt_s'] for r in snapshots),default=None),
        'median_dt_s':float(np.median([r['dt_s'] for r in snapshots])) if snapshots else None,
        'last':snapshots[-1] if snapshots else None,
        'basis':'distinct case.status snapshots polled every 1 wall second; NOT every accepted solver step'}
    save(folder/'status_samples.json',snapshots);save(folder/'analysis.json',report)
    print('DONE C '+name,json.dumps({k:v for k,v in report.items() if k!='rows'},ensure_ascii=False),flush=True)
    return report


def main():
    p=argparse.ArgumentParser();p.add_argument('--preflight-only',action='store_true');p.add_argument('--analyze-only',action='store_true');args=p.parse_args()
    b=verify_b();raw=json.loads(SOURCE.read_text('utf-8'));raw['spread'].update(run_timeout_s=1200,wall_time_budget_s=3600)
    model,targets,manifest=prepare(raw)
    original=normalize(raw);first=next(g for g in original['fuel_groups'] if 'initial_time_s' in g)
    original_room=next(r for r in original['rooms'] if r['id']==first['room'])
    oldcurve=fire_curve(first,math.prod(original_room['size_m'][:2]));newfirst=next(g for g in model['fuel_groups'] if 'initial_time_s' in g)
    assert all(np.array_equal(v,newfirst['room_rule_curve'][k]) for v,k in zip(oldcurve,('t','q','area')))
    assert math.isclose(sum(math.prod(r['size_m']) for r in original['rooms']),sum(math.prod(r['size_m']) for r in model['rooms']),rel_tol=1e-12)
    manifest.update(engine_sha256=digest(ENGINE),source_sha256=digest(SOURCE),source_path=str(SOURCE),
        run_timeout_s=1200,budget_basis='existing tools/test_room_rule.py floor budget; no increase',
        B_reused_exact_inputs=True,B_passed=True,source_initial_curve_arrays_equal=True,
        original_rooms=len(original['rooms']),native_cells=len(model['rooms']),registered_sources=len(model['fuel_groups']),
        no_vertical_vents_in_this_input=not any(v.get('type')=='FLOOR' for v in model['openings']))
    aborted=OUT/'C_coordinate_mismatch_aborted'
    if aborted.exists():
        manifest['discarded_attempt']={'folder':str(aborted),'reason':'CAD/native frame mismatch in virtual boundary passage distances',
            'baseline_last_state':json.loads((aborted/'baseline_native/execution-state.json').read_text('utf-8')),
            'completed':False,'not_in_final_timing':True}
    save(OUT/'C/rule_manifest.json',manifest);save(OUT/'C/prepared-scenario.json',model)
    (OUT/'C/prepared.in').write_text(make_deck(model,[],targets),'ascii')
    print('PREFLIGHT',json.dumps({k:manifest[k] for k in ('original_rooms','native_cells','registered_sources','sensor_placement_unavailable','no_vertical_vents_in_this_input')},ensure_ascii=False),flush=True)
    if args.preflight_only:return
    baseline=deepcopy(model)
    for g in baseline['fuel_groups']:
        if 'room_rule_trigger' in g:g['room_rule_trigger']['setpoint']=1e20
    reports={}
    for name,m in [('baseline_native',baseline),('scenario',model)]:
        reports[name]=run_case(name,m,targets,manifest,args.analyze_only)
        save(OUT/'C/comparison.json',{'cases':reports,'complete':len(reports)==2 and all(r['complete'] for r in reports.values()),'target_rooms':16,'legacy_timing_comparison':'not performed; baseline has only the initial fire active'})
        if not reports[name]['complete'] and 'CFAST failed:' in reports[name].get('error',''):break


if __name__=='__main__':main()
