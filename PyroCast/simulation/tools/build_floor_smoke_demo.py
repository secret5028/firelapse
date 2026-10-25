"""Coupled floor smoke with prescribed local solid ignition and FO times."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pyrocast_cfbt.cad import adapt,native_point
from pyrocast_cfbt.spread import simulate
from pyrocast_cfbt.playback import package


def expand_floor(project, base):
    old=base['scenario'];cad=old['cad']
    model=adapt(project,{'building_path':cad['source_path'],'fire_floor':'3F','fire_room':'R25',
        'scope_floor':'3F','duration_s':old['duration_s'],'max_added_ignitions':2,'max_runs':6})
    if model['cad']['building_sha256']!=cad['building_sha256']:raise ValueError('Different CAD building')
    rooms={r['id']:r for r in model['rooms']}
    # Preserve the declared inventories, chemistry and physical source position.
    # Solver box positions are rebuilt because the coupled room ordering has changed.
    model['fuel_groups']=deepcopy(old['fuel_groups'])
    for group in model['fuel_groups']:
        group['solver_position_m']=native_point(rooms[group['room']],group['position_m'])
    fuels={g['id'] for g in model['fuel_groups']}
    previous={v['id']:v for v in old['openings']}
    for opening in model['openings']:
        if opening['id'] in previous:opening['schedule']=deepcopy(previous[opening['id']]['schedule'])
    for name in ('gas','criteria','flashover','wall_material','demonstration'):
        model[name]=deepcopy(old[name])
    # For smoke coverage, keep the source programme explicit and run transport once.
    # New solid ignition times under the expanded ventilation are a separate analysis.
    model['prescribed_smoke']=True
    model['prescribed_fire_events']=deepcopy(base['ignitions'])
    for event in model['prescribed_fire_events']:
        event['solver_xyz']=native_point(rooms[event['room']],event['xyz'])
        event['basis']='prescribed_from_local_three_room_case; not_revalidated_in_expanded_floor'
    model['prescribed_fo_transitions']=deepcopy(base['fo_transitions'])
    for event in model['prescribed_fo_transitions']:
        event['basis']='prescribed_from_local_three_room_case; not_revalidated_in_expanded_floor'
    model['explicit_candidates']=[]
    model['spread'].update(enabled=False,max_runs=1,wall_time_budget_s=900.,run_timeout_s=900.)
    evaluated=sorted({g['room'] for g in model['fuel_groups']})
    model['smoke_scope']={'transport_rooms':list(rooms),'solid_evaluation_rooms':[],
        'prescribed_fire_rooms':evaluated,'mode':'prescribed_smoke',
        'basis':'coupled_native_floor_transport; fire and FO programme prescribed from previous local case; no new solid spread prediction'}
    model['cad']['uncovered_fuel_groups']=[g for g in model['cad'].get('uncovered_fuel_groups',[]) if g in fuels]
    model['cad']['warnings'].append('전층 연기 간편 재생: 고체 착화·FO 시각은 이전 3실 사례의 지정값. 층의 연결 구획에서 연기·열·산소·실제 발열을 함께 재계산하며 새 고체 착화 시각은 예측하지 않는다.')
    model['demonstration']['label']='R25 휴게실 · 연결층 전체 연기 / 화원 시각 지정'
    return model


def main():
    p=argparse.ArgumentParser();p.add_argument('project',type=Path)
    p.add_argument('--base',type=Path,default=ROOT/'results/cad_exterior_risk_demo_v4_ceiling/result.json')
    p.add_argument('--output',type=Path,default=ROOT/'results/cad_floor_smoke_v5_prescribed')
    p.add_argument('--build-only',action='store_true');args=p.parse_args()
    model=expand_floor(args.project,json.loads(args.base.read_text('utf-8')))
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'scenario.json').write_text(json.dumps(model,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'transport_rooms':len(model['rooms']),'solid_groups':len(model['fuel_groups']),
        'targets':len(model['explicit_candidates']),'openings':len(model['openings'])}),flush=True)
    if args.build_only:return
    result=simulate(model,ROOT/'build/ignition/cfbt/cfast-cfbt.exe',args.output)
    payload=package(result)
    (args.output/'playback.json').write_text(json.dumps(payload,ensure_ascii=False,allow_nan=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps({'status':result['terminated'],'error':result['error'],'runs':len(result['runs']),
        'native_seconds':sum(r['wall_seconds'] for r in result['runs']),'ignitions':len(result['ignitions'])}),flush=True)


if __name__=='__main__':main()
