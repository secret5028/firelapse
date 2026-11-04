"""Conservative CAD input repair, never a fire-model or geometry fabrication step.

Only an unambiguous existing aperture gets new sides. Exterior is never inferred.
Nested-room arc connections are explicitly inferred; other overlaps stay unknown.
Every mutation carries its original value and evidence.
"""
from copy import deepcopy
import json
from pathlib import Path
import numpy as np
from shapely.geometry import Point
from cad_connectivity_shared import geometry, opening_parts, aperture_frame, opening_dimensions
from cad_arc_doors import apply_arc_doors
from cad_reviewed_connections import apply_reviewed_connections

CONFIG = Path(__file__).resolve().parents[1]/'config/cad-autocorrect.json'


def repair_floor(floor, policy=None):
    policy = policy or json.loads(CONFIG.read_text('utf-8'))
    shapes = {r['id']: geometry(r['polys']) for r in floor['rooms']}
    arcs = apply_arc_doors(floor, policy)
    changes, reviews = arcs['changes'], arcs['reviews']
    reviewed=apply_reviewed_connections(floor,policy)
    changes.extend(reviewed['changes']);reviews.extend(reviewed['reviews'])
    def note(o, kind, detail, **more):
        row = dict(floor=floor['name'], id=o['id'], kind=kind, detail=detail, **more)
        reviews.append(row)
        return row
    for o in floor['openings']:
        if o.get('superseded_by') or o.get('connection_evidence'):
            continue
        if not o.get('kind','').startswith(('door','window')):
            continue
        parts = opening_parts(o)
        # A solid rectangular aperture plus disconnected thin drafting fragments
        # must not acquire the width of the envelope enclosing all fragments.
        if not o.get('span') and not o.get('leaves') and len(parts)>1:
            measured=[]
            for part in parts:
                g=geometry([part]); box=g.minimum_rotated_rectangle
                if g.is_empty or box.geom_type!='Polygon' or box.area<=0:continue
                xy=np.array(box.exterior.coords[:4]); lengths=np.linalg.norm(np.roll(xy,-1,axis=0)-xy,axis=1)
                measured.append(dict(part=part,shape=g,width=float(max(lengths)),thickness=float(min(lengths)),fill=g.area/box.area))
            candidates=[m for m in measured if m['fill']>=policy['rect_fill_min']
                        and policy['rect_width_range_m'][0]<=m['width']<=policy['rect_width_range_m'][1]
                        and policy['rect_thickness_range_m'][0]<=m['thickness']<=policy['rect_thickness_range_m'][1]]
            if len(candidates)==1:
                m=candidates[0]; others=[x for x in measured if x is not m]
                share=m['shape'].area/max(sum(x['shape'].area for x in measured),1e-9)
                near=any(m['shape'].distance(shapes[s].boundary)<=policy['boundary_tolerance_m'] for s in o.get('sides',[]) if s in shapes)
                old=opening_dimensions(o)['width_m']
                if others and all(x['fill']<=policy['fragment_fill_max'] for x in others) and share>=policy['rect_area_share_min'] and near and m['width']<old:
                    change=dict(kind='aperture_width',before=old,after=round(m['width'],4),basis='single_solid_rectangle_excluding_sparse_drafting_fragments',area_share=share)
                    o['span']=round(m['width'],4)
                    o['autocorrect_aperture_polys']=[deepcopy(m['part'])]
                    o.setdefault('auto_corrections',[]).append(change)
                    changes.append(dict(floor=floor['name'],id=o['id'],**change))
        probe=deepcopy(o)
        if o.get('autocorrect_aperture_polys'):
            probe['geometry_polys']=o['autocorrect_aperture_polys']
        frame=aperture_frame(probe)
        if frame is None:
            note(o,'missing_geometry','개구부 형상 없음');continue
        _,c,u,n,w,d=frame
        leaves=o.get('leaves') or []
        if leaves:
            # Different leaf axes/planes can mean several doors merged by extraction.
            points=np.array([p for leaf in leaves for p in [leaf['hinge'],leaf['closed']]])
            if max(points@n)-min(points@n)>policy['boundary_tolerance_m']:
                note(o,'mixed_leaf_planes','여러 방향의 문짝이 묶임 · 연결 추정 보류');continue
            lo,hi=min(points@u),max(points@u);c=u*(lo+hi)/2+n*float(np.mean(points@n));w=(hi-lo)/2;d=0
        samples=[]; candidates=[]
        for sign in (-1,1):
            side=[]
            for along in policy['probe_along_fractions']:
                for gap in policy['probe_gaps_m']:
                    p=Point(*(c+u*w*along+n*sign*(d+gap)))
                    side.append(sorted(rid for rid,g in shapes.items() if g.contains(p)))
            samples.append(side)
            unique={x[0] for x in side if len(x)==1}
            candidates.append(next(iter(unique)) if len(unique)==1 and all(len(x)==1 for x in side) else None)
        old=o.get('sides') or []
        valid_old=len(old)==2 and old[0]!=old[1] and all(x=='out' or x in shapes for x in old)
        # Do not reclassify a declared exterior opening into an interior opening.
        certain=all(candidates) and candidates[0]!=candidates[1] and 'out' not in old
        if certain and set(candidates)!=set(old) and not valid_old:
            change=dict(kind='opening_sides',before=old,after=candidates,basis='all_two_sided_geometry_probes_agree',samples=samples)
            o['sides']=candidates;o.setdefault('auto_corrections',[]).append(change)
            changes.append(dict(floor=floor['name'],id=o['id'],**change))
        elif certain and valid_old and set(candidates)!=set(old):
            note(o,'ambiguous_connection','추정 · 기존 유효 연결과 기하 근거가 충돌하여 유지',candidates=candidates,existing=old,samples=samples)
        elif not certain:
            overlapping=any(len(h)>1 for side in samples for h in side)
            if overlapping or not valid_old or (all(candidates) and candidates[0]==candidates[1]):
                note(o,'ambiguous_connection','추정 · 기존 연결 유지, 자동 연결 안 함',candidates=candidates,existing=old,overlapping_hits=overlapping,samples=samples)
        elif valid_old and set(candidates)==set(old):
            o['connection_verification']='two_sided_geometry_probes_agree'
    return dict(revision=policy['revision'],policy=policy,changes=changes,reviews=reviews)
