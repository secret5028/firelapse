"""Reproducible high-fuel case; ignitions are calculated, never time-scripted."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'simulation'))
from pyrocast_cfbt.cad import adapt
from pyrocast_cfbt.model import normalize
from pyrocast_cfbt.spread import simulate
from pyrocast_cfbt.playback import package
from pyrocast_cfbt.practical import execution_limits


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--primary', default='R1')
    p.add_argument('--primary-kw', type=float, default=50000)
    p.add_argument('--secondary-kw', type=float, default=8000)
    p.add_argument('--loaded-passages', action='store_true')
    p.add_argument('--large-room-cap-kw', type=float)
    p.add_argument('--fire-base-m',type=float,help='Explicit floor-fuel plume base, separate from the heated proxy surface')
    p.add_argument('--passage-kw',type=float,help='Separate supply cap for fuel-loaded circulation rooms')
    p.add_argument('--ventilated',action='store_true',help='All facade windows initially50% area open; stair doors open')
    p.add_argument('--build-only', action='store_true')
    a = p.parse_args()
    project = Path(r'C:\Users\<user>\Documents\Codex\2026-10-14\files-pasted-by-the-user-cad3d')
    options = dict(profile='practical', scope_floor='3F', fire_floor='3F', fire_room=a.primary,
                   duration_s=3600, full_floor_search=True, iteration_mode='fixed_point', window_fraction=.5,
                   window_breakage=dict(enabled=True, threshold=450, post_fraction=1),
                   opening_overrides={'CAD_3F_D1': 0, 'CAD_3F_D3': 0, 'CAD_3F_W0': 0, 'CAD_3F_W2': 0})
    if a.fire_base_m is not None:options['fuel_source_base_m']=a.fire_base_m
    if a.ventilated:options['opening_overrides']={}
    m = adapt(project, options)
    for v in m['openings']:
        if v['b'] != 'OUTSIDE' and (not a.ventilated or 'window' not in v.get('kind','')) and (a.ventilated or v['id'] not in ('CAD_3F_D1', 'CAD_3F_D3')) and '_EV' not in v['id']:
            v['schedule'] = [[0, 1]]
    for g in m['fuel_groups']:
        room = next(r for r in m['rooms'] if r['id'] == g['room'])
        g['energy_MJ'] *= 3
        g['fuel_area_m2'] = min(room['area_m2']*.65, g['fuel_area_m2']*2)
        g['growth_kW_s2'] = .1875
        g['hrrpua_kW_m2'] = 400
        g['peak_kW'] = a.primary_kw if 'initial_time_s' in g else a.secondary_kw
        g['basis'] = 'high-fuel scenario: default energy x3, fuel footprint x2 (floor cap65%), prescribed t2; not surveyed'
        if a.loaded_passages and g.get('usage') == 'passage':
            g['energy_MJ'] = room['area_m2']*1200
            g['fuel_area_m2'] = room['area_m2']*.5
            g['basis'] += '; passage contents assumed1200MJ/m2 and50% floor footprint: severe combustible-storage scenario'
            if a.passage_kw is not None and 'initial_time_s' not in g:g['peak_kW']=a.passage_kw
        if a.large_room_cap_kw and room['area_m2'] > 300 and 'initial_time_s' not in g:
            g['peak_kW'] = a.large_room_cap_kw
    m['flashover'].update(enabled=True, max_supply_kW=a.secondary_kw,
                         max_supply_by_room_kW={'CAD_3F_'+a.primary: a.primary_kw}, radiation_points=4)
    if a.large_room_cap_kw:
        m['flashover']['max_supply_by_room_kW'].update({g['room']:a.large_room_cap_kw for g in m['fuel_groups']
            if next(r for r in m['rooms'] if r['id']==g['room'])['area_m2']>300 and 'initial_time_s' not in g})
    if a.passage_kw is not None:
        m['flashover']['max_supply_by_room_kW'].update({g['room']:a.passage_kw for g in m['fuel_groups']
            if g.get('usage')=='passage' and 'initial_time_s' not in g})
    m['spread'].update(execution_limits(m['duration_s']))
    m['demonstration'] = dict(label='3F 고연료·연소 전이 탐색 · 1시간', target_rooms=16,
        denominator_indoor_rooms=len(m['rooms']), source=a.primary,
        primary_peak_kW=a.primary_kw, secondary_peak_cap_kW=a.secondary_kw,
        fuel_energy_multiplier=3, no_forced_ignition_times=True,
        loaded_passages=a.loaded_passages, large_room_cap_kW=a.large_room_cap_kw,
        fire_source_base_m=a.fire_base_m,
        passage_supply_cap_kW=a.passage_kw,
        opening_policy='all exterior windows50% effective area and interior/stair doors open' if a.ventilated else 'controlled closed W0/W2 and stair doors',
        limitations='Scenario assumptions; 16 burning rooms is a target, not a prescribed result.')
    m = normalize(m)
    a.output.mkdir(parents=True, exist_ok=True)
    (a.output/'scenario.json').write_text(json.dumps(m, ensure_ascii=False, indent=2), 'utf-8')
    print(json.dumps({'state': 'running', 'rooms': len(m['rooms']), 'groups': len(m['fuel_groups']),
                      'primary': a.primary, 'target': 16, 'duration_s': 3600}), flush=True)
    if a.build_only: return
    started = time.monotonic()
    result = simulate(m, ROOT/'simulation/build/mixture_r2/cfbt/cfast-cfbt.exe', a.output)
    payload = package(result)
    (a.output/'playback.json').write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(',', ':')), 'utf-8')
    print(json.dumps({'state': result['terminated'], 'wall_s': time.monotonic()-started,
                      'events': len(result['ignitions']), 'fires': payload.get('fire_scope_summary')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
