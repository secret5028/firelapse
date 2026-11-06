"""Independent checks for CAD correction transactions; no AI-generated geometry."""
import math
from copy import deepcopy
from cad_connectivity_shared import geometry

def floor_checks(f):
    issues=[]
    def issue(ident,kind):issues.append(dict(id=ident,kind=kind))
    rooms=f.get('rooms',[]);ids=[r.get('id') for r in rooms]
    if len(ids)!=len(set(ids)):issue('FLOOR','duplicate_room_id')
    slab=geometry(f.get('slab',[]))
    if slab.is_empty or not slab.is_valid:issue('FLOOR','invalid_slab')
    if not isinstance(f.get('h'),(int,float)) or not math.isfinite(f['h']) or f['h']<=0:issue('FLOOR','invalid_height')
    for r in rooms:
        g=geometry(r.get('polys',[]))
        if g.is_empty or not g.is_valid or not math.isfinite(g.area) or g.area<=0:issue(r['id'],'invalid_room')
        elif not slab.is_empty and g.difference(slab.buffer(.05)).area>max(.01,g.area*.01):issue(r['id'],'room_outside_slab')
    opening_ids=[o.get('id') for o in f.get('openings',[])]
    if len(opening_ids)!=len(set(opening_ids)):issue('FLOOR','duplicate_opening_id')
    for o in f.get('openings',[]):
        sides=o.get('sides') or []
        if any(s is not None and s!='out' and s not in ids for s in sides):issue(o['id'],'dangling_opening')
    return issues

def checked_apply(f,c,mode,apply):
    """Commit one source-bound correction only if no new structural errors appear."""
    baseline={(x['id'],x['kind']) for x in floor_checks(f)}
    trial=deepcopy(f)
    change=apply(trial,c,mode)
    introduced=[x for x in floor_checks(trial) if (x['id'],x['kind']) not in baseline]
    if c.get('type')=='merge':
        # Union footprint must remain identical even for pre-existing overlaps.
        from shapely.ops import unary_union
        before=unary_union([geometry(r['polys']) for r in f['rooms']])
        after=unary_union([geometry(r['polys']) for r in trial['rooms']])
        if before.symmetric_difference(after).area>1e-6:introduced.append(dict(id=c['id'],kind='merge_changed_footprint'))
    if introduced:raise ValueError('correction_rejected:'+','.join(x['kind'] for x in introduced))
    f.clear();f.update(trial)
    change['validation']=dict(status='passed',new_geometry_errors=0)
    return change

def audit(building):
    rows=[]
    for f in building['floors']:
        graph=f.get('simulation_graph',{})
        rows.append(dict(floor=f['name'],rooms=len(f.get('rooms',[])),
            connections=len(graph.get('connections',[])),isolated_rooms=list(graph.get('isolated_rooms',[])),
            geometry_errors=floor_checks(f),
            unconfirmed_alignment='unconfirmed' in f.get('align','unconfirmed'),
            unresolved_openings=[o['id'] for o in f.get('openings',[]) if len(o.get('sides') or [])!=2 or None in (o.get('sides') or [])],
            inferred_openings=[o['id'] for o in f.get('openings',[]) if o.get('connection_confidence')=='inferred']))
    errors=sum(len(x['geometry_errors']) for x in rows)
    isolated=sum(len(x['isolated_rooms']) for x in rows)
    missing_vertical=len(rows)>1 and not building.get('vertical_connections')
    return dict(status='geometry_failed' if errors else 'needs_review' if missing_vertical or isolated or any(x['unresolved_openings'] or x['unconfirmed_alignment'] or x['inferred_openings'] for x in rows) or building.get('unconfirmed_vertical_cores') else 'checked',
        floors=rows,geometry_error_count=errors,isolated_room_count=isolated,
        vertical_connections=len(building.get('vertical_connections',[])),
        missing_vertical_connections=missing_vertical,
        unconfirmed_vertical_cores=len(building.get('unconfirmed_vertical_cores',[])))
