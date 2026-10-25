"""Explicitly enriched exterior-room scenario on the existing CAD, not calibration."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pyrocast_cfbt.cad import adapt
from pyrocast_cfbt.spread import simulate
from pyrocast_cfbt.playback import package


def main():
    p=argparse.ArgumentParser();p.add_argument('project',type=Path);p.add_argument('--building',type=Path,required=True)
    p.add_argument('--output',type=Path,default=ROOT/'results/cad_exterior_risk_demo_v4_ceiling')
    args=p.parse_args()
    model=adapt(args.project,{'building_path':str(args.building),'fire_floor':'3F','fire_room':'R25',
        'scope_floor':'3F','duration_s':1800,'max_added_ignitions':3,'max_runs':6})
    keep={'CAD_3F_R25','CAD_3F_R15','CAD_3F_R4'}
    assert not any(r['core_kind'] for r in model['rooms'] if r['id'] in keep), 'Demo must use non-core rooms'
    removed=[r['id'] for r in model['rooms'] if r['id'] not in keep]
    model['rooms']=[r for r in model['rooms'] if r['id'] in keep]
    model['fuel_groups']=[g for g in model['fuel_groups'] if g['room'] in keep]
    model['openings']=[v for v in model['openings'] if v['a'] in keep and v['b'] in keep|{'OUTSIDE'}]
    vents={v['id'] for v in model['openings']}
    model['explicit_candidates']=[c for c in model['explicit_candidates'] if c['room'] in keep and (not c.get('opening_id') or c['opening_id'] in vents)]
    model['cad']['display_rooms']=[r for r in model['cad']['display_rooms'] if r['solver_id'] in keep]
    model['cad']['excluded'] += [{'key':r,'reason':'local_demonstration_closed_cut_boundary'} for r in removed]
    model['cad']['warnings'].append('경량 시연은 R25 휴게실·R15 홀2·R4 홀3만 계산. 계단실 R21은 제외. 나머지 연결은 닫힌 절단 경계 근사.')
    fire=next(g for g in model['fuel_groups'] if 'initial_time_s' in g)
    fire['energy_MJ']*=4;fire['peak_kW']*=8
    fire['growth_kW_s2']=.1875
    fire['fuel_area_m2']=next(r['area_m2'] for r in model['rooms'] if r['id']==fire['room']);fire['hrrpua_kW_m2']=750.
    fire['basis']='demonstration: fuel_energy_x4, peak_x8, full_floor_fuel_area, fast_t2_growth; not_surveyed'
    for opening in model['openings']:
        if fire['room'] not in (opening['a'],opening['b']):continue
        if opening['b']=='OUTSIDE':opening['schedule']=[[0,.1],[449,.1],[450,.8]]
        elif opening['kind']=='door':opening['schedule']=[[0,.15],[299,.15],[300,1.]]
    model['demonstration']={'label':'외기면 R25 · 연료 가산 탐색 사례',
        'fuel_energy_multiplier':4,'peak_multiplier':8,'growth_kW_s2':.1875,
        'ventilation_assumption':'외부창 10%→450초 80%; 실내문15%→300초100%',
        'basis':'user_requested_enriched_demonstration; not_existing_building_fuel_survey'}
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'scenario.json').write_text(json.dumps(model,ensure_ascii=False,indent=2),encoding='utf-8')
    result=simulate(model,ROOT/'build/ignition/cfbt/cfast-cfbt.exe',args.output)
    (args.output/'playback.json').write_text(json.dumps(package(result),ensure_ascii=False,allow_nan=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps({'terminated':result['terminated'],'runs':result['successful_runs_count'],
        'events':result['fo_transitions'],'phenomena':{r:v['first_times_s'] for r,v in result['phenomena'].items()}},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
