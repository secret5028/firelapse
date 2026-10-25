from pathlib import Path
import argparse
import json
from .spread import simulate
from .practical import apply_profile

parser=argparse.ArgumentParser(description='CFAST gas-reaction and representative solid-spread scenario')
parser.add_argument('scenario',type=Path)
parser.add_argument('--engine',type=Path,default=Path(__file__).resolve().parents[1]/'build/cfbt/cfast-cfbt.exe')
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--profile',choices=['practical','legacy'],default='practical')
parser.add_argument('--spread-model',choices=['existing','room-rule'],default=None)
parser.add_argument('--room-preset',choices=['conservative','standard','aggressive'],default='standard')
parser.add_argument('--room-flux',type=float,help='Native incident flux setpoint, kW/m2')
parser.add_argument('--room-ramp',type=float,help='Prescribed room supply ramp, seconds')
parser.add_argument('--room-trigger',choices=['floor_r2','fuel_r3','fuel_r4','ceiling_r4','floor_r4','parent_r5'],default=None)
parser.add_argument('--room-threshold-multiplier',type=float)
parser.add_argument('--room-vent-cap-k',type=float,help='Opt in to numerical single-opening supply cap')
args=parser.parse_args()
raw=apply_profile(json.loads(args.scenario.read_text(encoding='utf-8')),args.profile)
if args.spread_model=='room-rule':
    if args.room_trigger is None:parser.error('Room-rule standard is pending approval; explicitly choose --room-trigger')
    raw['room_fire_rule']={'enabled':True,'preset':args.room_preset,'trigger_mode':args.room_trigger}
    if args.room_flux is not None:raw['room_fire_rule']['setpoint']=args.room_flux
    if args.room_ramp is not None:raw['room_fire_rule']['ramp_s']=args.room_ramp
    if args.room_threshold_multiplier is not None:raw['room_fire_rule']['threshold_multiplier']=args.room_threshold_multiplier
    if args.room_vent_cap_k is not None:raw['room_fire_rule'].update(vent_cap_enabled=True,vent_cap_k=args.room_vent_cap_k)
elif args.spread_model=='existing':raw.setdefault('room_fire_rule',{})['enabled']=False
result=simulate(raw,args.engine,args.output)
print(json.dumps({k:result[k] for k in ('terminated','successful_runs_count','committed_ignitions_count','fo_transitions','error')},ensure_ascii=False,indent=2))
print(args.output.resolve()/'result.json')
