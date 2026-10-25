"""Integration evidence from actual CFAST runs, never a building-fire validation."""
from pathlib import Path
from copy import deepcopy
import json
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pyrocast_cfbt.model import normalize
from pyrocast_cfbt.deck import candidates, make_deck, gas_sidecar
from pyrocast_cfbt.native import execute
from pyrocast_cfbt.spread import simulate

OUT=ROOT/'results'/'verification'
BASE=ROOT/'build/baseline/cfast-baseline.exe'; ENGINE=ROOT/'build/cfbt/cfast-cfbt.exe'
original=json.loads((ROOT/'examples/three_rooms.json').read_text())
# Small structural test: lower thresholds and zero activation energy are intentional test settings.
raw=deepcopy(original)
raw.update(duration_s=90,max_time_step_s=.1)
raw['spread']={'enabled':False,'candidate_offsets_m':[.5],'candidate_heights_m':[1.5],
               'quadrature_n':8,'max_added_ignitions':0,'max_runs':1}
raw['gas'].update(gas_ignition_C=100,hot_C=100,oxygen_min_vol_percent=1,
                  fuel_min_mass_fraction=1e-6,rate_ref_s_inv=.05,activation_J_mol=0,
                  vent_gate_enabled=False,bulk_enabled=False)
model=normalize(raw); targets=candidates(model); deck=make_deck(model,[],targets); config=gas_sidecar(model)
baseline=execute(BASE,OUT/'baseline',deck,config,90,180)
off=execute(ENGINE,OUT/'extension_off',deck,config,90,180)
fields=[k for k in baseline['zone'] if k.startswith(('ULT_','LLT_','HGT_','HRR_'))]
off_difference=max(float(np.max(np.abs(baseline['zone'][k]-off['zone'][k]))) for k in fields)
assert off_difference<1e-8,off_difference

raw['gas']['bulk_enabled']=True
model=normalize(raw)
on=execute(ENGINE,OUT/'bulk_on',make_deck(model,[],targets),gas_sidecar(model),90,180)
peak_bulk=max(r['bulk_HRR_W'] for r in on['rooms'])
assert peak_bulk>1,peak_bulk
burn_integral=sum(float(np.trapezoid([r['bulk_burn_kg_s'] for r in on['rooms'] if r['room_index']==i],on['zone']['Time'])) for i in range(1,4))
initial_mass=sum(g['energy_MJ']*1000/g['heat_of_combustion_kJ_kg'] for g in model['fuel_groups'] if 'initial_time_s' in g)
assert burn_integral<=initial_mass+1e-3,(burn_integral,initial_mass)
assert min(r['fuel_upper_kg'] for r in on['rooms'])>=-1e-7
delta=float(np.max(np.abs(on['zone']['ULT_1']-off['zone']['ULT_1'])))
assert delta>.01,delta

blocked=deepcopy(raw); blocked['gas']['gas_ignition_C']=10000; blocked['gas']['pilot_assumed']=False
blocked=normalize(blocked)
blocked_result=execute(ENGINE,OUT/'temperature_gate_blocked',make_deck(blocked,[],targets),gas_sidecar(blocked),90,180)
assert max(r['bulk_HRR_W'] for r in blocked_result['rooms'])==0

oxygen_blocked=deepcopy(raw); oxygen_blocked['gas']['oxygen_min_vol_percent']=99
oxygen_blocked=normalize(oxygen_blocked)
oxygen_result=execute(ENGINE,OUT/'oxygen_gate_blocked',make_deck(oxygen_blocked,[],targets),gas_sidecar(oxygen_blocked),90,180)
assert max(r['bulk_HRR_W'] for r in oxygen_result['rooms'])==0

no_fuel=deepcopy(raw); no_fuel['duration_s']=10
no_fuel['fuel_groups']=[g for g in no_fuel['fuel_groups'] if 'initial_time_s' not in g]
no_fuel=normalize(no_fuel); no_fuel_targets=candidates(no_fuel)
empty=execute(ENGINE,OUT/'no_released_fuel',make_deck(no_fuel,[],no_fuel_targets),gas_sidecar(no_fuel),10,60)
assert max(r['bulk_HRR_W'] for r in empty['rooms'])==0

finer=deepcopy(raw); finer['max_time_step_s']=.05; finer=normalize(finer)
fine=execute(ENGINE,OUT/'half_max_timestep',make_deck(finer,[],targets),gas_sidecar(finer),90,180)
assert min(r['fuel_upper_kg'] for r in fine['rooms'])>=-1e-7
step_difference=float(np.max(np.abs(on['zone']['ULT_1']-np.interp(on['zone']['Time'],fine['zone']['Time'],fine['zone']['ULT_1']))))

# A lowered surface criterion forces the scheduling branch; it is not a realistic ignition-time claim.
solid=deepcopy(raw); solid['gas']['bulk_enabled']=False
solid['spread'].update(enabled=True,max_added_ignitions=1,max_runs=2)
solid['material']={'ignition_C':45,'pilot':'assumed'}
solid['fuel_groups']=[g for g in solid['fuel_groups'] if g['id']!='reserve_R1']
spread=simulate(solid,ENGINE,OUT/'one_solid_event')
assert spread['committed_ignitions_count']==1,spread['error']
assert spread['ignitions'][0]['room']!='R1'
assert spread['successful_runs_count']==2
final_deck=(Path(spread['runs'][-1]['folder'])/'case.in').read_text()
assert f"ID='F_{spread['ignitions'][0]['group']}'" in final_deck
assert spread['final_input_sha256']==spread['runs'][-1]['input_sha256']

summary={'baseline_off_max_difference':off_difference,'bulk_peak_W':peak_bulk,
         'bulk_burn_integral_kg':burn_integral,'initial_solid_budget_kg':initial_mass,
         'bulk_temperature_feedback_max_difference_C':delta,'high_temperature_gate_bulk_W':0,
         'high_oxygen_gate_bulk_W':0,'no_released_fuel_bulk_W':0,
         'half_max_timestep_temperature_difference_C':step_difference,
         'solid_events_committed':spread['committed_ignitions_count'],
         'solid_runs':spread['successful_runs_count'],'solid_termination':spread['terminated'],
         'scope':'structural_software_checks_with_intentionally_modified_thresholds_not_fire_validation'}
(OUT/'checks.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))
