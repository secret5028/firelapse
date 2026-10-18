"""Stage 2: render geometry from stage-1 source coordinates, without moving cores."""
import math,copy,json
from pathlib import Path
from collections import Counter
import numpy as np
from shapely.geometry import Polygon,box,Point,LineString
from shapely.ops import unary_union
from shapely import affinity
from cad_evidence import geometry,polygon_parts

def parts(g):
    return [dict(o=[list(q) for q in p.exterior.coords[:-1]],h=[[list(q) for q in h.coords[:-1]] for h in p.interiors]) for p in ([g] if g.geom_type=='Polygon' else getattr(g,'geoms',[])) if p.geom_type=='Polygon' and p.area>.0001]

def road_faces(plan,ramp):
    vs=[v for v in plan['source_vectors'] if v['id'] in ramp['source_vector_ids']]
    stairs=sorted([v for v in vs if v['category']=='stair'],key=lambda v:v['arc'][2])
    walls=[v for v in vs if v['category']=='wall']
    low,high=stairs[0]['arc'][2],stairs[-1]['arc'][2]
    inners=[v for v in walls if v['arc'][2]<=low];outers=[v for v in walls if v['arc'][2]>=high]
    if not inners or not outers:return None
    inner=max(inners,key=lambda v:v['arc'][2]);outer=min(outers,key=lambda v:v['arc'][2])
    def interval(v):a=v['arc'];return a[3],a[3]+(a[4]-a[3])%360
    start=max(interval(inner)[0],interval(outer)[0]);end=min(interval(inner)[1],interval(outer)[1])
    if end<=start:return None
    cx,cy=inner['arc'][:2];ri,ro=inner['arc'][2],outer['arc'][2]
    ts=np.linspace(start,end,81)
    outerpoints=[[cx+ro*math.cos(math.radians(t)),cy+ro*math.sin(math.radians(t))] for t in ts]
    innerpoints=[[cx+ri*math.cos(math.radians(t)),cy+ri*math.sin(math.radians(t))] for t in ts]
    return dict(inner=innerpoints,outer=outerpoints,width_m=ro-ri,length_m=math.radians(end-start)*(ri+ro)/2,
        inner_boundary_shift_m=low-ri,outer_boundary_shift_m=ro-high,
        source_vector_ids=[inner['id'],outer['id']],source='CAD_wall_road_faces',
        polys=[dict(o=outerpoints+innerpoints[::-1],h=[])])

def apply_outdoor_semantics(f, plan, building):
    """Classify exposed floor projections using aligned adjacent floor slabs.

    Ground/basement and a main roof beneath a penthouse are separate cases.
    A small alignment tolerance must not turn facade slivers into terraces.
    """
    if 'outdoor_source_model' in f:
        for key,value in f['outdoor_source_model'].items():f[key]=copy.deepcopy(value)
    f['outdoor_spaces']=[]
    upper=next((q for q in building['floors'] if abs(q['z']-f['z']-f['h'])<.02),None)
    if not upper or upper['name'].upper() in ('PH','RF','ROOF') or f['name'].upper().startswith('B'):return
    upper_slab=geometry(upper['slab'])
    exposed=geometry(f['slab']).difference(upper_slab.buffer(.25))
    candidates=[r for r in f['rooms'] if geometry(r['polys']).area>10
        and geometry(r['polys']).intersection(exposed).area/geometry(r['polys']).area>.8
        and not any(t in ('stair','elev') for t in r.get('tags',[]))]
    if not candidates:return
    f.setdefault('outdoor_source_model',{k:copy.deepcopy(f[k]) for k in ('bands','glass','openings','rooms','ceiling')})
    for room in candidates:
        _model_terrace(f, room, upper, upper_slab)


def _model_terrace(f, room, upper, upper_slab):
    terrace=geometry(room['polys'])
    indoor=unary_union([geometry(r['polys']) for r in f['rooms'] if r['id']!=room['id']])
    # Preserve the shared facade, lift enclosure and their openings. Only the
    # exposed perimeter is lowered; this is not a blanket room-boundary edit.
    edge=terrace.simplify(.035,preserve_topology=True).boundary.difference(indoor.buffer(.55))
    mask=edge.buffer(1.5).difference(indoor.buffer(.18))
    for band in f['bands']:band['polys']=parts(geometry(band['polys']).difference(mask))
    f['glass']['polys']=parts(geometry(f['glass']['polys']).difference(mask))
    changed=[]
    for opening in f['openings']:
        original=geometry(opening.get('geometry_polys') or [dict(o=p,h=[]) for p in opening['polys']])
        remaining=original.difference(mask)
        if original.area-remaining.area<.00001:continue
        opening['geometry_polys']=parts(remaining)
        opening['polys']=[p['o'] for p in parts(remaining)]
        opening['model_note']='테라스 외곽 오인 부분 제외; 실내 접합부는 보존'
        changed.append(opening['id'])
    f['openings']=[o for o in f['openings'] if o['polys']]
    railing=parts(edge.buffer(.1,cap_style=2,join_style=2))
    f['bands'].append(dict(kind='wall',structural_role='terrace_parapet',polys=railing,z0=0,z1=1.1,
        height_source='display_default_not_measured',room_id=room['id']))
    room['names']=['테라스'];room['tags']=list(dict.fromkeys(room.get('tags',[])+['terrace','outdoor']))
    room['environment']='outdoor';room['enclosed']=False
    # Include the outer band so no floating ceiling strip survives over it.
    open_sky=terrace.union(mask.intersection(geometry(f['slab'])))
    f['ceiling']=parts(geometry(f['ceiling']).difference(open_sky))
    f['outdoor_spaces'].append(dict(id=room['id'],kind='terrace',polys=room['polys'],open_sky_polys=parts(open_sky),
        boundary_mask=parts(mask),parapet_height_m=1.1,height_source='표시용 기본값; 도면 높이 미확인',
        evidence='계단·승강기로 정렬된 해당 층과 직상층 바닥 비교',changed_openings=changed,
        compared_floor=upper['name'],upper_slab_overlap_m2=terrace.intersection(upper_slab).area,
        classification_status='aligned_floor_projection_rule'))

def prepare_model(building,plans):
    b=copy.deepcopy(building);audit=[]
    for fi,f in enumerate(b['floors']):
        plan=plans[f['name']];sc=f['scale'];tx,ty=f['shift'];ox,oy=b['origin']
        apply_outdoor_semantics(f,plan,b)
        def transform(g):return affinity.translate(affinity.scale(g,sc,sc,origin=(0,0)),tx-ox,ty-oy)
        def xy(q):return [q[0]*sc+tx-ox,q[1]*sc+ty-oy]
        f['transport']=[];holes=[];ceiling_holes=[]
        for core in [c for c in b['core_nodes'] if c['floor']==f['name']]:
            c=next(c for c in plan['cores'] if c['core_id']==core['core_id'])
            anchor=box(core['x']-core['w']/2,core['y']-core['h']/2,core['x']+core['w']/2,core['y']+core['h']/2)
            dedicated=next((r for r in f['rooms'] if r['id']==core.get('room_id')),None)
            region=anchor
            if dedicated:region=region.intersection(geometry(dedicated['polys']))
            link=next((l for l in b['vertical_connections'] if l['from_floor']==f['name'] and l['from_core']==core['core_id']),None)
            incoming=any(l['to_floor']==f['name'] and l['to_core']==core['core_id'] for l in b['vertical_connections'])
            target=next((x for x in b['floors'] if link and x['name']==link['to_floor']),None)
            # Explicit source/reference round-trip audit; no hand positioning.
            error=math.hypot(xy([c['cx'],c['cy']])[0]-core['x'],xy([c['cx'],c['cy']])[1]-core['y'])
            assert error<.001
            item=dict(id=core['core_id'],kind=core['kind'],anchor=parts(anchor),region=parts(region),
                room_region=dedicated['polys'] if dedicated else None,source_vector_ids=c.get('source_vector_ids',[]),
                connected=bool(link or incoming),to_floor=target['name'] if target else None,
                rise_m=target['z']-f['z'] if target else 0,assumption='simplified_steps_and_landings_from_existing_webapp',meshes=[])
            if incoming:holes.append(region)
            if link:ceiling_holes.append(region)
            if c['kind']=='stair' and link:
                # Repeated tread direction identifies stair width axis. Shape
                # is a simplified return stair; each step clips to source area.
                ids=set(c.get('source_vector_ids',[]));angles=[]
                for v in plan['source_vectors']:
                    if v['id'] not in ids or v.get('arc') or len(v['points'])!=2:continue
                    a,d=np.array(v['points']);vec=d-a
                    if np.linalg.norm(vec)>.4:angles.append(round(math.degrees(math.atan2(vec[1],vec[0]))%180/5)*5)
                angle=Counter(angles).most_common(1)[0][0] if angles else (0 if core['w']<core['h'] else 90)
                local=affinity.rotate(region,-angle,origin=(core['x'],core['y']))
                x0,y0,x1,y1=local.bounds;w,h=x1-x0,y1-y0
                landing=min(w*.5,h*.2,1.3);run=h-2*landing;rise=item['rise_m'];n=max(4,math.ceil(rise/.36))
                def slab(xa,ya,xb,yb,z,th=.1):
                    p=affinity.rotate(box(xa,ya,xb,yb),angle,origin=(core['x'],core['y'])).intersection(region)
                    if not p.is_empty:item['meshes'].append(dict(polys=parts(p),z0=z-th,z1=z))
                for i in range(n):
                    slab(x0,y1-landing-(i+1)*run/n,x0+w*.46,y1-landing-i*run/n,(i+1)*rise/(2*n))
                    slab(x0+w*.54,y0+landing+i*run/n,x1,y0+landing+(i+1)*run/n,rise/2+(i+1)*rise/(2*n))
                slab(x0,y0,x1,y0+landing,rise/2,.14)
                slab(x0+w*.54,y1-landing,x1,y1,rise,.14)
                item['direction_source']='dominant_CAD_treads' if angles else 'short_axis_default'
            if c['kind']=='elev':
                candidates=[]
                for o in f['openings']:
                    if o['kind']!='door_elev':continue
                    g=geometry(o.get('geometry_polys') or [dict(o=p,h=[]) for p in o['polys']])
                    if g.distance(anchor)<.35:candidates.append(o['id'])
                item['door_ids']=candidates
            f['transport'].append(item)
            audit.append(dict(floor=f['name'],id=c['core_id'],coordinate_error_m=error,
                anchor_outside_room_m2=anchor.difference(geometry(dedicated['polys'])).area if dedicated else None))
        f['model_ramps']=[]
        for ramp in plan.get('ramps',[]):
            road=road_faces(plan,ramp)
            if not road:continue
            # User-reviewed B1 ramp: complete half-turn linking B1 and 1F.
            # Only this exact reviewed source uses the simplified 180-degree span.
            reviewed=plan.get('provenance',{}).get('source_sha256')=='8c388560bc23f92ad9fb03ed2b50c3f09dd2b7d3fb1cef31441e52a2d122a67d'
            upper=next((q for q in b['floors'] if q['name']=='1F'),None) if reviewed else None
            if upper:
                v=next(v for v in plan['source_vectors'] if v['id']=='V976');cx,cy,ri=v['arc'][:3]
                ro=next(v for v in plan['source_vectors'] if v['id']=='V14')['arc'][2]
                ts=np.linspace(270,450,121)
                road['inner']=[[cx+ri*math.cos(math.radians(t)),cy+ri*math.sin(math.radians(t))] for t in ts]
                road['outer']=[[cx+ro*math.cos(math.radians(t)),cy+ro*math.sin(math.radians(t))] for t in ts]
                road['polys']=[dict(o=road['outer']+road['inner'][::-1],h=[])]
                road['length_m']=math.pi*(ri+ro)/2
            model=dict(road,id=ramp['id'],inner=[xy(q) for q in road['inner']],outer=[xy(q) for q in road['outer']],polys=parts(transform(geometry(road['polys']))),
                slope_percent=10,height_assumption='표시용 경사 10%. 곡선 구간만 모델링하며 상단 연결층·표고는 미확정.',direction_assumption='CAD 경계 점 순서에 따른 임시 상승 방향; 화면에서 반전 가능')
            f['model_ramps'].append(model)
            if upper:
                rise=upper['z']-f['z']
                model.update(from_floor=f['name'],to_floor=upper['name'],rise_m=rise,span_degrees=180,
                    slope_percent=100*rise/model['length_m'],connection_status='user_reviewed_floor_connection',
                    height_assumption='B1↔1F 바닥 높이차 적용. 반원 180도는 사용자 해석에 따른 단순화 모델.',
                    direction_assumption='북측을 1F 접속측으로 표시; 기존 층 좌표 유지',
                    modeling_evidence='2026-10-14 user reviewed B1–1F half-turn; CAD wall radii retained')
                ceiling_holes.append(geometry(model['polys']))
            holes.append(geometry(model['polys']))
            audit.append(dict(floor=f['name'],id=ramp['id'],inner_boundary_shift_m=road['inner_boundary_shift_m'],outer_boundary_shift_m=road['outer_boundary_shift_m'],width_m=road['width_m']))
        cut=unary_union(holes)
        f['render_slab']=parts(geometry(f['slab']).difference(cut))
        for room in f['rooms']:room['render_polys']=parts(geometry(room['polys']).difference(cut))
        f['render_ceiling']=parts(geometry(f['ceiling']).difference(unary_union(ceiling_holes)))
    b['structural_tops']=[]
    for i,f in enumerate(b['floors']):
        z=f['z']+f['h'];upper=next((q for q in b['floors'] if abs(q['z']-z)<.02),None)
        sky=unary_union([geometry(t['open_sky_polys']) for t in f.get('outdoor_spaces',[])])
        covered=geometry(f['slab']).difference(sky)
        exposed=covered
        ramp_holes=unary_union([geometry(r['polys']) for r in f['model_ramps'] if r.get('to_floor')])
        exposed=exposed.difference(ramp_holes)
        if upper:exposed=exposed.difference(geometry(upper['slab']))
        b['structural_tops'].append(dict(from_floor=f['name'],to_floor=upper['name'] if upper else None,z=z,
            roof_polys=parts(exposed),ceiling_polys=parts(covered.difference(unary_union([geometry(c['region']) for c in f['transport'] if c.get('to_floor')])).difference(ramp_holes)),shared_slab_floor=upper['name'] if upper else None,thickness_m=.2,
            note='구조 슬래브: 아래층 천장/위층 바닥 공용. 반자와 별개. 두께 0.2m 표시 기본값.'))
    b['ramp_connections']=[dict(kind='vehicle_ramp',from_floor=f['name'],to_floor=r['to_floor'],ramp_id=r['id'],rise_m=r['rise_m'],evidence=r['connection_status']) for f in b['floors'] for r in f['model_ramps'] if r.get('to_floor')]
    b['movement_connections']=copy.deepcopy(b['vertical_connections'])+b['ramp_connections']
    b['model_scope']='stage_2_visualization; source stage-1 geometry retained'
    return b,audit
