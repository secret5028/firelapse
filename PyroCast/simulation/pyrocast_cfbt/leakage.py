"""A documented aggregate path through the rest of the building, not soil leakage."""
import math
from .physics_config import defaults
from .basement_pressure import configure, below_grade

BOUNDARY_REVISION = 'basement_pressure_boundary_v3'


def remove_assumed_leaks(model):
    """Before sampling/ranking real openings; regenerate for each chosen scenario."""
    model['openings']=[v for v in model.get('openings',[]) if not v.get('minimum_leakage')]
    model.pop('minimum_leakage',None)
    model.pop('basement_pressure',None)
    model['limits']=[s for s in model.get('limits',[]) if not s.startswith(('최소 누기 가정 적용:','지하 압력 간략식:'))]
    return model


def apply_minimum_leakage(model):
    model['boundary_revision'] = BOUNDARY_REVISION
    settings = {**defaults('leakage'), **model.get('leakage_defaults', {})}
    if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in settings.values()):
        raise ValueError('Minimum leakage dimensions must be finite positive values')
    model['leakage_defaults'] = settings
    rooms = {r['id']: r for r in model['rooms']}
    warnings = model.setdefault('warnings', [])
    for r in rooms.values():
        below = below_grade(r,model)
        if below:
            r.setdefault('leak_area_ratio', [0., 0.])
            note = '지하 판정: '+r['id']+' (below_grade 또는 지반 대비 표고)'
            if note not in warnings: warnings.append(note)
    # Repeated normalization and changed schedules must not retain obsolete assumptions.
    openings = [v for v in model.get('openings', []) if not v.get('minimum_leakage')]
    graph = {k: set() for k in [*rooms, 'OUTSIDE']}
    def link(a, b):
        if a in graph and b in graph: graph[a].add(b); graph[b].add(a)
    for v in openings:
        # A door that closes later is not a permanent pressure relief path.
        # Keep the small, declared passive leakage in addition to its schedule.
        if min(row[1] for row in v.get('schedule', [[0, 1]])) > 0:
            link(v['a'], v['b'])
    for r in rooms.values():
        if any(x > 0 for x in r.get('leak_area_ratio', [.00017, .000052])):
            link(r['id'], 'OUTSIDE')
    # A fan can stop (including its native pressure cutoffs). Its nominal flow
    # is not evidence of a permanent passive connection to ambient.
    assumptions = []
    visited = set()
    origins = [g['room'] for g in model['fuel_groups'] if 'initial_time_s' in g]
    for origin in origins:
        if origin in visited: continue
        component, pending = set(), [origin]
        while pending:
            r = pending.pop()
            if r in component: continue
            component.add(r); pending.extend(graph[r]-component)
        visited.update(component)
        if 'OUTSIDE' in component: continue
        cores = [rooms[r] for r in sorted(component) if rooms[r].get('core_kind') in ('stair', 'stairs', 'stairwell', 'elevator', 'elev', 'lift')]
        candidates = cores or [max((rooms[r] for r in sorted(component)), key=lambda r:r['size_m'][0]*r['size_m'][1])]
        for room in candidates:
            kind = room.get('core_kind', '')
            key = 'elevator_area_m2' if kind in ('elevator','elev','lift') else 'stair_area_m2' if cores else 'fallback_area_m2'
            area = settings[key]; height = min(settings['height_m'], room['size_m'][2])
            if area / height > room['size_m'][0]: raise ValueError('Leak opening exceeds room width')
            vent = dict(id='MINLEAK_'+room['id'], a=room['id'], b='OUTSIDE', type='WALL',
                        face='FRONT', offset_m=0., bottom_m=0., top_m=height, width_m=area/height,
                        schedule=[[0.,1.]], minimum_leakage=True,
                        basis='aggregate closed-door path through omitted building to ambient; not measured')
            openings.insert(0, vent)
            assumptions.append(dict(room=room['id'], area_m2=area, basis=vent['basis']))
    model['openings'] = openings
    model['minimum_leakage'] = assumptions
    model['limits'] = [s for s in model.get('limits', []) if not s.startswith('최소 누기 가정 적용:')]
    if assumptions:
        model['limits'].append('최소 누기 가정 적용: '+', '.join(a['room'] for a in assumptions)+
                               f", 총 {sum(a['area_m2'] for a in assumptions):g} m² (건물 나머지 경로의 등가 가정)")
    configure(model)
