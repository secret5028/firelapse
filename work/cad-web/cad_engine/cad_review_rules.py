"""Optional, source-hash-bound human review; never a universal CAD exception."""
import hashlib,json
from pathlib import Path


def apply_source_review(filename, primitives, categories, profile):
    if not profile:return None
    sha=hashlib.sha256(Path(filename).read_bytes()).hexdigest()
    if profile['source_sha256']!=sha:raise ValueError('Review profile belongs to a different CAD source')
    found=[]
    rules={item['handle']:item for item in profile.get('source_categories',[])}
    for i,p in enumerate(primitives):
        rule=rules.get(p.source.get('handle'))
        if rule:
            if p.layer!=rule['expected_layer']:raise ValueError('Reviewed entity layer changed')
            categories[i]=rule['category'];found.append(rule['handle'])
    if set(found)!=set(rules):raise ValueError('Reviewed CAD entity missing')
    return dict(source_sha256=sha,mode='human_reviewed_source_entities',profile=profile,
                promoted_handles=found)


def apply_candidate_review(plan):
    """Remove verified non-opening candidates and qualify ambiguous symbols."""
    from cad_evidence import geometry,opening_parts,polygon_parts
    from shapely.geometry import box
    from shapely.geometry import LineString
    import re
    from cad_topology import connection_status
    from cad_connectivity import aperture_frame
    from collections import Counter
    review=plan.get('source_review') or {}
    rules=review.get('profile',{}).get('exclude_candidates',[])
    rooms=[geometry(polygon_parts(r)) for r in plan['rooms']]
    kept=[]; rejected=[]
    for o in plan['openings']:
        g=geometry(opening_parts(o));rule=None
        for r in rules:
            area=box(*r['bounds_m'])
            if area.covers(g.centroid) and g.area and g.intersection(area).area/g.area>.75:
                rule=dict(rule='reviewed_non_opening',reason=r['reason'],review_alias=r['alias'],
                          decision='human_assisted_source_review',note=r['note']);break
        status=connection_status(o,{r['id'] for r in plan['rooms']})
        if rule is None and o.get('sides')==['out','out']:
            # A leaf span may extend beyond a malformed footprint. Do not erase
            # a vestibule door just because two local samples said 'out'.
            nearby=min((g.distance(r) for r in rooms),default=999.)
            if not o.get('leaves') and nearby>.35:
                rule=dict(rule='outside_outside_non_compartment',reason='no_adjacent_indoor_compartment',
                          nearest_room_m=round(nearby,3),decision='excluded_from_building_flow_model',
                          note='외기↔외기 부속 선: 실내 구획과 접하지 않아 건물 개구부에서 제외')
        leaves=o.get('leaves',[])
        if (rule is None and status=='same_space' and leaves
                and not any(l.get('leaf_line') or l.get('pair') for l in leaves)
                and o.get('host_evidence',{}).get('status') in ('partial','unsupported')
                and not o.get('kind_before_fire') and not o.get('automatic_evidence')):
            explicit_door=any(re.search(r'DOOR|DOFRAME|셔터|SHUTTER',v['layer'],re.I)
                and LineString(v['points']).distance(g)<.15 for v in plan.get('source_vectors',[]) if len(v['points'])>1)
            from shapely.geometry import Point
            frame_pending=any(g.distance(Point(e['hinge']))<.25 for e in plan.get('layer_evidence',{}).get('weak_door_evidence',[]))
            if frame_pending:
                o['symbol_evidence']=dict(status='boundary_review_pending',reason='frame_without_independent_leaf',
                    note='전체 레이어에서 문틀/이중 경계 근거 발견. 문짝과 구획이 불완전하여 후보 유지, 유동 연결 보류')
            if not explicit_door and not frame_pending:
                rule=dict(rule='arc_requires_leaf_or_partition',reason='arc_only_without_independent_door_support',
                          decision='insufficient_evidence_candidate_not_ground_truth',
                          note='호만 존재·문짝/양개문 근거 없음·양쪽 동일 공간·벽 지지 불충분: 문 후보에서 제외, 원본 보존')
        if rule:
            rejected.append(dict(o,rejection=rule));continue
        if status in ('same_space','unresolved'):
            leaves=o.get('leaves',[])
            if leaves and not any(l.get('leaf_line') or l.get('pair') for l in leaves) and 'symbol_evidence' not in o:
                o['symbol_evidence']=dict(status='insufficient',reason='arc_without_verified_leaf',
                    note='호만 있고 확인된 문짝선·양개문 짝이 없음. 벽 경계와 개폐 근거 확인 전 유동 연결 제외')
            elif o['kind'] in ('window','window_inner'):
                o['symbol_evidence']=dict(status='window_operation_unknown',
                    note='개폐 흔적이 없는 창 후보. 고정창 가능성이 있어 흔적 부재만으로 삭제하지 않음')
        kept.append(o)
    plan['openings']=kept;plan.setdefault('rejected_openings',[]).extend(rejected)
    plan['candidate_review_summary']=dict(rejected=len(rejected),retained_uncertain=sum('symbol_evidence' in o for o in kept))
    plan['checks'].extend(dict(rule='개구부후보재검토',id=o['id'],note=o['rejection']['note']) for o in rejected)
    counts=Counter(o['kind'] for o in kept)
    for field,kind in dict(doors_open='door',doors_elev='door_elev',doors_internal='door_internal',sliding='door_sliding',windows='window',windows_inner='window_inner',vents='vent').items():plan['stats'][field]=counts[kind]
    return plan


def apply_space_review(plan):
    """Source-bound roof/reference regions are not enclosed fire compartments."""
    from cad_evidence import geometry,polygon_parts
    from shapely.geometry import box
    rules=(plan.get('source_review') or {}).get('profile',{}).get('non_compartment_regions',[])
    excluded=[];kept=[]
    for room in plan['rooms']:
        g=geometry(polygon_parts(room))
        rule=next((r for r in rules if box(*r['bounds_m']).covers(g.centroid) and g.area and g.intersection(box(*r['bounds_m'])).area/g.area>.95),None)
        if rule:excluded.append(dict(room,classification=rule))
        else:kept.append(room)
    ids={r['id'] for r in excluded};plan['rooms']=kept
    for o in plan['openings']:o['sides']=['out' if s in ids else s for s in o.get('sides',[])]
    plan['non_compartment_regions']=excluded;plan['stats']['rooms']=len(kept)
    for r in excluded:plan['checks'].append(dict(rule='검토-비실내영역',id=r['id'],note=r['classification']['note']))
    return plan
