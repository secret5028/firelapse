"""Existing CAD graph functions, extracted unchanged except configurable thresholds.
Provenance: reviews/D3-20261103/cad-source.json. No simulation integration.
"""
import math
from collections import Counter
import numpy as np
from shapely import make_valid
from shapely.geometry import Point, LineString, Polygon, GeometryCollection
from shapely.ops import unary_union
from building_rules import load_rules
OUTSIDE = load_rules()['openings']['outside_id']

def polygon_parts(item):
    return item.get('polys') or [dict(o=item.get('poly', []), h=item.get('holes', []))]


def opening_parts(item):
    return item.get('geometry_polys') or [dict(o=p,h=[]) for p in item.get('polys',[])]


def geometry(parts):
    ps = []
    for p in parts:
        outer, holes = (p.get('o', []), p.get('h', [])) if isinstance(p, dict) else (p, [])
        if len(outer) >= 3:
            g = Polygon(outer, holes)
            ps.append(g if g.is_valid else make_valid(g))
    return unary_union(ps) if ps else GeometryCollection()


def connection_status(opening, room_ids):
    sides = opening.get('sides') or []
    if len(sides) != 2 or any(s is None or (s != OUTSIDE and s not in room_ids) for s in sides):
        return 'unresolved'
    if sides[0] == sides[1]:
        return 'internal_leaf' if opening['kind'] == 'door_internal' and sides[0] != OUTSIDE else 'same_space'
    return 'exterior' if OUTSIDE in sides else 'interior'


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


def opening_dimensions(o, defaults=None):
    defaults = defaults or {}
    width = o.get('span')
    source = 'CAD_span'
    if not width:
        width = sum(l.get('r_std') or l.get('r') or 0 for l in o.get('leaves', []))
        source = 'CAD_leaf'
    if not width:
        frame = aperture_frame(o)
        width = frame[4]*2 if frame else None
        source = 'CAD_aperture_envelope'
    if not width or not math.isfinite(width) or width <= 0:
        raise ValueError(f"Opening {o['id']} has no valid width")
    window = o['kind'] in load_rules()['openings']['window_kinds']
    bottom = float(o.get('sill') if o.get('sill') is not None else defaults.get('sill', load_rules()['openings']['sill_m'])) if window else 0.
    top = float(o.get('head') if o.get('head') is not None else defaults.get('head', load_rules()['openings']['head_m'])) if window else float(o.get('door_h') or defaults.get('door_h', load_rules()['openings']['door_height_m']))
    if top <= bottom: raise ValueError(f"Invalid height for {o['id']}")
    return dict(width_m=round(float(width), 4), bottom_m=bottom, top_m=top,
                height_m=top-bottom, area_m2=float(width)*(top-bottom),
                width_source=source, height_source='CAD_override_or_floor_default')


def build_graph(rooms, openings, defaults=None):
    ids = {r['id'] for r in rooms}; links = []; excluded = []; degree = Counter()
    if len(ids) != len(rooms): raise ValueError('Duplicate room IDs')
    if len({o['id'] for o in openings}) != len(openings): raise ValueError('Duplicate opening IDs')
    for o in openings:
        if o.get('superseded_by'):
            o['connection_status']='superseded_arc_bundle'
            excluded.append(dict(id=o['id'],reason='superseded_arc_bundle'))
            continue
        status = connection_status(o, ids)
        o['connection_status'] = status
        if status not in ('interior', 'exterior') or o['kind'] == 'vent':
            excluded.append(dict(id=o['id'],reason='non_flow_symbol' if o['kind']=='vent' else status))
            continue
        dim = opening_dimensions(o, defaults)
        links.append(dict(id=o['id'],kind=o['kind'],sides=list(o['sides']),
            boundary='exterior' if OUTSIDE in o['sides'] else 'interior',
            opening_states=[0,50,100],opening_unit='percent',
            inferred=bool(o.get('guessed') or o.get('connection_evidence')),
            dimensions=dim))
        degree.update(s for s in o['sides'] if s != OUTSIDE)
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


def match_vertical_cores(cores, floor_names=None):
    """One-to-one matches on adjacent named floors, with footprint overlap.

    Missing floors, weak alignment, or ambiguous matches remain unconfirmed.
    """
    from shapely.geometry import box
    import re
    unsupported=[dict(floor=c['floor'],kind=c['kind'],room_id=c.get('room_id'),core_id=c.get('core_id'),reason='vertical_kind_excluded_by_model_axiom') for c in cores if c.get('kind') not in ('stair','elev')]
    cores=[c for c in cores if c.get('kind') in ('stair','elev')]
    normal=[]
    for name in (floor_names if floor_names is not None else [c['floor'] for c in cores]):
        m=re.fullmatch(r'(B)?(\d+)F?',name)
        if m and not m[1]:normal.append(int(m[2])-1)
    def ordinal(name):
        if name in ('PH','옥탑'):return max(normal)+1 if normal else None
        m = re.fullmatch(r'(B)?(\d+)F?', name)
        return (-int(m[2]) if m[1] else int(m[2])-1) if m else None
    def adjacent(a,b):
        x,y=ordinal(a),ordinal(b)
        return x is not None and y is not None and y-x == 1
    def footprint(c):return box(c['x']-c['w']/2,c['y']-c['h']/2,c['x']+c['w']/2,c['y']+c['h']/2)
    groups=[]; unresolved=unsupported
    for c in sorted(cores,key=lambda c:c['z0']):
        candidates=[]
        for group in groups:
            prev=group[-1]
            if c['kind']!=prev['kind'] or not adjacent(prev['floor'],c['floor']): continue
            if abs(prev['z1']-c['z0'])>load_rules()['vertical']['max_z_gap_m'] or not (c.get('core_id') or c.get('room_id')) or not (prev.get('core_id') or prev.get('room_id')):continue
            if any(t in q.get('align','') for q in (c,prev) for t in load_rules()['vertical']['weak_alignment_tokens']):continue
            a,b=footprint(prev),footprint(c)
            iou=a.intersection(b).area/max(a.union(b).area,1e-9)
            if iou>=load_rules()['vertical']['minimum_iou']:candidates.append((iou,group))
        candidates.sort(key=lambda t:t[0],reverse=True)
        if candidates and (len(candidates)==1 or candidates[0][0]-candidates[1][0]>load_rules()['vertical']['ambiguity_margin']):
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
