"""Actual-engine checks for CAD identity, flow transport, and committed ignition feedback."""
import json
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pyrocast_cfbt.model import normalize
from pyrocast_cfbt.deck import make_deck,gas_sidecar
from pyrocast_cfbt.native import execute
from pyrocast_cfbt.playback import package

base=json.loads((ROOT/'results/cad_floor/result.json').read_text('utf-8'))
trial=json.loads((ROOT/'results/cad_low_threshold/result.json').read_text('utf-8'))
assert base['simulation_complete_to_requested_horizon'] and trial['simulation_complete_to_requested_horizon']
event=trial['ignitions'][0];assert event['cad_key']=='CAD_3F_R2'
t=np.array(trial['time_s']);a=np.array(base['rooms'][event['room']]['T_upper_C']);b=np.array(trial['rooms'][event['room']]['T_upper_C'])
before=float(np.max(np.abs((b-a)[t<event['t_ign_s']])));after=float(np.max((b-a)[t>event['t_ign_s']]))
assert before<.2 and after>.1
peak=max(trial['solid_fuel_inventory'][event['group']]['actual_HRR_W'])/1000;assert peak>0
payload=package(base);assert payload['building_sha256']==base['scenario']['cad']['building_sha256']
assert len(payload['rooms'])==14 and payload['time_s'][-1]==900
assert any(row[3]>1e-10 for opening in payload['openings'] for row in opening['ab']+opening['ba'])
model=json.loads((ROOT/'examples/three_rooms.json').read_text())
model['rooms']=model['rooms'][:2];model['rooms'][1]['origin_m']=[0,0,3]
model['openings']=[{'id':'UpperExit','a':'R2','b':'OUTSIDE','face':'RIGHT','width_m':1.,'top_m':2.1,'offset_m':1.5,'schedule':[[0,1]]},
                   {'id':'Vertical','type':'FLOOR','a':'R2','b':'R1','area_m2':1.,'schedule':[[0,1]]}]
model['fuel_groups']=model['fuel_groups'][:1];model['duration_s']=30;model['output_step_s']=5;model['gas']={'enabled':False};model=normalize(model)
native=execute(ROOT/'build/cfbt/cfast-cfbt.exe',ROOT/'results/verification/vertical_transport',make_deck(model,[],[]),gas_sidecar(model),30,60)
up={}
for row in native['slabs']:
    if row['vent_index']==2 and row['room_from']==1:up[row['time_s']]=up.get(row['time_s'],0)+row['mass_kg_s']
# Smokeview writes vertical slabs in reversed order (j=2 then j=1), signed relative to the top room.
values=np.array([up.get(float(t),0) for t in native['zone']['Time']]);direct=np.abs(native['zone']['VSLABF_1_2'])
error=float(np.max(np.abs(values-direct)));assert np.allclose(values,direct,rtol=1e-8,atol=1e-9)
assert values.max()>0 and max(row['T_upper_C'] for row in native['rooms'] if row['room_index']==2)>20
checks={'floor_rooms':len(payload['rooms']),'floor_horizon_s':payload['time_s'][-1],
        'default_committed_ignitions':base['committed_ignitions_count'],
        'test_solid_threshold_C':45,'test_ignition_cad_key':event['cad_key'],'test_ignition_s':event['t_ign_s'],
        'test_pre_event_temperature_difference_C':before,'test_post_event_temperature_difference_C':after,
        'test_added_fire_peak_kW':peak,'vertical_native_flow_max_difference_kg_s':error,
        'scope':'software integration and altered-threshold functional tests; not validation of real building fire predictions'}
destination=ROOT/'results/verification/cad_connection_checks.json';destination.write_text(json.dumps(checks,indent=2),encoding='utf-8');print(json.dumps(checks,indent=2))
