"""Declared HRR input, distinct from CFAST's oxygen-constrained output."""
import json
import math
from pathlib import Path


def load_design(path, duration):
    d = json.loads(Path(path).read_text(encoding='utf8'))
    tabulated = d.get('curve_type') == 'tabulated'
    for k in ('peak_kW', 'max_duration_seconds', 'area_m2', 'heat_of_combustion_kJ_kg'):
        if not math.isfinite(d[k]) or d[k] <= 0:
            raise ValueError(f'{k} must be finite and positive')
    for k in ('base_height_m', 'co_yield', 'soot_yield'):
        if not math.isfinite(d[k]) or d[k] < 0:
            raise ValueError(f'{k} must be finite and nonnegative')
    if not 0 <= d['radiative_fraction'] <= 1:
        raise ValueError('radiative_fraction must be between 0 and 1')
    if not tabulated and (d['sample_seconds'] != int(d['sample_seconds']) or d['sample_seconds'] < 1):
        raise ValueError('sample_seconds must be a positive integer')
    if set(d['formula']) - {'CARBON', 'HYDROGEN', 'OXYGEN', 'NITROGEN', 'CHLORINE'}:
        raise ValueError('Unsupported fuel element')
    if any(not math.isfinite(v) or v < 0 for v in d['formula'].values()):
        raise ValueError('Invalid fuel composition')
    if d['formula'].get('CARBON', 0) <= 0 or d['formula'].get('HYDROGEN', 0) <= 0:
        raise ValueError('CFAST fuel must contain carbon and hydrogen')
    if duration <= 0 or duration > d['max_duration_seconds']:
        raise ValueError('Requested duration exceeds declared fire scenario horizon')
    if tabulated:
        table = d['hrr_kW']
        if not 2 <= len(table) <= 200 or any(len(p) != 2 or any(not math.isfinite(v) or v < 0 for v in p) for p in table):
            raise ValueError('Invalid tabulated fire')
        if table[0][0] != 0 or table[-1][0] < duration or any(b[0] <= a[0] for a,b in zip(table,table[1:])):
            raise ValueError('Tabulated fire must cover horizon with increasing times')
        table = [p for p in table if p[0] < duration] + [[duration, interpolate(table,duration)]]
        return summarize(d, table, duration)
    for k in ('growth_seconds', 'sample_seconds', 'steady_seconds', 'decay_seconds'):
        if not math.isfinite(d[k]) or d[k] < 0 or (k in ('growth_seconds','sample_seconds') and d[k] == 0):
            raise ValueError(f'Invalid {k}')
    if d['end_behavior'] not in ('hold', 'zero'):
        raise ValueError('Declare hold or zero end behavior')
    if d['end_behavior'] == 'zero' and d['decay_seconds'] <= 0:
        raise ValueError('A finite fire must specify a positive decay duration')
    if d['end_behavior'] == 'hold' and d['decay_seconds'] != 0:
        raise ValueError('Hold scenario must have zero decay duration')
    g, plateau, decay = d['growth_seconds'], d['steady_seconds'], d['decay_seconds']
    stop = g + plateau + decay
    if d['end_behavior'] == 'hold' and duration > stop:
        raise ValueError('Requested duration exceeds specified steady period')
    ts = {0., float(duration)}
    ts.update(float(t) for t in range(0, duration + 1, int(d['sample_seconds'])))
    ts.update(t for t in (g, g + plateau, stop) if 0 <= t <= duration)
    if len(ts) > 200:
        raise ValueError('CFAST fire table exceeds 200 points')

    def q(t):
        if t <= g:
            return d['peak_kW'] * (t / g) ** 2
        if t <= g + plateau or d['end_behavior'] == 'hold':
            return d['peak_kW']
        return d['peak_kW'] * max(0, (stop - t) / decay) ** 2

    table = [[t, round(q(t), 6)] for t in sorted(ts)]
    return summarize(d, table, duration)


def summarize(d, table, duration):
    # Integrate exactly the piecewise-linear input CFAST receives, not an ideal curve.
    energy = sum((b[0] - a[0]) * (a[1] + b[1]) / 2000 for a, b in zip(table, table[1:]))
    return dict(d, hrr_kW=table, prescribed_energy_MJ=energy,
                equivalent_fuel_kg=energy * 1000 / d['heat_of_combustion_kJ_kg'],
                energy_scope='지정 계산시간 내 입력 열량 · 실제 방출 열량과 구분')


def interpolate(table, t):
    for a, b in zip(table, table[1:]):
        if t <= b[0]:
            return a[1] + (b[1] - a[1]) * (t - a[0]) / (b[0] - a[0])
    return table[-1][1]
