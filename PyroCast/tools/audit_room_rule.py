"""Read-only analysis of the stopped staged test. Never launches CFAST."""
import json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'simulation'))
from pyrocast_cfbt.native import load_result,read_native_csv
from pyrocast_cfbt.room_rule import observe
from pyrocast_cfbt.playback import fire_visuals
from pyrocast_cfbt.exposure import room_series
from pyrocast_cfbt.spread import solid_inventory,classify
from pyrocast_cfbt.conditions import evaluate
OUT=ROOT/'simulation/results/room_rule_20261025'
path=OUT/'spread/standard'
model=json.loads((path/'scenario.json').read_text('utf-8'))
state=json.loads((path/'run_00/execution-state.json').read_text('utf-8'))
horizon=min(read_native_csv(path/'run_00'/('case_'+name+'.csv'),420)[0]['Time'][-1]
            for name in ('zone','compartments','devices','vents'))
native=load_result(path/'run_00',horizon,{'folder':str(path/'run_00')},allow_prefix=True)
events,views,records=observe(model,native,model['explicit_candidates'])
states=room_series(model,native);inventory=solid_inventory(model,native,events)
partial={'time_s':native['zone']['Time'],'rooms':states,'solid_fuel_inventory':inventory,
         'ignitions':events,'candidates':views,'directional_vent_reactions':native['vents'],
         'phenomena':classify(model,native,states,events,views)}
assert len(evaluate(model,partial))>=3
assert all(np.min(item['remaining_solid_kg'])>=0 for item in inventory.values())
actual={g['room']:native['zone'][f'HRR_{i}'] for i,g in enumerate(model['fuel_groups'],1)}
report={'passed':False,'stage':'three_room_600s','same_fuel_geometry_and_gas_off':True,
    'completed_horizon_s':None,'partial_horizon_s':float(horizon),'requested_horizon_s':600,
    'partial_output_note':'Killed process leaves buffered CSV tails; evaluate only the common fully written prefix',
    'failure':state,'native_status':(path/'run_00/case.status').read_text().strip(),
    'dt_distribution_available':False,'dt_basis':'only last native status, not min/max/history',
    'observed_actual_burning_rooms':[rid for rid,q in actual.items() if np.any(q>1000)],
    'observed_events':events,'room_sensors':records,
    'baseline_native':json.loads((path/'baseline_native/completed.json').read_text('utf-8'))['run'],
    'legacy_not_started':True,'speedup_claim':None,'floor_and_preset_runs_blocked':True,
    'scope':'partial prefix only; stock initial-only baseline is not the legacy spread comparison'}
(OUT/'spread/comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
smoke=json.loads((OUT/'smoke_fixed/result.json').read_text('utf-8'))
assert len(fire_visuals(smoke))==1
verification={'automatic_ignition':json.loads((OUT/'stage0/verification.json').read_text('utf-8')),
    'short_pipeline_completed':True,'standby_fires_hidden':True,'supplementary_display_only':True,
    'partial_ignited_inventory_and_conditions_checked':True,
    'python_tests':106,'three_room_600s_passed':False,'floor_3600s_run':False,'presets_compared':False,
    'production_default_enabled':False,'existing_playback_replaced':False,'engine_rebuilt':False,
    'report':'spread/comparison.json'}
(OUT/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),'utf-8')
print(json.dumps({'partial_events':[{k:e[k] for k in ('room','t_ign_s','time_interval_s')} for e in events],
                  'actual_rooms':report['observed_actual_burning_rooms'],'native_status':report['native_status'],
                  'wall_seconds':state['wall_seconds']},ensure_ascii=False,indent=2))
