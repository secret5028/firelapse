"""Cross-layer geometry evidence. Layer names are priors, never source deletion.

Unknown paired wall faces are adopted only in components anchored to both an
independently drawn swing/leaf and an existing structural boundary. Only the
overlapping lengths of the faces are used; no mirrored geometry is invented.
"""
import math
import numpy as np
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree
from shapely.ops import unary_union
from cadio import Prim


def radial_leaf(points, arc, unit):
    q=np.asarray(points)*unit; h=np.asarray(arc[:2])*unit; r=arc[2]*unit
    if len(q)<2:return False
    ds=np.linalg.norm(q-h,axis=1)
    if ds.min()>.06 or not .7*r<=ds.max()<=r+.06:return False
    direction=(q[ds.argmax()]-h)/ds.max()
    return np.max(np.abs((q-h)[:,0]*direction[1]-(q-h)[:,1]*direction[0]))<=.08


def cross_layer_evidence(prims,cats,unit,dashed,std_width):
    original_count=len(prims); original_cats=list(cats); lines=[]; owners=[]; segments=[]
    for i,p in enumerate(prims):
        if dashed.search(p.lt):continue
        pts=[(x*unit,y*unit) for x,y in p.pts]
        if len(pts)<2:continue
        lines.append(LineString(pts));owners.append(i)
        # Only straight faces and shallow long wall curves, never door sweeps.
        if p.arc and (p.arc[4]-p.arc[3])%360>=60:continue
        if p.closed and pts[0]!=pts[-1]:pts.append(pts[0])
        for a,b in zip(pts,pts[1:]):
            g=LineString([a,b])
            if g.length>=.18:segments.append((g,i))
    tree=STRtree(lines) if lines else None
    st=STRtree([s[0] for s in segments]) if segments else None
    pairs=[]
    for k,(g,i) in enumerate(segments):
        a,b=np.asarray(g.coords);u=(b-a)/g.length
        for j in st.query(g.buffer(.4)):
            if j<=k:continue
            other,oi=segments[j]
            if oi==i:continue
            c,d=np.asarray(other.coords);v=(d-c)/other.length
            if abs(float(u@v))<.995:continue
            delta=c-a;distance=abs(float(u[0]*delta[1]-u[1]*delta[0]))
            if not .10<=distance<=.40:continue
            lo=max(0,min(float((c-a)@u),float((d-a)@u)))
            hi=min(g.length,max(float((c-a)@u),float((d-a)@u)))
            if hi-lo<.18 or hi-lo<.65*min(g.length,other.length):continue
            ga=LineString([a+u*lo,a+u*hi])
            # Project onto the second face, preserving its real direction.
            gb=LineString([other.interpolate(other.project(Point(t))).coords[0] for t in ga.coords])
            pairs.append((ga,i,gb,oi))
    pair_geoms=[unary_union([a,b]) for a,_,b,_ in pairs]
    pt=STRtree(pair_geoms) if pairs else None
    confirmed={}; weak=[]
    for i,p in enumerate(prims):
        arc=p.arc
        if not arc or dashed.search(p.lt) or std_width(arc[2]*unit*1000) is None:continue
        if not 60<=(arc[4]-arc[3])%360<=190:continue
        h=Point(arc[0]*unit,arc[1]*unit); r=arc[2]*unit
        near=[owners[j] for j in tree.query(h.buffer(r+.08))]
        leaves=[j for j in near if j!=i and not prims[j].arc and radial_leaf(prims[j].pts,arc,unit)]
        ends=[Point(h.x+r*math.cos(math.radians(t)),h.y+r*math.sin(math.radians(t))) for t in arc[3:]]
        support=[]
        if pt is not None:
            for j in pt.query(h.buffer(r+.15)):
                g=pair_geoms[j]
                if g.distance(h)<.12 or min(g.distance(e) for e in ends)<.12:support.append(int(j))
        if leaves and support:
            confirmed[i]=dict(leaves=leaves,pairs=support)
        elif support:
            weak.append(dict(source=p.source,layer=p.raw,hinge=[h.x,h.y],reason='frame_without_independent_leaf'))
    # Flood only connected double-face components; furniture islands stay out.
    parent=list(range(len(pairs)))
    def root(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for i,g in enumerate(pair_geoms):
        for j in pt.query(g.buffer(.08)):
            if j>i and g.distance(pair_geoms[j])<=.08:parent[root(int(j))]=root(i)
    door_roots={root(j) for ev in confirmed.values() for j in ev['pairs']}
    structural=[lines[k] for k,i in enumerate(owners) if cats[i] in ('wall','column')]
    structural_tree=STRtree(structural) if structural else None
    structural_roots=set()
    if structural_tree is not None:
        for i,g in enumerate(pair_geoms):
            if any(g.distance(structural[j])<=.08 for j in structural_tree.query(g.buffer(.08))):structural_roots.add(root(i))
    anchored=door_roots&structural_roots
    log=[];door_ids=set()
    for i,ev in confirmed.items():
        # Both jamb context and an actual leaf required before crossing a
        # furniture/annotation layer prior.
        if not any(root(j) in anchored for j in ev['pairs']):continue
        for k in [i]+ev['leaves']:
            if cats[k] not in ('wall','column'):
                old=cats[k];cats[k]='door';door_ids.add(k)
                log.append(dict(primitive_index=k,source=prims[k].source,layer=prims[k].raw,from_category=old,to_category='door',rule='swing_leaf_paired_boundary'))
    # Recovery is a separate, much narrower graph. Structural networks cannot
    # carry promotion across crossing furniture, dimension or plumbing lines.
    eligible=[j for j,(_,i,_,k) in enumerate(pairs)
              if original_cats[i] in ('ignore','other') and original_cats[k] in ('ignore','other')
              and prims[i].raw==prims[k].raw and prims[i].ins==prims[k].ins
              and i not in door_ids and k not in door_ids]
    recover_parent={j:j for j in eligible}
    def rr(i):
        while recover_parent[i]!=i:recover_parent[i]=recover_parent[recover_parent[i]];i=recover_parent[i]
        return i
    eligible_set=set(eligible)
    def endpoints(j):return [Point(t) for face in (pairs[j][0],pairs[j][2]) for t in (face.coords[0],face.coords[-1])]
    for i in eligible:
        for j in pt.query(pair_geoms[i].buffer(.08)):
            j=int(j)
            if j<=i or j not in eligible_set:continue
            if prims[pairs[i][1]].raw!=prims[pairs[j][1]].raw:continue
            if min(a.distance(b) for a in endpoints(i) for b in endpoints(j))<=.08:recover_parent[rr(j)]=rr(i)
    new_door_pairs={j for i,ev in confirmed.items() if i in door_ids and original_cats[i] in ('ignore','other') for j in ev['pairs']}
    recover_door_roots={rr(j) for j in eligible if j in new_door_pairs}
    recover_structure_roots=set()
    if structural_tree is not None:
        for j in eligible:
            g=pair_geoms[j]
            if any(g.distance(structural[k])<=.08 for k in structural_tree.query(g.buffer(.08))):recover_structure_roots.add(rr(j))
    recover_roots=recover_door_roots&recover_structure_roots
    pieces={}
    for j,(a,i,b,k) in enumerate(pairs):
        if j not in eligible_set or rr(j) not in recover_roots:continue
        for g,owner in ((a,i),(b,k)):
            if owner in door_ids or cats[owner] not in ('ignore','other'):continue
            pieces.setdefault(owner,[]).append(g)
    for owner,gs in pieces.items():
        p=prims[owner];merged=unary_union(gs)
        for g in (merged.geoms if hasattr(merged,'geoms') else [merged]):
            q=Prim(p.layer,p.raw,'LINE',[(x/unit,y/unit) for x,y in g.coords],False,p.ins,lt=p.lt)
            q.source=dict(p.source,derived='paired_face_supported_interval')
            prims.append(q);cats.append('wall')
        log.append(dict(primitive_index=owner,source=p.source,layer=p.raw,from_category=cats[owner],to_category='wall',rule='paired_faces_anchored_to_door_and_structure',length_m=merged.length))
    return dict(version=1,input_primitives=original_count,scanned_layers=sorted({p.raw for p in prims}),
                accepted=log,weak_door_evidence=weak,derived_wall_pieces=len(prims)-original_count,
                rule='all_layers_scanned_geometry_gated_no_synthetic_symmetry')
