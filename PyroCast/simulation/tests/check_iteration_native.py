"""Small real-engine no-event / single-transfer regression, separate QA inputs."""
import json
from pathlib import Path
import sys
from copy import deepcopy

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pyrocast_cfbt.spread import simulate

base=json.loads((ROOT/'examples/three_rooms.json').read_text('utf-8'))
base.update(output_step_s=5,max_time_step_s=1)
base['spread']={'max_runs':4,'max_passes':4,'run_timeout_s':60,'wall_time_budget_s':180}
engine=ROOT/'build/ignition/cfbt/cfast-cfbt.exe';out=ROOT/'results/iteration_native_checks'
out.mkdir(parents=True,exist_ok=True);report={}
for case in ('no_event','single_transfer'):
    raw=deepcopy(base)
    raw['fuel_groups']=[g for g in raw['fuel_groups'] if g['id'] in ('primary','reserve_R2')]
    if case=='no_event':raw['fuel_groups']=raw['fuel_groups'][:1]
    else:raw['material']={'ignition_C':45,'pilot':'assumed'}  # QA only, not a production edit.
    results={}
    for mode in ('earliest_single','fixed_point'):
        raw['spread']['iteration_mode']=mode
        results[mode]=simulate(raw,engine,out/case/mode)
    a,b=(results[x] for x in ('earliest_single','fixed_point'))
    if case=='no_event':
        assert b['successful_runs_count']==1 and b['terminated']=='converged'
    else:
        assert len(a['ignitions'])==len(b['ignitions'])==1
        assert a['ignitions'][0]['group']==b['ignitions'][0]['group']
        assert abs(a['ignitions'][0]['t_ign_s']-b['ignitions'][0]['t_ign_s'])<=10
    report[case]={mode:{'terminated':r['terminated'],'native_runs':r['successful_runs_count'],
        'ignitions':r['ignitions'],'condition_consistent':r['iteration'].get('condition_consistent'),
        'native_seconds':sum(0 if x['cache_hit'] else x['wall_seconds'] for x in r['runs'])} for mode,r in results.items()}
    print(case,'passed',flush=True)
(out/'checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
