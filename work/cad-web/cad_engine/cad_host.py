"""Check ambiguous apertures against independent CAD wall/jamb evidence.

The raster wall mask cannot prove a host wall: it was partly made from the
candidate symbols themselves. Use original wall and column vectors instead.
Rejected symbols remain auditable, not deleted from the source CAD.
"""
import copy
import math
from collections import Counter
import numpy as np
from shapely.geometry import LineString,Point
from shapely.ops import unary_union
from shapely.strtree import STRtree
from cad_connectivity import aperture_frame
from cad_evidence import geometry,opening_parts,polygon_parts
from cad_topology import connection_status


def wall_segments(plan):
    result=[]
    for v in plan.get('source_vectors',[]):
        if v['category'] not in ('wall','column') or v.get('excluded_from_boundary') or v.get('excluded_by_auto'):continue
        pts=v['points']
        if v.get('closed'):pts=pts+[pts[0]]
        for a,b in zip(pts,pts[1:]):
            if math.dist(a,b)>=.08:result.append((LineString([a,b]),v['id'],v['category']))
    return result


def host_evidence(o,segments,tree):
    frame=aperture_frame(o)
    if frame is None:return dict(status='unknown',reason='no_aperture_geometry')
    g,c,u,n,hw,hd=frame
    # Door symbols may have several leaves; use their closed spans, not a
    # centroid of disconnected raster fragments, to locate the jambs.
    if o.get('leaves'):
        pts=np.array([pt for leaf in o['leaves'] for pt in (leaf['hinge'],leaf['closed'])])
        along=pts@u;c=u*((along.min()+along.max())/2)+n*np.median(pts@n)
        hw=float((along.max()-along.min())/2)
    caps=[Point(c-u*hw),Point(c+u*hw)]
    supports=[[],[]];coverage=[];parallel_ids=[];column_ids=[]
    near=tree.query(g.buffer(.4)) if tree is not None else []
    for idx in near:
        line,vid,cat=segments[int(idx)]
        a,b=np.asarray(line.coords);delta=b-a;length=np.linalg.norm(delta)
        for side,cap in enumerate(caps):
            if line.distance(cap)<=.22:supports[side].append(vid)
        if cat=='column' and line.distance(g)<.03:column_ids.append(vid)
        if length<.25 or abs(delta@u/length)<.97:continue
        off=max(abs((a-c)@n),abs((b-c)@n))
        if off>min(hd+.15,.4):continue
        lo,hi=sorted([(a-c)@u,(b-c)@u])
        lo,hi=max(-hw,lo),min(hw,hi)
        if hi>lo:coverage.append(LineString([(lo,0),(hi,0)]));parallel_ids.append(vid)
    covered=unary_union(coverage).length/max(hw*2,1e-9) if coverage else 0.
    compact_column=bool(column_ids and hd/max(hw,1e-9)>.55 and not o.get('leaves'))
    both=all(supports)
    status='supported' if (both or covered>=.65) and not compact_column else 'partial' if (any(supports) or covered>.1) and not compact_column else 'unsupported'
    return dict(status=status,reason='column_surround_symbol' if compact_column else 'independent_wall_and_jamb_check',
        jambs=[sorted(set(x)) for x in supports],parallel_coverage=round(covered,4),
        wall_vectors=sorted(set(parallel_ids)),column_vectors=sorted(set(column_ids)),
        compact_column=compact_column)


def exterior_sides(o,plan,host):
    """Require a supported aperture along an outer boundary, with one room.

    Being near a building bounding box or touching a boundary at one point is
    insufficient. No nearest-room assignment across walls is allowed.
    """
    if host['status']!='supported':return None
    frame=aperture_frame(o)
    if frame is None:return None
    g,c,u,n,hw,hd=frame
    foot=geometry(plan['footprint'])
    outer=[p.exterior for p in (list(foot.geoms) if hasattr(foot,'geoms') else [foot]) if p.geom_type=='Polygon']
    border=unary_union(outer)
    if g.distance(border)>.12:return None
    axis=LineString([c-u*hw*.8,c+u*hw*.8])
    if axis.intersection(border.buffer(hd+.12)).length<axis.length*.8:return None
    rooms=[(r['id'],geometry(polygon_parts(r))) for r in plan['rooms']]
    solid=geometry(plan['walls']).difference(g.buffer(.06))
    votes=[]
    for shift in (-.25,0,.25):
        origin=c+u*hw*shift;pair=[]
        for sign in (-1,1):
            hit=None
            for extra in (.08,.2,.4,.6,.9):
                pt=Point(origin+sign*n*(hd+extra));ray=LineString([origin,pt])
                if ray.intersection(solid).length>.06:break
                matches=[rid for rid,room in rooms if room.contains(pt)]
                if len(matches)==1:hit=matches[0];break
                if len(matches)>1:break
                if not foot.buffer(.04).contains(pt) and ray.intersects(border):hit='out';break
            pair.append(hit)
        votes.append(tuple(pair))
    if len(set(votes))==1 and 'out' in votes[0] and None not in votes[0] and votes[0][0]!=votes[0][1]:return list(votes[0])
    return None


def apply_host_axioms(plan):
    p=copy.deepcopy(plan);segments=wall_segments(p)
    if not segments:
        p['host_filter_summary']=dict(rejected=0,exterior_recovered=0,note='벽 원본 벡터 근거 없음: 자동 제외 보류')
        return p
    tree=STRtree([s[0] for s in segments]);ids={r['id'] for r in p['rooms']}
    rejected=[];changes=[];kept=[]
    for o in p['openings']:
        status=connection_status(o,ids)
        if status not in ('unresolved','same_space'):
            kept.append(o);continue
        host=host_evidence(o,segments,tree);o['host_evidence']=host
        sides=exterior_sides(o,p,host)
        if sides:
            before=o.get('sides');o['sides']=sides;o['connection_status']='exterior'
            if o['kind'] in ('window','window_inner'):o['kind']='window'
            o['connection_evidence']=dict(rule='supported_exterior_wall',previous_sides=before)
            changes.append(dict(rule='AUTO외벽개구부연결',id=o['id'],sides=sides,note='원본 벽 지지·바닥 외곽·실내측 공간을 함께 확인해 외기 연결'))
        # A visible door leaf or a fire-supported opening is stronger than the
        # absence of wall-layer evidence (glass walls may be in other layers).
        if (not sides and host['status']=='unsupported' and not o.get('leaves')
                and not o.get('kind_before_fire') and not o.get('automatic_evidence')):
            rejected.append(dict(o,rejection=dict(rule='opening_requires_wall_host',
                reason=host['reason'],decision='excluded_candidate_not_ground_truth',
                note='독립된 벽·양쪽 문틀 지지 근거가 없는 후보. 개구부에서 제외하고 원본과 판정 근거 보존')))
            changes.append(dict(rule='AUTO벽없는개구부제외',id=o['id'],note='벽 위 개구부 공리의 근거 부족: 모호한 기호를 개구부 목록에서 제외'))
        else:kept.append(o)
    p['openings']=kept
    p.setdefault('rejected_openings',[]).extend(rejected)
    p['checks'].extend(changes);p.setdefault('automatic_repairs',[]).extend(changes)
    count=Counter(o['kind'] for o in kept)
    for field,kind in dict(doors_open='door',doors_elev='door_elev',doors_internal='door_internal',sliding='door_sliding',windows='window',windows_inner='window_inner',vents='vent').items():p['stats'][field]=count[kind]
    p['host_filter_summary']=dict(rejected=len(rejected),exterior_recovered=sum(c['rule']=='AUTO외벽개구부연결' for c in changes),
        retained_review=sum(connection_status(o,ids) in ('same_space','unresolved') for o in kept))
    return p
