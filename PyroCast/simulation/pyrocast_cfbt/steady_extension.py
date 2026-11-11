"""Finish a slow native run that has settled into a quasi-steady state with constants. Project rule, not CFAST.

A fire that is held at a constant rate (typically oxygen-limited, with far more fuel prescribed than can burn)
can pin the solver at millisecond steps although nothing is changing any more. When such a run cannot reach
the horizon inside its wall-time budget and its last window of output is steady, the native prefix is kept as
evidence and the remaining samples are written from it:

  heat release, flows, species, pressure, layer height  = last native value
  gas / surface temperatures                            = wall-heating power law of a constant fire, dT ~ t^p
  cumulative doses and totals                           = last native rate
  a planned decay of the prescribed fire                = heat release x f, temperature rise x f^(2/3)

The result is a deliberate simplification: it is reported as unverified and labelled in the limits.
"""
import csv
import json
import math
import re
import shutil
from pathlib import Path
import numpy as np
from .physics_config import defaults

REVISION = 'quasi_steady_extension_v1'
NOTICE = '준정상 상수 연장:'
FILES = ('zone', 'compartments', 'devices', 'vents', 'masses', 'walls')
WRAP = 16384   # stock CFAST wraps wider Smokeview records; those are left alone


def settings():
    cfg = defaults('quasi_steady')
    for key, value in cfg.items():
        if key in ('enabled', 'basis'): continue
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError('Invalid quasi-steady setting: '+key)
    return cfg


def overrun(pace, duration_s, timeout_s, cfg):
    """pace: [(wall_s, native_s)]; will the horizon be missed at the recent rate?"""
    now, t = pace[-1]
    old = next(((w, s) for w, s in reversed(pace) if now-w >= cfg['pace_window_s']), None)
    if old is None: return False
    rate = (t-old[1])/(now-old[0])
    return rate <= 0 or now+(duration_s-t)/rate > timeout_s


def step(t):
    """native output interval; a final off-grid sample must not set it"""
    return float(np.median(np.diff(t)))


def read_complete(path):
    """Complete native records only (a running solver may be mid-write). -> names, ids, units, array | None"""
    from .native import native_float
    try:
        with Path(path).open(encoding='utf-8-sig', newline='') as f:
            reader = csv.reader(f); first = next(reader)
            if first[0].strip() == 's': units = first; names = next(reader); ids = names
            else: names = first; next(reader); ids = next(reader); units = next(reader)
            trim = lambda row: row[:-1] if len(row) == len(names)+1 and row[-1] == '' else row
            names, ids, units = [[v.strip() for v in trim(row)] for row in (names, ids, units)]
            if not (len(names) == len(ids) == len(units)) or len(names) > WRAP or names[0] != 'Time': return None
            rows = []
            for row in reader:
                row = trim(row)
                if len(row) != len(names): continue
                try: values = [native_float(v) for v in row]
                except ValueError: continue
                if all(math.isfinite(v) for v in values): rows.append(values)
    except (OSError, StopIteration, IndexError): return None
    if len(rows) < 2: return None
    data = np.asarray(rows, float)
    if not np.all(np.diff(data[:, 0]) > 0): return None
    return names, ids, units, data


def prescribed(deck):
    """fire id -> (room, [(time_s, kW)]) from the deck's own tables"""
    tables = {}
    for m in re.finditer(r"&TABL\s+ID\s*=\s*'([^']+)',?\s*DATA\s*=\s*([^/]+)/", deck):
        v = [float(x) for x in re.split(r'[,\s]+', m[2].strip()) if x]
        tables.setdefault(m[1], []).append((v[0], v[1]))
    return {m[1]: (m[2], sorted(tables.get(m[3], [])))
            for m in re.finditer(r"&FIRE\s+ID\s*=\s*'([^']+)'\s+COMP_ID\s*=\s*'([^']+)'\s+FIRE_ID\s*=\s*'([^']+)'", deck)}


def assess(names, ids, data, deck, cfg):
    """Is the last window steady? -> dict(steady, reasons, metrics)"""
    t = data[:, 0]; dt = step(t); n = int(round(cfg['window_s']/dt)); reasons = []
    if len(t) < 3*n+1 or t[-1] < cfg['min_native_s']:
        return dict(steady=False, reasons=['native prefix shorter than three windows'], metrics={})
    col = {name: i for i, name in enumerate(names)}
    pick = lambda rx: [i for i, name in enumerate(names) if re.fullmatch(rx, name)]
    fires = prescribed(deck); hrr = pick(r'HRR_\d+'); req = pick(r'HRR_E\d+')
    actual = data[-n:, hrr].sum(1); mean = float(actual.mean()); metrics = dict(native_time_s=float(t[-1]), window_s=n*dt, actual_hrr_W=mean)
    if mean < 1e3: reasons.append('no fire')
    else:
        metrics['hrr_band'] = float((actual.max()-actual.min())/mean)
        if metrics['hrr_band'] > cfg['hrr_band']: reasons.append('heat release still changing')
    if req:
        wanted = data[-n:, req].sum(1); metrics['prescribed_hrr_W'] = float(wanted[-1])
        if wanted.max() > 0 and (wanted.max()-wanted.min())/wanted.max() > cfg['hrr_band']: reasons.append('prescribed fire still changing')
    ign = pick(r'IGN_\d+')
    if ign and np.any(data[-1, ign] != data[-2*n, ign]): reasons.append('recent ignition')
    burning = sorted({fires[ids[i]][0] for i in hrr if data[-1, i] > 1e3 and ids[i] in fires})
    room_no = {ids[i]: names[i].split('_')[-1] for i in pick(r'ULT_\d+')}
    metrics['burning_rooms'] = burning
    for room in burning:
        k = room_no.get(room)
        if k is None: continue
        o2 = col.get('ULO2_'+k); hgt = col.get('HGT_'+k)
        if o2 is not None:
            drift = abs(data[-1, o2]-data[-n, o2])*100; metrics['o2_drift_pct'] = max(metrics.get('o2_drift_pct', 0.), float(drift))
            if drift > cfg['o2_drift_pct']: reasons.append('oxygen still moving in '+room)
        if hgt is not None:
            drift = abs(data[-1, hgt]-data[-n, hgt]); metrics['layer_drift_m'] = max(metrics.get('layer_drift_m', 0.), float(drift))
            if drift > cfg['layer_drift_m']: reasons.append('smoke layer still moving in '+room)
    prs = np.abs(data[:, pick(r'PRS_\d+')]).max(1)
    metrics['pressure_Pa'] = float(prs[-1]); metrics['pressure_drift_Pa'] = float(abs(prs[-1]-prs[-n]))
    if metrics['pressure_drift_Pa'] > max(cfg['pressure_drift_Pa'], cfg['pressure_drift_fraction']*prs[-n:].max()): reasons.append('pressure still moving')
    # A temperature rise that speeds up announces flashover or a new ignition, not a steady state.
    temps = pick(r'[UL]LT_\d+'); blocks = [data[a:b, temps].mean(0) for a, b in ((-3*n, -2*n), (-2*n, -n), (-n, None))]
    d1, d2 = blocks[1]-blocks[0], blocks[2]-blocks[1]
    faster = int(np.sum((d2 > 2.) & (d2 > cfg['temperature_growth_ratio']*np.maximum(d1, 0.))))
    metrics['rooms_heating_faster'] = faster
    if faster: reasons.append(f'temperature rise accelerating in {faster} layer(s)')
    return dict(steady=not reasons, reasons=reasons, metrics=metrics)


def probe(folder, deck, duration_s, cfg):
    table = read_complete(Path(folder)/'case_compartments.csv')
    if not table: return False
    names, ids, _, data = table
    return data[-1, 0] < duration_s-1e-3 and assess(names, ids, data, deck, cfg)['steady']


def future_fire(names, ids, data, deck, new_t):
    """Scale factors for the remaining time from the prescribed tables: f actual, q pyrolysis, g vent jet."""
    t = data[:, 0]; fires = prescribed(deck); one = np.ones(len(new_t)); known = True; requested = {}
    hrr = [i for i, name in enumerate(names) if re.fullmatch(r'HRR_\d+', name)]
    for i in (i for i, name in enumerate(names) if re.fullmatch(r'HRR_E\d+', name)):
        seen = data[:, i]; table = fires.get(ids[i], (None, []))[1]
        if seen[-1] <= 0: requested[i] = np.zeros(len(new_t)); continue      # not ignited: stays off
        on = int(np.argmax(seen > 0)); best = None
        if table:
            tt, qq = np.array([a for a, _ in table]), np.array([q for _, q in table])*1000.
            for start in {0., *(float(t[j]) for j in range(max(0, on-2), min(len(t), on+2)))}:
                error = float(np.abs(np.interp(t[-3:]-start, tt, qq)-seen[-3:]).max())
                if best is None or error < best[0]: best = (error, start)
        if best is None or best[0] > max(1e3, 0.03*seen[-1]): known = False; requested[i] = np.full(len(new_t), seen[-1]); continue
        requested[i] = np.interp(new_t-best[1], tt, qq)
    held = float(data[-1, hrr].sum()); wanted = float(sum(data[-1, i] for i in requested)); total = sum(requested.values()) if requested else one*wanted
    if held <= 0 or wanted <= 0: return dict(f=one, q=one, g=one, requested=requested, known=False, growth_ignored=False)
    actual = np.minimum(held, total) if held < 0.98*wanted else total*held/wanted
    growth = bool(np.any(actual > 1.02*held))
    f = np.minimum(actual/held, 1.); excess = wanted-held
    g = np.clip((total-np.minimum(actual, held))/excess, 0., None) if excess > 1e3 else f
    return dict(f=f, q=np.minimum(total/wanted, 1.) if not growth else one, g=np.minimum(g, 1.), requested=requested, known=known, growth_ignored=growth)


def kind(name, unit):
    if name == 'Time': return 'time'
    if name.startswith(('TRGFEDG', 'TRGFEDH', 'PYTOL_T', 'TRACE_T')): return 'cumulative'
    if name.startswith('HRR_E'): return 'requested'
    if re.match(r'HRR[CLU]?_\d', name): return 'actual'
    if name.startswith('PYROL'): return 'pyrolysis'
    if name.startswith('DJET'): return 'jet'
    if unit in ('C', 'K') and not name.startswith(('TRGHGT', 'TRGPRS')): return 'temperature'   # mislabelled native units
    return 'held'


def extend(names, units, data, new_t, fire, cfg):
    """Rows for new_t from a complete prefix."""
    t = data[:, 0]; tk = t[-1]; n = int(round(cfg['window_s']/step(t))); last = data[-1]
    out = np.repeat(last[None, :], len(new_t), 0); out[:, 0] = new_t
    kinds = np.array([kind(a, b) for a, b in zip(names, units)])
    ambient = data[0]; rise = last-ambient
    b1, b2 = data[-2*n:-n].mean(0)-ambient, data[-n:].mean(0)-ambient
    with np.errstate(all='ignore'):
        p = np.log(b2/b1)/math.log(t[-n:].mean()/t[-2*n:-n].mean())
    p = np.where(np.isfinite(p), np.clip(p, 0., cfg['max_temperature_exponent']), 0.)
    hot = (kinds == 'temperature') & (rise >= cfg['min_temperature_rise_C'])
    out[:, hot] = (ambient+rise*(new_t[:, None]/tk)**p[None, :]*fire['f'][:, None]**(2/3))[:, hot]
    total = kinds == 'cumulative'
    rate = np.maximum((last-data[-n-1])/(t[-1]-t[-n-1]), 0.)
    out[:, total] = (last+rate*(new_t[:, None]-tk))[:, total]
    for label, factor in (('actual', fire['f']), ('pyrolysis', fire['q']), ('jet', fire['g'])):
        mask = kinds == label; out[:, mask] = last[mask]*factor[:, None]
    return out, dict(exponent=p[hot], counts={k: int(np.sum(kinds == k)) for k in ('temperature', 'held', 'cumulative', 'actual', 'pyrolysis', 'jet', 'requested')})


def rewrite(path, until_s, rows):
    """Keep the header and the complete native records up to until_s verbatim, then append rows."""
    from .native import native_float
    lines = Path(path).read_text(encoding='utf-8-sig').splitlines()
    head = 2 if lines[0].split(',')[0].strip() == 's' else 4
    width = rows.shape[1]; kept = lines[:head]
    for line in lines[head:]:
        cells = line.split(',')
        if len(cells) == width+1 and cells[-1].strip() == '': cells = cells[:-1]
        if len(cells) != width: continue
        try:
            if native_float(cells[0]) > until_s+1e-3: break
        except ValueError: continue
        kept.append(line)
    kept += [','.join('%.12E' % v for v in row) for row in rows]
    Path(path).write_text('\n'.join(kept)+'\n', encoding='utf-8')


def finish(folder, deck, duration_s, cfg, *, trigger, exit_kind, wall_seconds, accepted_steps):
    """Extend every native table of a stopped run to the horizon. -> evidence dict | None (nothing changed)"""
    from .native import digest
    folder = Path(folder); tables = {}
    for key in FILES:
        path = folder/f'case_{key}.csv'
        if not path.exists() or path.stat().st_size == 0: continue
        table = read_complete(path)
        if table is None: return None
        tables[key] = table
    if 'compartments' not in tables or 'zone' not in tables: return None
    until = min(float(v[3][-1, 0]) for v in tables.values())
    tables = {k: (a, b, c, d[d[:, 0] <= until+1e-3]) for k, (a, b, c, d) in tables.items()}
    names, ids, _, data = tables['compartments']
    if until >= duration_s-1e-3 or any(abs(v[3][-1, 0]-until) > 1e-3 for v in tables.values()): return None
    verdict = assess(names, ids, data, deck, cfg)
    if not verdict['steady']: return None
    dt = step(data[:, 0]); new_t = np.arange(until+dt, duration_s+dt/2, dt)
    if abs(new_t[-1]-duration_s) > 1e-6: new_t = np.append(new_t[new_t < duration_s-1e-6], float(duration_s))
    fire = future_fire(names, ids, data, deck, new_t)
    prefix = folder/'native-prefix'
    if prefix.exists(): shutil.rmtree(prefix)     # belongs to a run this one replaces
    prefix.mkdir()
    for path in [*folder.glob('case*.csv'), *(folder/n for n in ('case.in', 'case.cfbt', 'case.log', 'execution.log', 'case.status'))]:
        if path.is_file(): shutil.copy2(path, prefix/path.name)
    counts = {}; exponents = np.array([])
    for key, (a, b, units, d) in tables.items():
        rows, note = extend(a, units, d, new_t, fire, cfg)
        if key == 'compartments':
            exponents = note['exponent']
            for i, series in fire['requested'].items(): rows[:, i] = series
        counts[key] = note['counts']; rewrite(folder/f'case_{key}.csv', until, rows)
    info = dict(revision=REVISION, trigger=trigger, native_exit=exit_kind, native_until_s=until, horizon_s=float(duration_s),
                extended_samples=int(len(new_t)), wall_seconds=float(wall_seconds), accepted_steps=int(accepted_steps),
                criteria=verdict['metrics'], settings={k: v for k, v in cfg.items() if k != 'basis'},
                temperature_exponent=dict(median=float(np.median(exponents)) if len(exponents) else None,
                                          max=float(exponents.max()) if len(exponents) else None, columns=int(len(exponents))),
                prescribed_fire=dict(known=fire['known'], growth_ignored=fire['growth_ignored'],
                                     actual_factor_end=float(fire['f'][-1]), actual_factor_min=float(fire['f'].min())),
                columns=counts, prefix_files={p.name: digest(p) for p in sorted(prefix.iterdir())},
                basis='project simplification of a quasi-steady native run; values after native_until_s are not CFAST output')
    (folder/'steady-extension.json').write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding='utf-8')
    return info


def notice(info):
    clock = lambda s: '%d:%02d' % divmod(int(round(s)), 60)
    return (f"{NOTICE} 순정 CFAST 계산은 {clock(info['native_until_s'])}까지 · 이후 {clock(info['horizon_s'])}까지 발열량·산소·압력·유량은 마지막 값으로 고정, "
            '온도는 일정 화원의 벽 가열 추세로 연장 · 계산 시간 한도 안에 끝나지 않는 준정상 상태의 단순화이며 순정 CFAST 완주 결과가 아님')


def qualify(validation, info):
    """The native prefix was screened; the extended part cannot be, so the run is never reported as valid."""
    validation = dict(validation); validation['unknown'] = [*validation.get('unknown', []), 'quasi_steady_extension']
    if validation['status'] == 'valid': validation['status'] = 'unverified'
    validation['passed'] = False
    validation['steady_extension'] = {k: info[k] for k in ('revision', 'trigger', 'native_until_s', 'horizon_s')}
    return validation
