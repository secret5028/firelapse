"""Small real-engine integration checks, separate from the unit suite."""
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from test_practical import building_fixture
from pyrocast_cfbt.cad import adapt
from pyrocast_cfbt.spread import simulate
from pyrocast_cfbt.playback import package


def main():
    base=ROOT/'results/practical_checks';base.mkdir(parents=True,exist_ok=True)
    reports=[]
    for name in ('two_rooms','single_room','fo_two_rooms'):
        destination=base/name;destination.mkdir(parents=True,exist_ok=True)
        building=building_fixture()
        if name=='single_room':
            floor=building['floors'][0];floor['rooms']=floor['rooms'][:1]
            floor['simulation_graph']['connections']=[];floor['openings']=[]
        source=destination/'building.json';source.write_text(json.dumps(building),encoding='utf-8')
        scenario=adapt(source,{'duration_s':90 if name=='fo_two_rooms' else 60,'max_added_ignitions':1,
                               'gas':{'enabled':False},'criteria':{'fo_temperature_C':40.},
                               'flashover':{'enabled':name=='fo_two_rooms'}})
        begin=time.monotonic()
        result=simulate(scenario,ROOT/'build/cfbt/cfast-cfbt.exe',destination)
        payload=package(result)
        assert result['simulation_complete_to_requested_horizon']
        assert result['execution_profile']=='practical'
        assert payload['limitations'] and payload['building_sha256']
        assert all(run['normal_exit'] for run in result['runs'])
        if name=='fo_two_rooms':
            assert result['fo_transitions'], 'Low-threshold functional FO did not activate'
            import numpy as np
            from pyrocast_cfbt.native import load_result
            from pyrocast_cfbt.exposure import supplementary,room_series
            native=load_result(Path(result['runs'][-1]['folder']),scenario['duration_s'],result['runs'][-1])
            states=room_series(result['scenario'],native)
            target=result['scenario']['explicit_candidates'][0]
            point,_=supplementary(result['scenario'],native,target,states,result['ignitions'],[])
            distributed,_=supplementary(result['scenario'],native,target,states,result['ignitions'],result['fo_transitions'])
            before=np.asarray(result['time_s'])<result['fo_transitions'][0]['t_ign_s']
            np.testing.assert_allclose(point['fire_through_vent'][before],distributed['fire_through_vent'][before])
            assert np.max(np.abs(point['fire_through_vent']-distributed['fire_through_vent']))>0
        (destination/'playback.json').write_text(json.dumps(payload,ensure_ascii=False,allow_nan=False),encoding='utf-8')
        reports.append({'case':name,'passed':True,'wall_s':time.monotonic()-begin,
                        'terminated':result['terminated'],'time_end_s':result['time_s'][-1]})
        print(json.dumps(reports[-1]),flush=True)
    # Exercise a real FO supply transition with a larger time step and pooled fuel area.
    from pyrocast_cfbt.practical import apply_profile
    raw=json.loads((ROOT/'examples/fo_transition_check.json').read_text('utf-8'))
    raw['max_time_step_s']=1.
    scenario=apply_profile(raw);scenario['flashover']['area_basis']='floor'
    begin=time.monotonic();result=simulate(scenario,ROOT/'build/cfbt/cfast-cfbt.exe',base/'fo_transition')
    assert result['fo_transitions'] and result['simulation_complete_to_requested_horizon']
    reports.append({'case':'fo_transition','passed':True,'wall_s':time.monotonic()-begin,
                    'fo_events':len(result['fo_transitions']),'time_end_s':result['time_s'][-1]})
    print(json.dumps(reports[-1]),flush=True)
    (base/'checks.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')


if __name__=='__main__':main()
