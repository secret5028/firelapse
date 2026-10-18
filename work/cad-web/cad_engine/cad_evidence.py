"""Shared polygon and fire-evidence logic. Coordinates are source metres.

Fire symbols are supplementary evidence, never a source of invented walls.
Distance thresholds are configurable matching tolerances, not fire regulations.
"""
import copy
import math
from collections import Counter
from shapely import make_valid
from shapely.geometry import Polygon, Point, LineString, GeometryCollection
from shapely.ops import unary_union, nearest_points
from shapely.strtree import STRtree
from cad_topology import connection_status


def polygon_parts(item):
    return item.get('polys') or [dict(o=item.get('poly', []), h=item.get('holes', []))]


def opening_parts(item):
    return item.get('geometry_polys') or [dict(o=p,h=[]) for p in item.get('polys',[])]


def normalize_plan(plan):
    """Resolve raster contour self-touches without discarding polygon interiors.

    Store a repair record and preserve source_vectors for inspecting every repair.
    Collapsed non-area pieces are recorded, not presented as usable geometry.
    """
    def polygon_components(g):
        if g.geom_type=='Polygon': return [g] if g.area>0 else []
        return [p for child in getattr(g,'geoms',[]) for p in polygon_components(child)]
    def normalize(parts,family,oid):
        output=[]
        for part in parts:
            g=Polygon(part['o'],part.get('h',[]))
            fixed=g if g.is_valid else make_valid(g)
            pieces=polygon_components(fixed)
            if not g.is_valid or not pieces:
                plan['checks'].append(dict(rule='Q형상정리',id=oid,family=family,
                    area_before=round(g.area,6),area_after=round(sum(p.area for p in pieces),6),
                    note='래스터 윤곽의 자기 접촉·교차를 유효 면으로 분리. 원본 벡터와 보정 전 결과로 확인 가능'))
            for p in pieces:
                output.append(dict(o=[list(x) for x in p.exterior.coords[:-1]],
                    h=[[list(x) for x in ring.coords[:-1]] for ring in p.interiors]))
        return output
    for field in ('walls','footprint'):
        plan[field]=normalize(plan.get(field,[]),field,field)
    for r in plan['rooms']:
        r['polys']=normalize(polygon_parts(r),'room',r['id'])
        if r['polys']:
            largest=max(r['polys'],key=lambda p:Polygon(p['o'],p['h']).area)
            r['poly']=largest['o']; r['holes']=largest['h']
            r['area']=round(geometry(r['polys']).area,4)
    # Contour make_valid can turn a self-touching interior into an extra solid
    # polygon. The original raster partitions rooms and walls disjointly; keep
    # that invariant after vector repair as well, including newly closed rooms.
    room_union=unary_union([geometry(polygon_parts(r)) for r in plan['rooms']])
    wall_shape=geometry(plan.get('walls',[]));overlap=wall_shape.intersection(room_union).area
    if overlap>1e-8:
        fixed=wall_shape.difference(room_union)
        plan['walls']=[dict(o=[list(x) for x in p.exterior.coords[:-1]],h=[[list(x) for x in ring.coords[:-1]] for ring in p.interiors]) for p in polygon_components(fixed)]
        plan['checks'].append(dict(rule='Q벽실분리',id='walls',overlap_removed_m2=round(overlap,6),note='윤곽 보정 중 채워진 실내 면을 벽에서 제거하여 실·벽 비중첩 유지'))
    for o in plan['openings']:
        parts=normalize(opening_parts(o),'opening',o['id'])
        o['geometry_polys']=parts
        o['polys']=[p['o'] for p in parts]  # compatibility; consumers use geometry_polys for interiors
    return plan


def geometry(parts):
    ps = []
    for p in parts:
        outer, holes = (p.get('o', []), p.get('h', [])) if isinstance(p, dict) else (p, [])
        if len(outer) >= 3:
            g = Polygon(outer, holes)
            ps.append(g if g.is_valid else make_valid(g))
    return unary_union(ps) if ps else GeometryCollection()


def analyze_fire(plan, symbols, *, alignment_verified=False, max_distance=1.5, ambiguity_margin=.25):
    rooms = [(r, geometry(polygon_parts(r))) for r in plan['rooms']]
    openings = [(o, geometry(opening_parts(o))) for o in plan['openings']]
    openings = [(o,g) for o,g in openings if not g.is_empty]
    walls = geometry(plan.get('walls', []))
    footprint = geometry(plan.get('footprint', []))
    result = dict(rooms={r['id']:dict(detectors=0,exit_signs=0,corridor_lights=0) for r,g in rooms},
                  openings={},symbols=[],dropped=[],covered=[],checks=[],
                  alignment_verified=alignment_verified,
                  matching_tolerances_m=dict(max_distance=max_distance,ambiguity_margin=ambiguity_margin))
    seen = set()
    room_ids = set(result['rooms'])
    for index, incoming in enumerate(symbols):
        s = {k:copy.deepcopy(v) for k,v in incoming.items() if k not in ('room','opening','role','match','candidates','evidence_id')}
        s['evidence_id'] = f'F{index}'
        if s.get('kind') not in ('detector','exit_sign','corridor_light','hydrant'):
            result['dropped'].append(dict(s,reason='unsupported_symbol')); continue
        try:
            xy = (float(s['x']),float(s['y']))
            if not all(math.isfinite(v) for v in xy): raise ValueError('nonfinite')
        except (KeyError,TypeError,ValueError):
            result['dropped'].append(dict(s,reason='invalid_coordinate')); continue
        key = (s['kind'],round(xy[0],3),round(xy[1],3))
        if key in seen:
            result['dropped'].append(dict(s,reason='duplicate')); continue
        seen.add(key)
        point = Point(xy)
        if not footprint.is_empty and not footprint.buffer(1).covers(point):
            result['dropped'].append(dict(s,reason='outside_plan')); continue
        inrooms = [r['id'] for r,g in rooms if g.covers(point)]
        s['room'] = inrooms[0] if len(inrooms)==1 else None
        s['room_candidates'] = inrooms
        stat = dict(detector='detectors',exit_sign='exit_signs',corridor_light='corridor_lights').get(s['kind'])
        if s['room'] and stat: result['rooms'][s['room']][stat] += 1
        if s['kind']=='detector' and not s['room']:
            result['checks'].append(dict(rule='F감지기-실미확인',id=s['evidence_id'],at=list(xy),
                note='감지기 위치의 실 소속을 확정할 수 없음 — 누락 경계·제외 영역·정렬 확인'))
        if s['kind']=='exit_sign':
            candidates=[]
            for o,g in openings:
                d = point.distance(g)
                if d>max_distance: continue
                target = nearest_points(point,g)[1]
                path = LineString([point,target])
                # Allow the symbol on a wall face and the destination opening,
                # but reject an intervening wall outside these small end zones.
                middle = path.difference(point.buffer(.15).union(g.buffer(.15))) if d>1e-9 else GeometryCollection()
                obstruction = 0 if middle.is_empty else middle.intersection(walls).length
                sides=o.get('sides') or []
                reason = 'room_mismatch' if s['room'] and s['room'] not in sides else None
                if obstruction > max(.02,2*plan.get('res_m',.02)): reason='wall_between'
                candidates.append(dict(id=o['id'],distance=round(d,4),blocked=reason))
            viable=sorted([c for c in candidates if not c['blocked']],key=lambda c:c['distance'])
            s['candidates']=sorted(candidates,key=lambda c:c['distance'])
            match = viable[0] if viable else None
            ambiguous = len(viable)>1 and viable[1]['distance']-viable[0]['distance']<ambiguity_margin
            s['opening']=None
            if match and not ambiguous and s['room']:
                s['opening']=match['id']; s['match']='supported' if alignment_verified else 'alignment_unverified'
                o=next(o for o,g in openings if o['id']==match['id'])
                rec=result['openings'].setdefault(o['id'],dict(kind_in=o['kind'],kind_out=o['kind'],exit_signs=0,evidence=[]))
                rec['exit_signs']+=1; rec['evidence'].append(s['evidence_id'])
                status=connection_status(o,room_ids)
                if o['kind'] in ('window','window_inner'):
                    rec['candidate_kind']='door'
                    if alignment_verified and status in ('interior','exterior'):
                        rec.update(kind_out='door',decision='fire_supported',operation='unknown')
                        result['checks'].append(dict(rule='F유도등→문',id=o['id'],note='정렬·실 소속·고유 개구부·벽 차폐 검사 통과. 문으로 보정; 여닫이 방식은 미확정'))
                    else:
                        rec['decision']='review'
            elif ambiguous:
                s['match']='ambiguous'
                result['checks'].append(dict(rule='F유도등-개구부경합',id=s['evidence_id'],at=list(xy),note='가까운 개구부가 여러 개여서 문 판정 보류'))
            else:
                s['match']='unresolved'; s['role']='corridor_guide_candidate'
                result['checks'].append(dict(rule='F유도등-문미확인',id=s['evidence_id'],at=list(xy),note='문 누락 또는 통로유도 역할 후보 — 기호만으로 벽에 문을 만들지 않음'))
        result['symbols'].append(s)
    for r,g in rooms:
        stats=result['rooms'][r['id']]
        if not stats['detectors']:
            result['checks'].append(dict(rule='F실-감지기없음',id=r['id'],note='감지기 미검출. 설치 예외·심볼 누락·정렬·실 분할을 검토하며 실은 유지'))
    if not alignment_verified:
        result['checks'].append(dict(rule='F정렬-미확인',id='fire',note='건축·소방 도면 정렬의 신뢰 근거가 없어 자동 재분류 보류'))
    return result


def fuse_fire(plan, result):
    """Apply supported classification only; do not split/delete/invent rooms."""
    fused=copy.deepcopy(plan)
    for o in fused['openings']:
        rec=result['openings'].get(o['id'])
        if not rec: continue
        o['fire_evidence']=copy.deepcopy(rec)
        if rec.get('decision')=='fire_supported' and result['alignment_verified']:
            o['kind_before_fire']=o['kind']; o['kind']=rec['kind_out']
            o['operation']=rec.get('operation','unknown')
            o.pop('candidate_kind',None)
        elif rec.get('candidate_kind'): o['candidate_kind']=rec['candidate_kind']
        o['connection_status']=connection_status(o,{r['id'] for r in fused['rooms']})
    for r in fused['rooms']:
        r['fire_evidence']=copy.deepcopy(result['rooms'].get(r['id'],{}))
        if r['fire_evidence'].get('corridor_lights'): r['usage_candidate']='circulation'
    fused['checks']=[c for c in fused['checks'] if not c.get('rule','').startswith('F')]+copy.deepcopy(result['checks'])
    fused['fire']=copy.deepcopy(result)
    cnt=Counter(o['kind'] for o in fused['openings'])
    for field,kind in dict(doors_open='door',doors_elev='door_elev',doors_internal='door_internal',sliding='door_sliding',windows='window',windows_inner='window_inner',vents='vent').items():
        fused['stats'][field]=cnt[kind]
    return fused


def quality_report(plan):
    """Mechanical checks are not a claim of ground-truth extraction accuracy."""
    issues=[]; room_shapes=[]
    ids=[r['id'] for r in plan['rooms']]
    if len(ids)!=len(set(ids)): issues.append(dict(rule='Q중복실ID',severity='error'))
    for family,items in [('room',plan['rooms']),('wall',[dict(id='walls',polys=plan.get('walls',[]))]),('opening',plan['openings'])]:
        for item in items:
            parts=polygon_parts(item) if family=='room' else opening_parts(item) if family=='opening' else item.get('polys',[])
            if not parts: issues.append(dict(rule='Q형상없음',severity='error',family=family,id=item['id']))
            for part in parts:
                try:
                    g=Polygon(part['o'],part.get('h',[])) if isinstance(part,dict) else Polygon(part)
                    if not g.is_valid or g.is_empty or g.area<=0:
                        issues.append(dict(rule='Q형상무효',severity='error',family=family,id=item['id']))
                except (ValueError,TypeError): issues.append(dict(rule='Q형상무효',severity='error',family=family,id=item['id']))
            if family=='room': room_shapes.append(geometry(parts))
    tree=STRtree(room_shapes)
    wall_shape=geometry(plan.get('walls',[]))
    for i,g in enumerate(room_shapes):
        if g.intersection(wall_shape).area>max(plan.get('res_m',.02)**2,.0001):
            issues.append(dict(rule='Q벽실중첩',severity='error',id=ids[i]))
        for j in tree.query(g):
            if j>i and g.intersection(room_shapes[j]).area>max(plan.get('res_m',.02)**2,.0001):
                issues.append(dict(rule='Q실중첩',severity='error',ids=[ids[i],ids[j]]))
    for o in plan['openings']:
        status=connection_status(o,set(ids)); o['connection_status']=status
        if status in ('unresolved','same_space'): issues.append(dict(rule='Q개구부연결',severity='review',id=o['id'],status=status))
    counts=Counter(c.get('rule','unknown') for c in plan.get('checks',[]))
    errors=sum(i['severity']=='error' for i in issues)
    return dict(status='invalid' if errors else 'review_required', errors=errors,issues=issues,
                check_counts=dict(counts),raster_resolution_m=plan.get('res_m'),
                ground_truth_validated=False,auto_repaired_line_count=len(plan.get('heal',{}).get('log',[])))
