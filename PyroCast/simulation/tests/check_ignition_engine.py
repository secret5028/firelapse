"""Real engine checks for no-force compatibility and finite gas ignition assistance."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pyrocast_cfbt.model import normalize
from pyrocast_cfbt.deck import make_deck,gas_sidecar,candidates
from pyrocast_cfbt.native import execute


def main():
    out=ROOT/'results/ignition_checks';out.mkdir(parents=True,exist_ok=True)
    raw=json.loads((ROOT/'examples/three_rooms.json').read_text())
    raw.update(duration_s=90.,max_time_step_s=.1)
    raw['gas'].update(gas_ignition_C=10000.,pilot_assumed=False,oxygen_min_vol_percent=1.,
                      fuel_min_mass_fraction=1e-6,activation_J_mol=0.,vent_gate_enabled=False)
    model=normalize(raw);targets=candidates(model);deck=make_deck(model,[],targets)
    old=execute(ROOT/'build/cfbt/cfast-cfbt.exe',out/'old',deck,gas_sidecar(model),90,120)
    new=execute(ROOT/'build/ignition/cfbt/cfast-cfbt.exe',out/'no_force',deck,gas_sidecar(model),90,120)
    difference=max(float(np.max(np.abs(v-new['zone'][key]))) for key,v in old['zone'].items())
    assert difference==0,difference
    forced=deepcopy(model);forced['ignition_assumption']={'room':'R1','time_s':40.,'duration_s':20.,'rate_s_inv':.2,'oxygen_min_vol_percent':1.}
    changed=execute(ROOT/'build/ignition/cfbt/cfast-cfbt.exe',out/'forced',deck,gas_sidecar(normalize(forced)),90,120)
    room=[r for r in changed['rooms'] if r['room_index']==1]
    peak=max(r['bulk_HRR_W'] for r in room)
    assert peak>0
    assert all(r['bulk_HRR_W']==0 for r in room if r['time_s']<40 or r['time_s']>=60)
    assert all(r['bulk_HRR_W']==0 for r in changed['rooms'] if r['room_index']!=1)
    before=changed['zone']['Time']<40
    pre=max(float(np.max(np.abs(changed['zone'][key][before]-new['zone'][key][before]))) for key in ('ULT_1','LLT_1'))
    assert pre<.2,pre
    empty=deepcopy(forced);empty['fuel_groups']=[g for g in empty['fuel_groups'] if 'initial_time_s' not in g]
    none=execute(ROOT/'build/ignition/cfbt/cfast-cfbt.exe',out/'no_fuel',make_deck(empty,[],targets),gas_sidecar(empty),90,120)
    assert max(r['bulk_HRR_W'] for r in none['rooms'])==0
    report={'no_force_old_new_max_difference':difference,'forced_room_peak_W':peak,'pre_force_temperature_difference_C':pre,
            'outside_window_bulk_W':0,'other_rooms_bulk_W':0,'no_fuel_bulk_W':0,
            'scope':'lowered thresholds for software testing; not fire validation'}
    (out/'checks.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report),flush=True)


if __name__=='__main__':main()
