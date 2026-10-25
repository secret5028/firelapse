"""Audit the completed CAD aperture-candidate run without recomputing fire dynamics."""
import json
from pathlib import Path
import re
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pyrocast_cfbt.cad import geometry_dependencies,footprint
from pyrocast_cfbt.deck import active_fuels
from pyrocast_cfbt.native import digest,read_native_csv


def main():
    folder=ROOT/'results/cad_opening_30min'
    result=json.loads((folder/'result.json').read_text('utf-8'))
    payload=json.loads((folder/'playback.json').read_text('utf-8'))
    model=result['scenario'];geometry_dependencies(Path(model['cad']['source_path']).parents[4])
    from shapely.geometry import Point
    rooms={r['key']:r for r in model['cad']['display_rooms']}
    solvers={r['id']:r for r in model['rooms']}
    openings={v['id']:v for v in model['openings']}
    targets={c['id']:c for c in model['explicit_candidates']}
    assert result['simulation_complete_to_requested_horizon'] and payload['time_s'][-1]==1800
    assert all(run['normal_exit'] for run in result['runs'])
    for target in targets.values():
        room=rooms[target['cad_key']];shape=footprint(room['cad_polys'])
        opening=openings[target['opening_id']];c=opening['cad_geometry']['center_m']
        p=np.array(target['xyz']);normal=np.array(target['normal'])
        assert shape.contains(Point(p[:2]))
        assert np.isclose(np.linalg.norm(p[:2]-c[:2]),target['distance_from_opening_m'])
        assert np.dot(p[:2]-c[:2],normal[:2])<0
        assert np.isclose(p[2]-room['z_m'],target['fuel_face_height_m'])
        assert target['source_cad_key']!=target['cad_key']
    events=result['ignitions'];assert len({e['group'] for e in events})==len(events)
    stage_differences=[]
    for index,event in enumerate(events):
        target=targets[event['candidate']]
        np.testing.assert_allclose(event['xyz'],target['xyz'])
        np.testing.assert_allclose(event['solver_xyz'],target['solver_xyz'])
        assert event['opening_id']==target['opening_id']
        before,_,_=read_native_csv(Path(result['runs'][index]['folder'])/'case_compartments.csv')
        after,_,_=read_native_csv(Path(result['runs'][index+1]['folder'])/'case_compartments.csv')
        mask=before['Time']<event['t_ign_s']-model['spread']['event_tolerance_s']
        delta=max(float(np.max(np.abs(before[k][mask]-np.interp(before['Time'][mask],after['Time'],after[k]))))
                  for k in before if k.startswith(('ULT_','LLT_')))
        assert delta<.2
        stage_differences.append(delta)
    native_folder=Path(result['runs'][-1]['folder']);deck=(native_folder/'case.in').read_text('ascii')
    assert digest(native_folder/'case.in')==payload['final_input_sha256']
    byevent={e['group']:e for e in events};byfire={f['id']:f for f in payload['fires']}
    for group in active_fuels(model,events):
        f=byfire[group['id']];event=byevent.get(group['id']);xyz=event['xyz'] if event else group['position_m']
        expected=xyz[2]-solvers[group['room']]['origin_m'][2]
        location=re.search(r"&FIRE ID='F_"+re.escape(group['id'])+r"'.*? LOCATION=([^ ]+)",deck)[1]
        expected_xy=np.array(event.get('solver_xyz',event['xyz']) if event else group.get('solver_position_m',group['position_m']))[:2]-np.array(solvers[group['room']]['origin_m'])[:2]
        np.testing.assert_allclose(list(map(float,location.split(','))),expected_xy,rtol=1e-7,atol=1e-6)
        heights=[float(m[1].split(',')[2]) for m in re.finditer(r"&TABL ID='F_"+re.escape(group['id'])+r"' DATA=([^/]+)/",deck)]
        assert heights and np.allclose(heights,expected)
        assert np.isclose(f['visuals']['base_height_m'],expected)
        np.testing.assert_allclose(f['position_m'],xyz,atol=1e-7)
    summary={'horizon_s':payload['time_s'][-1],'candidate_count':len(targets),
             'candidate_geometry_checks':'inside actual receiving CAD polygon; 0.6/1.5m; face toward opening',
             'runs':len(result['runs']),'status':result['terminated'],
             'native_seconds':[r['wall_seconds'] for r in result['runs']],
             'pre_event_max_temperature_difference_C':stage_differences,
             'events':[{k:e[k] for k in ('cad_key','candidate','opening_id','source_cad_key','distance_from_opening_m','t_ign_s','xyz','largest_incident_term')} for e in events],
             'fire_base_height_checks':'native TABL = ignition Z minus room floor = playback flame base',
             'fire_xy_checks':'native FIRE LOCATION = mapped candidate/event XY minus native room origin, without clipping',
             'uncovered_fuel_groups':model['cad']['uncovered_fuel_groups'],
             'scope':'one 3F R9 initial-fire scenario, 3F connected rooms, 45C exploratory solid threshold; no all-room initial-fire sweep'}
    output=ROOT/'results/verification/opening30_checks.json'
    output.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
