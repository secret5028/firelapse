"""One explicit ignition scenario; existing fuel/O2 only, no probability estimate."""
from copy import deepcopy
import json
from pathlib import Path
import numpy as np
import math
import hashlib
from .spread import simulate,check_causality
from .native import load_result
from .playback import package
from .model import normalize


def comparison_key(base,room,time_s,exe,duration_s=30.,rate_s_inv=.2):
    from .native import digest
    signature={'base_config':base['config_sha256'],'base_input':base['final_input_sha256'],
               'engine':digest(exe),'room':room,'time_s':float(time_s),
               'duration_s':float(duration_s),'rate_s_inv':float(rate_s_inv),
               'implementation':{p.name:digest(p) for p in Path(__file__).parent.glob('*.py')}}
    return hashlib.sha256(json.dumps(signature,sort_keys=True).encode()).hexdigest()


def clipped_playback(payload,horizon):
    """Clip only known time-series fields; leave CAD geometry and provenance intact."""
    payload=deepcopy(payload);count=sum(t<=horizon+1e-6 for t in payload['time_s'])
    payload['time_s']=payload['time_s'][:count]
    for room in payload['solvers'].values():
        for key,value in list(room.items()):
            if isinstance(value,list):room[key]=value[:count]
        room['tags']={k:v[:count] for k,v in room['tags'].items()}
    for vent in payload['openings']:
        for key in ('ab','ba','gas_ab_kW','gas_ba_kW'):vent[key]=vent[key][:count]
    for fire in payload['fires']:
        fire['Q_kW']=fire['Q_kW'][:count]
        for key in ('area_m2','flame_height_m'):fire['visuals'][key]=fire['visuals'][key][:count]
    payload['comparison_horizon_s']=horizon
    return payload


def compare_ignition(base, room, time_s, exe, destination, duration_s=30., rate_s_inv=.2):
    model=normalize(deepcopy(base['scenario']))
    if base.get('error') or not base.get('simulation_complete_to_requested_horizon'):
        raise ValueError('완료된 기준 계산을 선택하세요.')
    ids=[r['id'] for r in model['rooms']]
    if room not in ids:raise ValueError('선택 실이 계산 범위에 없습니다.')
    if not 0<=time_s<model['duration_s'] or not 1<=duration_s<=60 or not .01<=rate_s_inv<=1:
        raise ValueError('점화 시점·유지시간·반응률 범위 오류')
    if not model['gas']['enabled'] or not model['gas']['bulk_enabled']:
        raise ValueError('비교 기준에도 가스 추가연소가 켜져 있어야 합니다. 같은 조건의 기준 계산을 먼저 실행하세요.')
    # Follow the intervention for five minutes, rather than rerunning a long hot tail.
    model['duration_s']=min(model['duration_s'],math.ceil((time_s+300)/model['output_step_s'])*model['output_step_s'])
    model['ignition_assumption']={'room':room,'time_s':float(time_s),'duration_s':float(duration_s),
        'rate_s_inv':float(rate_s_inv),'oxygen_min_vol_percent':model['criteria']['fgi_oxygen_vol_percent'],
        'basis':'finite_ignition_assistance_existing_upper_fuel_and_oxygen_only'}
    # Recompute later solid/FO events; never freeze the baseline future event list.
    model['spread']['max_runs']=min(6,model['spread']['max_runs'])
    model['spread']['wall_time_budget_s']=min(600.,model['spread']['wall_time_budget_s'])
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    changed=simulate(model,exe,destination)
    original=load_result(Path(base['runs'][-1]['folder']),model['duration_s'],base['runs'][-1])
    altered=load_result(Path(changed['runs'][-1]['folder']),model['duration_s'],changed['runs'][-1])
    check_causality(original,altered,{'t_ign_s':time_s},model['spread'])
    t=np.asarray(changed['time_s']); diffs={}
    for rid in ids:
        a=base['rooms'][rid];b=changed['rooms'][rid]
        diffs[rid]={}
        for key in ('T_upper_C','o2_upper_vol','optical_density_upper_m_inv'):
            delta=np.asarray(b[key])-np.interp(t,base['time_s'],a[key])
            diffs[rid][key]={'delta':delta.tolist(),'max_abs_change':float(np.max(np.abs(delta)))}
    b_events={e['group']:e['t_ign_s'] for e in base['ignitions'] if e['t_ign_s']<=model['duration_s']}
    new_events={e['group']:e['t_ign_s'] for e in changed['ignitions']}
    reactions=np.asarray(changed['rooms'][room]['bulk_HRR_W'])
    mask=(t>=time_s)&(t<=time_s+duration_s)
    base_reaction=np.interp(t,base['time_s'],base['rooms'][room]['bulk_HRR_W'])
    active=bool(np.any((reactions-base_reaction)[mask]>1.))
    output={'schema':'pyrocast-ignition-comparison-1','baseline':clipped_playback(package(base),model['duration_s']),'ignited':package(changed),
        'cache_key':comparison_key(base,room,time_s,exe,duration_s,rate_s_inv),
        'comparison_horizon_s':model['duration_s'],
        'assumption':model['ignition_assumption'],'room_differences':diffs,
        'solid_ignitions':{'baseline':b_events,'ignited':new_events},
        'reaction_observed':active,'coupling':'prescribed_solid_and_FO_times_native_transport_recomputed' if model.get('prescribed_smoke') else 'outer_loop_recomputed_solid_and_FO_events',
        'pre_ignition_causality_checked':True,
        'limitations':['점화원 유지시간 동안의 대표 반응률 가정이다. 폭연 압력·화염 전면은 계산하지 않는다.',
                      '가벼운 비교를 위해 점화 이후 약5분까지만 재계산한다. 그 뒤의 확산 변화는 비교하지 않는다.',
                      '연료·산소가 부족하면 점화를 가정해도 추가 반응이 없을 수 있다.',
                      '상한 종료 시 인접실 전이 탐색은 미완료다. 비교는 마지막 유효 계산까지이다.']}
    path=destination/'comparison.json';temp=path.with_suffix('.tmp')
    if model.get('prescribed_smoke'):
        output['limitations'].append('전층 연기 간편 모드: 고체 착화·FO 시각은 기준과 동일한 지정값이며 새 고체 전이 시각은 재평가하지 않는다.')
    temp.write_text(json.dumps(output,ensure_ascii=False,allow_nan=False,separators=(',',':')),encoding='utf-8');temp.replace(path)
    return output
