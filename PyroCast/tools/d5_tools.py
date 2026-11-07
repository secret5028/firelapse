"""Read-only D-5 evidence helpers. No solver or route recalculation here."""
import math
from bisect import bisect_right


def finite(value):
    return type(value) in (float, int) and math.isfinite(value)


def windows(timeline, phenomenon, threshold=100):
    kind = {'BD': 'backdraft'}.get(phenomenon, phenomenon)
    if kind not in ('FO', 'FGI', 'backdraft', 'rollover') or not finite(threshold) or threshold < 0:
        raise ValueError('현상/기준 오류')
    intervals = []; evaluated = False; partial = False
    for cell in timeline['cells']:
        active = None
        for row in cell['rows']:
            value = row['indices'].get('FGI' if kind == 'rollover' else kind)
            if kind == 'rollover':
                flag = row.get('rollover_active')
                value = None if flag is None else value if flag else 0
            known = finite(value); evaluated |= known; partial |= not known
            if known and value >= threshold:
                if active is None:
                    active = dict(t_start=row['time_s'], t_end=None, peak=value,
                                  t_peak=row['time_s'], cell=cell['cell'])
                elif value > active['peak']:
                    active.update(peak=value, t_peak=row['time_s'])
            elif active is not None:
                # Exclusive end: first saved 10 s point below threshold or unknown.
                active['t_end'] = row['time_s']; intervals.append(active); active = None
        if active is not None: intervals.append(active)
    return dict(room=timeline['room'], phenomenon=phenomenon, threshold=threshold,
                evaluated=evaluated, partial=partial, windows=intervals,
                aggregation=timeline['aggregation'], source_end_s=timeline['source_end_s'],
                sampling=timeline['sampling'], end_convention='exclusive; null = through last saved 10 s sample')


def fraction_at(opening, t, times=()):
    """Read a saved opening fraction without inferring one from an open flag."""
    value = None
    schedule = opening.get('schedule')
    if isinstance(schedule, list):
        for pair in schedule:
            if len(pair) == 2 and finite(pair[0]) and finite(pair[1]) and pair[0] <= t:
                value = pair[1]
    elif isinstance(opening.get('fraction'), list):
        i = bisect_right(times, t) - 1
        if 0 <= i < len(opening['fraction']): value = opening['fraction'][i]
    elif finite(opening.get('effective_fraction')): value = opening['effective_fraction']
    return value


def state_at(opening, t, times=()):
    """Saved right-hand schedule, or saved sample at/before t. No interpolation."""
    value = fraction_at(opening, t, times)
    if value is None and not any(isinstance(opening.get(k), list) for k in ('schedule', 'fraction')):
        if type(opening.get('open')) is bool: value = int(opening['open'])
    return 'unknown' if not finite(value) else 'open' if value > 0 else 'closed'


def hose_segments(result, building, hose_m=15):
    route = result['route']
    if route.get('error'): return []
    length = route['length']; parts = route.get('segments', [])
    names = {r['id']: r.get('name') or r['id'] for r in building['rooms']}
    openings = {r['id']: r for r in building['openings']}
    crossings = []
    # Door locations come from the existing route's room transition, not projection.
    entry = next((s for s in parts if s.get('room')), None)
    if entry: crossings.append((entry['start'], route.get('entry')))
    for a, b in zip(parts, parts[1:]):
        if a.get('room') != b.get('room'):
            edge = next((e for e in route.get('edges', [])
                         if e['kind'] != 'stair' and e['from'] == a.get('room') and e['to'] == b.get('room')), None)
            if edge: crossings.append((a['end'], edge['id']))
    output = []
    for i in range(math.ceil(length / hose_m)):
        start, end = i * hose_m, min(length, (i + 1) * hose_m)
        rooms = []; stairs = 0
        for part in parts:
            enter, leave = max(start, part['start']), min(end, part['end'])
            if leave <= enter: continue
            rid = part.get('room')
            if rooms and rooms[-1]['id'] == rid: rooms[-1]['exit_m'] = leave
            else: rooms.append(dict(id=rid, name=names.get(rid, '외부' if rid is None else rid), enter_m=enter, exit_m=leave))
            # Count the saved stair segment once where it begins, even if it spans hoses.
            if part.get('stair') and start <= part['start'] < end: stairs += 1
        doors = [dict(id=key, state=openings.get(key, {}).get('state', 'unknown'))
                 for distance, key in crossings if start <= distance < end or distance == end == length]
        output.append(dict(n=i + 1, from_m=start, to_m=end, rooms=rooms, stairs=stairs, doors=doors))
    return output
