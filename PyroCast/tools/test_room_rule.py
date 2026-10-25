"""Bounded staged native validation; never overwrites production playback."""
import argparse,json,sys,time
from copy import deepcopy
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'simulation'))
from pyrocast_cfbt.model import normalize
from pyrocast_cfbt.room_rule import prepare,observe,supply_curve,settings
from pyrocast_cfbt.deck import make_deck,gas_sidecar,candidates
from pyrocast_cfbt.native import execute,digest,load_result
from pyrocast_cfbt.spread import simulate

ENGINE=ROOT/'simulation/build/adaptive_radiation_20261025/cfbt/cfast-cfbt.exe'
STOCK=ROOT/'simulation/build/baseline/cfast-baseline.exe'
OUT=ROOT/'simulation/results/room_rule_20261025'

def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf-8')

def stage0():
    source=json.loads((ROOT/'simulation/examples/three_rooms.json').read_text('utf-8'))
    source.update(duration_s=180,output_step_s=1,max_time_step_s=.5)
    source['rooms']=source['rooms'][:1]
    source['openings']=[{'id':'OUT','a':'R1','b':'OUTSIDE','face':'RIGHT','width_m':2,'top_m':2.5}]
    source['fuel_groups']=source['fuel_groups'][:2]
    source['fuel_groups'][0].update(energy_MJ=3000,peak_kW=3000)
    model=normalize(source)
    model['gas'].update(enabled=False,bulk_enabled=False,vent_gate_enabled=False,mixture_enabled=False)
    model['room_fire_rule']={'prepared':True}
    group=model['fuel_groups'][1];group['position_m']=[3,2,0]
    group['room_rule_curve']=supply_curve(group,16,settings({}))
    target={'id':'RF_TEST','group':group['id'],'room':'R1','xyz':[3,2,.1],
            'normal':[0,0,1],'material':{**model['material'],'thickness_m':.001}}
    report={'engine':digest(ENGINE),'stock_engine':digest(STOCK),'checks':{}}
    for criterion,point,column,unit in [('FLUX',5.,'TRGFLXI_1',1),('TEMPERATURE',100.,'TRGSURT_1',1)]:
        group['room_rule_trigger']={'criterion':criterion,'setpoint':point,'target_id':target['id']}
        deck=make_deck(model,[],[target]);side=gas_sidecar(model)
        r=execute(ENGINE,OUT/'stage0'/criterion,deck,side,180,90)
        stock=execute(STOCK,OUT/'stage0'/(criterion+'_stock'),deck,side,180,90)
        t=r['zone']['Time'];flag=r['compartments']['IGN_2'];hit=np.flatnonzero(flag>.5)
        assert len(hit) and hit[0]>0,'Standby fire did not ignite after start'
        j=int(hit[0]);values=r['devices'][column]/unit
        assert np.max(values[:j+1])>point,'Ignition without criterion crossing'
        assert np.max(r['zone']['HRR_2'])>1000,'No actual fire after trigger'
        identical=all(np.array_equal(r[key][col],stock[key][col]) for key in ('zone','compartments','devices','native_vents') for col in stock[key])
        assert identical,'Disabled extension differs from stock'
        report['checks'][criterion]={'ignition_bracket_s':[float(t[j-1]),float(t[j])],
            'last_before':float(values[j-1]),'first_after':float(values[j]),'stock_physical_arrays_bit_equal':identical,
            'wall_seconds':r['run']['wall_seconds']}
        save(OUT/'stage0/verification.json',report)
        print(criterion,report['checks'][criterion],flush=True)
    # Explicitly disabled rule preserves legacy deck and sidecar, byte for byte.
    raw=json.loads((ROOT/'simulation/examples/three_rooms.json').read_text('utf-8'))
    old=normalize(raw);raw['room_fire_rule']={'enabled':False};off=normalize(raw)
    assert make_deck(old,[],candidates(old))==make_deck(off,[],candidates(off))
    assert gas_sidecar(old)==gas_sidecar(off)
    report['rule_disabled_legacy_input_bytes_equal']=True
    report['passed']=True;save(OUT/'stage0/verification.json',report)

def summarize(result):
    actual={g['room']:result['solid_fuel_inventory'][g['id']].get('actual_HRR_W',[0]*len(result['time_s'])) for g in result['scenario']['fuel_groups']}
    concurrent=sum((np.asarray(v)>1000 for v in actual.values()),np.zeros(len(result['time_s']),int))
    return {'terminated':result['terminated'],'engine_wall_seconds':sum(r['wall_seconds'] for r in result['runs']),
        'scenario_wall_seconds':result['runs'][-1]['wall_seconds'],'total_wall_seconds':result['wall_seconds'],
        'native_runs':len(result['runs']),'ignitions':[{k:e[k] for k in ('room','t_ign_s')} for e in result['ignitions']],
        'actual_burning_rooms':[rid for rid,q in actual.items() if max(q)>1000],
        'peak_concurrent':int(np.max(concurrent)),'spread_search_complete':result['spread_search_complete']}

def spread():
    source=ROOT/'simulation/results/adaptive_radiation_20261025/spread/native/scenario.json'
    raw=json.loads(source.read_text('utf-8'))
    raw['engine_optimization']={'adaptive_radiation':False,'radiation_cache':False,'wall_cache':False}
    raw['gas'].update(enabled=False,bulk_enabled=False,vent_gate_enabled=False,mixture_enabled=False,mixture_smooth_enabled=False)
    raw['spread'].update(run_timeout_s=180,wall_time_budget_s=600)
    raw['room_fire_rule']={'enabled':True,'preset':'standard','trigger_mode':'floor_r2'}
    try:new=simulate(raw,ENGINE,OUT/'spread/standard')
    except (TimeoutError,RuntimeError,ValueError) as exc:
        save(OUT/'spread/comparison.json',{'passed':False,'same_fuel_geometry_and_gas_off':True,
            'error':str(exc),'legacy_not_started':True,'floor_and_preset_runs_blocked':True})
        raise
    print('spread rule',summarize(new),flush=True)
    raw['room_fire_rule']['enabled']=False
    old=simulate(raw,ENGINE,OUT/'spread/legacy');print('spread legacy',summarize(old),flush=True)
    save(OUT/'spread/comparison.json',{'passed':True,'same_fuel_geometry_and_gas_off':True,'legacy':summarize(old),'room_rule':summarize(new)})

def floor(preset):
    gate=json.loads((OUT/'spread/comparison.json').read_text('utf-8'))
    if not gate.get('passed'):raise ValueError('3-room comparison has not passed; floor/preset runs are blocked')
    raw=json.loads((ROOT/'simulation/results/mixture_r3f_cache_20261023/floor60/scenario.json').read_text('utf-8'))
    raw['room_fire_rule']={'enabled':True,'preset':preset,'trigger_mode':'floor_r2'}
    raw['spread'].update(run_timeout_s=1200,wall_time_budget_s=3600)
    result=simulate(raw,ENGINE,OUT/'floor'/preset)
    report=summarize(result);report['target_rooms']=16;report['target_met']=len(report['actual_burning_rooms'])>=16
    save(OUT/'floor'/preset/'audit.json',report)
    from pyrocast_cfbt.playback import package
    save(OUT/'floor'/preset/'playback.json',package(result))
    print(preset,json.dumps(report,ensure_ascii=False),flush=True)

def smoke():
    raw=json.loads((ROOT/'simulation/examples/three_rooms.json').read_text('utf-8'))
    raw.update(duration_s=60,output_step_s=5,max_time_step_s=.5)
    for opening in raw['openings']:opening['schedule']=[[0,1]]
    raw['room_fire_rule']={'enabled':True,'trigger_mode':'floor_r2'}
    raw['spread']={'run_timeout_s':60,'wall_time_budget_s':120}
    result=simulate(raw,ENGINE,OUT/'smoke_fixed')
    assert result['scenario_runs_count']==1 and result['baseline_runs_count']==1
    assert result['conditions'] and result['spread_model']=='room_flashover_rule_v1'
    assert all(not v['supplementary_used_for_ignition'] for v in result['candidates'])
    from pyrocast_cfbt.playback import fire_visuals
    assert len(fire_visuals(result))==1  # standby fires do not become visible flames
    save(OUT/'smoke_fixed/audit.json',summarize(result))
    print('Pipeline smoke',summarize(result),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('scope',choices=['stage0','spread','floor','smoke']);p.add_argument('--preset',default='standard',choices=['standard','conservative','aggressive']);a=p.parse_args()
    if a.scope=='stage0':stage0()
    else:
        assert json.loads((OUT/'stage0/verification.json').read_text('utf-8'))['passed']
        if a.scope=='smoke':smoke()
        elif a.scope=='spread':spread()
        else:floor(a.preset)
