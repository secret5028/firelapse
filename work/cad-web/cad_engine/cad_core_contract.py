"""Stage-1 core/ramp evidence. Coordinates are metres in the source frame.

Alignment anchors describe the CAD stair symbol, not the containing room.
A core contained by a large room is an access relationship, not a claim that
the whole room is a vertical shaft. No new separating wall is invented here.
"""
import math
from collections import defaultdict
import numpy as np
from shapely.geometry import Point, Polygon, LineString, box
from shapely.ops import unary_union
from cad_evidence import geometry, polygon_parts


def envelope(c):
    return box(c['cx']-c['w']/2,c['cy']-c['h']/2,c['cx']+c['w']/2,c['cy']+c['h']/2)


def find_ramps(plan):
    # Curved road band: concentric large arcs, a vehicle-width separation,
    # structural/stair layer evidence and explicit parking context together.
    if not plan.get('use_hint',{}).get('parking'): return []
    groups=defaultdict(list)
    for v in plan.get('source_vectors',[]):
        a=v.get('arc')
        if a and a[2]>=3 and v['category'] in ('stair','wall'):
            groups[(round(a[0],1),round(a[1],1))].append(v)
    ramps=[]
    for vs in groups.values():
        stairs=[v for v in vs if v['category']=='stair']
        if len(stairs)<2:continue
        lo=min(stairs,key=lambda v:v['arc'][2]);hi=max(stairs,key=lambda v:v['arc'][2])
        if hi['arc'][2]-lo['arc'][2]<2.5:continue
        # Use the actual overlapping angular range, including wrapped arcs.
        def angles(a):
            start=a[3];end=start+(a[4]-start)%360
            return start,end
        a0,a1=angles(lo['arc']);b0,b1=angles(hi['arc'])
        start,end=max(a0,b0),min(a1,b1)
        if end-start<30:continue
        cx,cy=lo['arc'][:2]
        def arc(r,ts):return [[cx+r*math.cos(math.radians(t)),cy+r*math.sin(math.radians(t))] for t in ts]
        pts=arc(hi['arc'][2],np.linspace(start,end,60))+arc(lo['arc'][2],np.linspace(end,start,60))
        g=Polygon(pts)
        ramps.append(dict(id=f'RAMP{len(ramps)}',kind='vehicle_ramp',polys=[dict(o=pts,h=[])],
            width_m=round(hi['arc'][2]-lo['arc'][2],3),source_vector_ids=[v['id'] for v in vs],
            evidence='parking_text_and_concentric_road_band',connection_status='endpoints_not_extracted',
            note='차량 램프 평면 형상. 상하단 표고와 외기 연결은 원본 근거 확인 전 미확정.'))
    return ramps


def stair_symbols(plan, ramps):
    from cad_plan import cluster_boxes
    ramp_geoms=[geometry(r['polys']).buffer(.4) for r in ramps]
    foot=geometry(plan.get('footprint',[])).buffer(.5)
    items=[]
    for v in plan.get('source_vectors',[]):
        if v['category']!='stair' or len(v['points'])<2:continue
        line=LineString(v['points'])
        if line.is_empty or not foot.intersects(line):continue
        if any(g.intersection(line).length>line.length*.5 for g in ramp_geoms):continue
        # Degenerate line rectangles are not valid polygons in Shapely.
        items.append((line.envelope.buffer(.002),v))
    result=[]
    for group in cluster_boxes(items,.3):
        vs=[items[i][1] for i in group]
        bounds=unary_union([items[i][0] for i in group]).bounds
        if len(bounds)!=4:continue
        x0,y0,x1,y1=bounds;w,h=x1-x0,y1-y0
        if min(w,h)<.8 or max(w,h)>20 or len(vs)<10:continue
        # A stairs layer alone is insufficient: require repeated tread lines.
        bins=defaultdict(list)
        for v in vs:
            if v.get('arc') or len(v['points'])!=2:continue
            a,b=np.array(v['points']);d=b-a;length=np.linalg.norm(d)
            if length<.4:continue
            angle=round(math.degrees(math.atan2(d[1],d[0]))%180/5)*5
            bins[angle].append((a+b)/2)
        repeated=max((len(q) for q in bins.values()),default=0)
        if repeated<6:continue
        result.append(dict(kind='stair',cx=(x0+x1)/2,cy=(y0+y1)/2,w=w,h=h,
            n=len(vs),src='repeated_tread_vectors',source_vector_ids=[v['id'] for v in vs]))
    return result


def normalize_cores(plan):
    if plan.get('core_contract_version')==1:return plan
    ramps=find_ramps(plan);plan['ramps']=ramps
    original=plan.get('cores',[])
    # Use the same tread-vector anchor on every floor, even when a complete
    # stair room has also been extracted. Retain symbol/room evidence separately.
    stairs=stair_symbols(plan,ramps)
    # Existing room-based evidence remains valid when another CAD convention
    # provides no extractable tread-line anchor. Do not erase legacy cores.
    if not stairs and not ramps:
        stairs=[dict(c,anchor_evidence='existing_extraction') for c in original if c['kind']=='stair']
    else:
        for c in original:
            if c['kind']!='stair' or c.get('src')!='room':continue
            g=envelope(c)
            if not any(g.intersection(envelope(s)).area/min(g.area,envelope(s).area)>.5 for s in stairs):
                stairs.append(dict(c,anchor_evidence='existing_stair_room'))
    cores=[dict(c) for c in original if c['kind']=='elev']+stairs
    if not plan.get('source_vectors'):
        cores=[dict(c) for c in original]  # Legacy callers without raw CAD.
    rooms=[(r,geometry(polygon_parts(r))) for r in plan['rooms']]
    for i,c in enumerate(cores):
        c['core_id']=f'C{i}';g=envelope(c);point=Point(c['cx'],c['cy'])
        hits=[(r,p) for r,p in rooms if p.covers(point)]
        c['access_room_ids']=[r['id'] for r,p in hits]
        c.pop('room_id',None)
        if len(hits)==1:
            r,p=hits[0]
            tags=r.get('tags',[])
            if (c['kind'] in tags or c['kind']+'_inside' in tags) and p.area<=3*g.area:
                c['room_id']=r['id'];c['room_bounds']=list(p.bounds)
        c['association']='dedicated_room' if c.get('room_id') else 'contained_core_in_room' if hits else 'unresolved_access'
    plan['cores']=cores;plan['core_contract_version']=1
    plan['core_review']=[dict(id=c['core_id'],reason='access_room_missing') for c in cores if not c['access_room_ids']]
    # An unhosted arc on a ramp is not a door; retain rejection evidence.
    keep=[]
    ramp_vectors={v['id']:LineString(v['points']) for v in plan.get('source_vectors',[]) if len(v['points'])>=2 and any(v['id'] in r['source_vector_ids'] for r in ramps)}
    for o in plan['openings']:
        g=geometry(o.get('geometry_polys') or [dict(o=p,h=[]) for p in o.get('polys',[])])
        on_ramp=any(g.distance(geometry(r['polys']))<.5 for r in ramps) or any(g.distance(v)<.1 for v in ramp_vectors.values())
        if on_ramp and o.get('host_evidence',{}).get('status')=='unsupported' and not any(l.get('leaf_line') for l in o.get('leaves',[])):
            plan.setdefault('rejected_openings',[]).append(dict(o,rejection_reason='unhosted_arc_on_vehicle_ramp'))
        else:keep.append(o)
    plan['openings']=keep
    if 'stats' in plan:
        plan['stats'].update(doors_open=sum(o['kind']=='door' for o in keep),ramps=len(ramps),cores=len(cores))
    return plan
