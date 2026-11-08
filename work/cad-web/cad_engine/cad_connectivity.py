"""One compartment/opening contract for CAD, 3D and the prototype solver.

Tolerances are drafting heuristics in metres, not regulatory criteria.
Unknown connectivity is retained explicitly; it never implies outside air.
"""
import math
from collections import Counter
import numpy as np
from shapely.geometry import Point, LineString
from cad_evidence import geometry, polygon_parts, opening_parts
from cad_topology import connection_status


def opening_fraction(value, unit='percent'):
    allowed = {'percent': (0., 50., 100.), 'fraction': (0., .5, 1.)}
    if unit not in allowed:
        raise ValueError('opening_unit must be percent or fraction')
    value = float(value)
    if not math.isfinite(value) or value not in allowed[unit]:
        raise ValueError(f'opening state must be {allowed[unit]} with unit={unit}')
    return value / 100 if unit == 'percent' else value


def aperture_frame(o):
    g = geometry(opening_parts(o))
    if g.is_empty: return None
    leaves = o.get('leaves') or []
    if leaves:
        leaf = leaves[0]
        u = np.asarray(leaf['closed']) - np.asarray(leaf['hinge'])
    else:
        rect = g.minimum_rotated_rectangle
        if rect.geom_type != 'Polygon': return None
        xy = np.array(rect.exterior.coords[:4])
        edges = np.roll(xy, -1, axis=0) - xy
        u = max(edges, key=np.linalg.norm)
    norm = np.linalg.norm(u)
    if norm < 1e-8: return None
    u = u / norm; n = np.array([-u[1], u[0]])
    c = np.array([g.centroid.x, g.centroid.y])
    points = np.array(g.minimum_rotated_rectangle.exterior.coords[:4]) - c
    return g, c, u, n, float(np.max(abs(points @ u))), float(np.max(abs(points @ n)))


def recover_connections(plan):
    """Recover only existing CAD apertures with two unambiguous, visible sides.

    Three transects must agree. Rays cannot cross an intervening solid wall,
    and outside is allowed only at the actual footprint boundary.
    """
    rooms = [(r['id'], geometry(polygon_parts(r))) for r in plan['rooms']]
    ids = {rid for rid, _ in rooms}
    walls = geometry(plan.get('walls', []))
    foot = geometry(plan.get('footprint', []))
    changes = []
    for o in plan['openings']:
        status = connection_status(o, ids)
        if status not in ('unresolved', 'same_space') or o['kind'] == 'vent': continue
        frame = aperture_frame(o)
        if frame is None: continue
        g, c, u, n, half_width, half_depth = frame
        solid = walls.difference(g.buffer(.06))
        votes = []
        for along in (-.25, 0, .25):
            origin = c + u * half_width * along
            pair = []
            for sign in (-1, 1):
                hit = None
                for extra in (.04, .1, .2, .35, .5):
                    target = origin + sign*n*(half_depth+extra)
                    ray = LineString([origin, target]); point = Point(target)
                    if ray.intersection(solid).length > .06: break
                    candidates = [rid for rid, room in rooms if room.contains(point)]
                    if len(candidates) == 1:
                        hit = candidates[0]; break
                    if len(candidates) > 1: break
                    if (not foot.is_empty and not foot.buffer(.04).contains(point)
                            and g.distance(foot.boundary) <= .12
                            and ray.intersects(foot.boundary)):
                        hit = 'out'; break
                pair.append(hit)
            votes.append(tuple(pair))
        if len(set(votes)) != 1: continue
        sides = list(votes[0])
        if None in sides or sides[0] == sides[1]: continue
        old = o.get('sides')
        o['sides'] = sides; o['connection_status'] = connection_status(o, ids)
        if o['kind'] in ('window', 'window_inner'):
            o['kind'] = 'window' if 'out' in sides else 'window_inner'
        evidence = dict(rule='CAD_aperture_three_transects',previous_sides=old,
                        max_search_m=.5,wall_crossing_tolerance_m=.06)
        o['connection_evidence'] = evidence
        changes.append(dict(rule='AUTO개구부연결복구',id=o['id'],sides=sides,
                            note='기존 CAD 개구부의 3개 횡단선에서 동일한 양쪽 공간 확인'))
    plan['checks'].extend(changes)
    plan.setdefault('automatic_repairs', []).extend(changes)
    return plan


def opening_dimensions(o, defaults=None):
    defaults = defaults or {}
    width = o.get('span')
    source = 'CAD_span'
    if not width:
        width = sum(l.get('r_std') or l.get('r') or 0 for l in o.get('leaves', []))
        source = 'CAD_leaf'
    if not width:
        frame = aperture_frame(o)
        # The area centroid of an asymmetric door symbol is not its bounds midpoint.
        points = np.asarray(frame[0].minimum_rotated_rectangle.exterior.coords[:4]) if frame else None
        width = float(np.ptp(points @ frame[2])) if frame else None
        source = 'CAD_aperture_envelope'
    if not width or not math.isfinite(width) or width <= 0:
        raise ValueError(f"Opening {o['id']} has no valid width")
    window = o['kind'] in ('window', 'window_inner')
    bottom = float(o.get('sill') if o.get('sill') is not None else defaults.get('sill', .9)) if window else 0.
    top = float(o.get('head') if o.get('head') is not None else defaults.get('head', 2.2)) if window else float(o.get('door_h') or defaults.get('door_h', 2.1))
    if top <= bottom: raise ValueError(f"Invalid height for {o['id']}")
    return dict(width_m=round(float(width), 4), bottom_m=bottom, top_m=top,
                height_m=top-bottom, area_m2=float(width)*(top-bottom),
                width_source=source, height_source='CAD_override_or_floor_default')


def build_graph(rooms, openings, defaults=None):
    ids = {r['id'] for r in rooms}; links = []; excluded = []; degree = Counter()
    if len(ids) != len(rooms): raise ValueError('Duplicate room IDs')
    if len({o['id'] for o in openings}) != len(openings): raise ValueError('Duplicate opening IDs')
    for o in openings:
        status = connection_status(o, ids)
        o['connection_status'] = status
        if status not in ('interior', 'exterior') or o['kind'] == 'vent':
            excluded.append(dict(id=o['id'],reason='non_flow_symbol' if o['kind']=='vent' else status))
            continue
        dim = opening_dimensions(o, defaults)
        links.append(dict(id=o['id'],kind=o['kind'],sides=list(o['sides']),
            boundary='exterior' if 'out' in o['sides'] else 'interior',
            opening_states=[0,50,100],opening_unit='percent',
            inferred=bool(o.get('guessed') or o.get('connection_evidence')),
            dimensions=dim))
        degree.update(s for s in o['sides'] if s != 'out')
    compartments = []
    for r in rooms:
        connected = bool(degree[r['id']])
        r['connectivity'] = 'connected' if connected else 'unresolved_isolated'
        compartments.append(dict(id=r['id'],area=r['area'],tags=r.get('tags',[]),
            connectivity=r['connectivity'],height_m=(defaults or {}).get('room_h'),
            included_in_solver=True))
    return dict(schema_version=2,opening_unit='percent',opening_states=[0,50,100],
        state_meaning='effective_open_area_fraction',compartments=compartments,
        connections=links,excluded_openings=excluded,
        isolated_rooms=[r['id'] for r in rooms if not degree[r['id']]],
        note='연결 미확정 공간도 유지. 개구부 미확인은 외기 연결로 바꾸지 않음. 높이 미지정 시 층 기본값 사용.')


def match_vertical_cores(cores):
    """One-to-one matches on adjacent named floors, with footprint overlap.

    Missing floors, weak alignment, or ambiguous matches remain unconfirmed.
    """
    from shapely.geometry import box
    import re
    normal=[]
    for c in cores:
        m=re.fullmatch(r'(B)?(\d+)F?',c['floor'])
        if m and not m[1]:normal.append(int(m[2])-1)
    def ordinal(name):
        if name in ('PH','옥탑'):return max(normal)+1 if normal else None
        m = re.fullmatch(r'(B)?(\d+)F?', name)
        return (-int(m[2]) if m[1] else int(m[2])-1) if m else None
    def adjacent(a,b):
        x,y=ordinal(a),ordinal(b)
        return x is not None and y is not None and y-x == 1
    def footprint(c):return box(c['x']-c['w']/2,c['y']-c['h']/2,c['x']+c['w']/2,c['y']+c['h']/2)
    groups=[]; unresolved=[]
    for c in sorted(cores,key=lambda c:c['z0']):
        candidates=[]
        for group in groups:
            prev=group[-1]
            if c['kind']!=prev['kind'] or not adjacent(prev['floor'],c['floor']): continue
            if abs(prev['z1']-c['z0'])>.5 or not (c.get('core_id') or c.get('room_id')) or not (prev.get('core_id') or prev.get('room_id')):continue
            if any(t in q.get('align','') for q in (c,prev) for t in ('xcorr','none','약함','unconfirmed')):continue
            a,b=footprint(prev),footprint(c)
            iou=a.intersection(b).area/max(a.union(b).area,1e-9)
            if iou>=.6:candidates.append((iou,group))
        candidates.sort(key=lambda t:t[0],reverse=True)
        if candidates and (len(candidates)==1 or candidates[0][0]-candidates[1][0]>.15):
            candidates[0][1].append(c)
        else:groups.append([c])
    shafts=[]
    for group in groups:
        if len(group)<2:
            unresolved.append(dict(floor=group[0]['floor'],kind=group[0]['kind'],room_id=group[0].get('room_id'),core_id=group[0].get('core_id'),reason='no_unambiguous_adjacent_floor_match'))
            continue
        c=group[0]
        shafts.append(dict(kind=c['kind'],x=c['x'],y=c['y'],w=c['w'],h=c['h'],
            z0=c['z0'],z1=group[-1]['z1'],floors=[g['floor'] for g in group],
            room_ids={g['floor']:g['room_id'] for g in group if g.get('room_id')},
            core_ids={g['floor']:g.get('core_id') for g in group},
            access_room_ids={g['floor']:g.get('access_room_ids',[]) for g in group},nodes=group,
            overlaps=[round(footprint(a).intersection(footprint(b)).area/max(footprint(a).union(footprint(b)).area,1e-9),4) for a,b in zip(group,group[1:])],
            evidence='adjacent_floor_envelope_overlap_and_room_id'))
    return shafts,unresolved
