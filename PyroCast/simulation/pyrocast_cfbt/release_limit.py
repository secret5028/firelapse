"""Limit the prescribed fuel release of a fire that only an assumed equivalent path connects to ambient. Project rule.

The fuel curves come from floor area and fire load; they do not know how much air the fire can get. In a sealed
component (the cases that receive a MINLEAK equivalent path) they can prescribe several times what can burn, the
surplus leaves as unburned gas, and the native solver crawls or loses its mass balance. The existing room rule cap
k*1500*max(A sqrt(H)) does not apply there because no real aperture exists.

Burnable heat is taken from two constants:
  the air already inside   volume * density * heat per kg of air * usable fraction
  the equivalent path      air factor * A * sqrt(H) * heat per kg of air        (0.5 A sqrt(H) kg/s, 3 MJ/kg -> 1500 A sqrt(H) kW)
A curve is followed until its released heat exceeds that budget; from then on it releases excess_release_ratio
times the path supply. The fuel is not removed: what was held back burns later.
"""
import math
import numpy as np
from .physics_config import defaults

REVISION = 'sealed_release_limit_v1'
NOTE = '밀폐 구역 연료 방출 제한:'


def settings(model):
    cfg = {**defaults('fuel_release_limit'), **model.get('fuel_release_limit_settings', {})}
    if type(cfg['enabled']) is not bool: raise ValueError('Fuel release limit enabled must be boolean')
    for key, value in cfg.items():
        if key in ('enabled', 'basis'): continue
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError('Invalid fuel release limit setting: '+key)
    if cfg['usable_oxygen_fraction'] > 1 or cfg['excess_release_ratio'] < 1: raise ValueError('Invalid fuel release limit bounds')
    return cfg


def sealed_components(model):
    """(rooms, equivalent vents) of each fire origin that reaches ambient only through an assumed path."""
    rooms = {r['id']: r for r in model['rooms']}
    real = [v for v in model.get('openings', []) if not v.get('minimum_leakage')]
    graph = {k: set() for k in [*rooms, 'OUTSIDE']}
    def link(a, b):
        if a in graph and b in graph: graph[a].add(b); graph[b].add(a)
    for v in real:
        if min(row[1] for row in v.get('schedule', [[0, 1]])) > 0: link(v['a'], v['b'])
    for r in rooms.values():
        if any(x > 0 for x in r.get('leak_area_ratio', [.00017, .000052])): link(r['id'], 'OUTSIDE')
    seen = set()
    for origin in [g['room'] for g in model['fuel_groups'] if 'initial_time_s' in g]:
        if origin in seen or origin not in graph: continue
        component, pending = set(), [origin]
        while pending:
            rid = pending.pop()
            if rid in component: continue
            component.add(rid); pending.extend(graph[rid]-component)
        seen.update(component)
        if 'OUTSIDE' in component: continue
        # A door that opens later or a fan brings air this budget does not know about.
        opens_later = any((v['a'] in component) != (v['b'] in component) and max(row[1] for row in v.get('schedule', [[0, 1]])) > 0 for v in real)
        fan = any(v.get('comp') in component for v in model.get('mechanical_vents', []))
        vents = [v for v in model.get('openings', []) if v.get('minimum_leakage') and v['a'] in component]
        if opens_later or fan or not vents: continue
        yield sorted(component), vents


def apply(model):
    """Attach a release budget to every fuel group of a sealed component (idempotent)."""
    from .deck import prescribed_curve
    for g in model['fuel_groups']: g.pop('release_limit', None)
    model.pop('fuel_release_limit', None)
    model['limits'] = [s for s in model.get('limits', []) if not s.startswith(NOTE)]
    cfg = settings(model)
    if not cfg['enabled']: return model
    rooms = {r['id']: r for r in model['rooms']}; records = []
    for component, vents in sealed_components(model):
        volume = sum(math.prod(rooms[r]['size_m']) for r in component)
        store = volume*cfg['air_density_kg_m3']*cfg['air_energy_kJ_kg']*cfg['usable_oxygen_fraction']
        geometry = sum(v['width_m']*(v['top_m']-v.get('bottom_m', 0))*math.sqrt(v['top_m']-v.get('bottom_m', 0)) for v in vents)
        supply = cfg['opening_air_factor_kg_s_m25']*geometry*cfg['air_energy_kJ_kg']
        groups = [g for g in model['fuel_groups'] if g['room'] in component]
        peaks = [max(prescribed_curve(g, math.prod(rooms[g['room']]['size_m'][:2]))[1]) for g in groups]
        if not groups or sum(peaks) <= 0: continue
        for g, peak in zip(groups, peaks):
            share = peak/sum(peaks)
            g['release_limit'] = dict(revision=REVISION, share=share, store_kJ=store*share, supply_kW=supply*share,
                                      excess_release_ratio=cfg['excess_release_ratio'], ramp_s=cfg['ramp_s'])
        records.append(dict(revision=REVISION, rooms=component, volume_m3=volume, stored_air_energy_MJ=store/1000, path_A_sqrt_H=geometry,
                            path_supply_kW=supply, limited_release_kW=cfg['excess_release_ratio']*supply, prescribed_peak_kW=sum(peaks),
                            fuel_groups=[g['id'] for g in groups], settings={k: v for k, v in cfg.items() if k != 'basis'}, basis=cfg['basis']))
    if records:
        model['fuel_release_limit'] = records
        for r in records:
            model['limits'].append(f"{NOTE} 구역 공기로 탈 수 있는 열량 {r['stored_air_energy_MJ']/1000:.3g} GJ와 등가 경로 유입 {r['path_supply_kW']:.4g} kW를 넘으면 "
                                   f"지정 방출률(최대 {r['prescribed_peak_kW']/1000:.3g} MW)을 {r['limited_release_kW']:.4g} kW로 낮춤 · 연료 총량은 유지 · 환기 지배 간략식, 실측 아님")
    return model


def limited_curve(t, q, area, limit):
    """Follow (t, q) until its released heat exceeds the budget, then hold the limited rate until the fuel is spent."""
    t, q, area = (np.asarray(v, float) for v in (t, q, area))
    cap = limit['excess_release_ratio']*limit['supply_kW']
    grid = np.unique(np.concatenate([t, np.arange(0., t[-1], 1.)])); rate = np.interp(grid, t, q)
    energy = np.concatenate([[0.], np.cumsum((rate[1:]+rate[:-1])/2*np.diff(grid))])
    over = (energy >= limit['store_kJ']+limit['supply_kW']*grid) & (rate > cap)
    if not over.any(): return list(t), list(q), list(area)
    k = int(np.argmax(over)); start = float(grid[k]); ramp = limit['ramp_s']
    left = float(energy[-1]-energy[k])-(rate[k]+cap)/2*ramp-cap*ramp/2      # both ramps carry fuel too
    hold = max(left, 0.)/cap
    size = float(np.interp(start, t, area)); small = max(float(area.min()), size*cap/rate[k])
    before = t < start
    return ([*t[before], start, start+ramp, start+ramp+hold, start+2*ramp+hold],
            [*q[before], float(rate[k]), cap, cap, 0.],
            [*area[before], size, small, small, float(area.min())])
