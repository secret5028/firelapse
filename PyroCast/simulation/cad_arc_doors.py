"""User assumption: every recorded interior CAD arc denotes a door.

Door presence and flow connectivity are separate. Unbound arcs never get a
fabricated exterior or an arbitrary nearest-room link. Nested room resolution
is explicitly inferred and leaves the overlapping room geometry untouched.
"""
from copy import deepcopy
import math
import numpy as np
from shapely.geometry import Point,LineString
from cad_connectivity_shared import geometry

def bind_leaf(leaf,shapes,policy):
    h=np.array(leaf['hinge'],float);e=np.array(leaf['closed'],float);u=e-h
    length=float(np.linalg.norm(u))
    if length<1e-6:return dict(sides=None,reason='degenerate_leaf')
    u/=length;n=np.array([-u[1],u[0]]);samples=[];resolved=[];nested=False
    for sign in (-1,1):
        side=[];chosen=[]
        for along in policy['probe_along_fractions']:
            for gap in policy['probe_gaps_m']:
                # Do not let a millimetre drafting arc probe across a whole wall.
                p=Point(*((h+e)/2+u*length*.5*along+n*sign*min(gap,length*.5)))
                hits=sorted((k for k,g in shapes.items() if g.contains(p)),key=lambda k:(shapes[k].area,k));side.append(hits)
                if len(hits)==1:chosen.append(hits[0])
                elif len(hits)>1:
                    small=shapes[hits[0]]
                    # Proper containment, not simply choosing the smallest hit.
                    if all(small.area<shapes[k].area and small.difference(shapes[k]).area<=small.area*policy['nested_outside_fraction_max'] for k in hits[1:]):
                        chosen.append(hits[0]);nested=True
                    else:chosen.append(None)
                else:chosen.append(None)
        samples.append(side);resolved.append(chosen[0] if chosen and all(x==chosen[0] for x in chosen) else None)
    valid=all(resolved) and resolved[0]!=resolved[1]
    return dict(sides=resolved if valid else None,candidates=resolved,samples=samples,
        confidence='inferred' if nested else 'geometry',reason='nested_room_boundary' if nested else 'two_sided_leaf_probes')

def apply_arc_doors(floor,policy):
    if not policy.get('interior_arcs_are_doors',False):return dict(changes=[],reviews=[],inventory=[])
    shapes={r['id']:geometry(r['polys']) for r in floor['rooms']};inside=geometry(floor.get('slab',[]))
    changes=[];reviews=[];original=list(floor['openings']);by_id={o['id']:o for o in original};inventory=[]
    def valid(s):return len(s)==2 and s[0]!=s[1] and all(x in shapes or x=='out' for x in s)
    def record(o,kind,before,after,**more):
        c=dict(kind=kind,before=before,after=after,basis='user_assumption_interior_arc_is_door',**more)
        o.setdefault('auto_corrections',[]).append(c);changes.append(dict(floor=floor['name'],id=o['id'],**c))
    def note(o,binding):
        reviews.append(dict(floor=floor['name'],id=o['id'],kind='door_connection_estimated',
            detail='문 있음 · 연결 대상 추정 (실 폴리곤 중첩)' if binding.get('sides') else '문 있음 · 연결 대상 미확정',
            **binding))
    def child(parent,leaf,index,binding):
        name=f"{parent['id']}_ARC{index}";h=np.array(leaf['hinge']);e=np.array(leaf['closed']);u=e-h;w=float(np.linalg.norm(u));n=np.array([-u[1],u[0]])/w*.025
        o=deepcopy(parent)
        for key in ('auto_corrections','superseded_by','span','geometry_polys','autocorrect_aperture_polys','connection_status'):o.pop(key,None)
        o.update(id=name,kind='door',sides=binding['sides'],leaves=[deepcopy(leaf)],span=round(w,4),
            polys=[[(h-n).tolist(),(e-n).tolist(),(e+n).tolist(),(h+n).tolist()]],
            source_parent_id=parent['id'],source_leaf_index=index,door_presence='user_assumed_from_interior_arc',
            connection_evidence=binding,connection_confidence=binding['confidence'])
        record(o,'arc_door_connection',parent.get('sides'),o['sides'],source_parent_id=parent['id'],source_leaf_index=index,confidence=binding['confidence'])
        floor['openings'].append(o);by_id[name]=o
        if binding['confidence']=='inferred':note(o,binding)
        return o

    # Handle existing arc/leaf evidence first; never let a merged envelope hide a leaf.
    known=[]
    for o in original:
        if o.get('source_parent_id'):continue
        for i,l in enumerate(o.get('leaves') or []):known.append((o,i,l))
        if o.get('superseded_by'):
            for name in o['superseded_by']:
                sub=by_id[name]
                if sub.get('connection_confidence')=='inferred':note(sub,sub['connection_evidence'])
            continue
        bindings=[]
        for i,l in enumerate(o.get('leaves') or []):
            h=l['hinge'];e=l['closed']
            if not inside.is_empty and not inside.buffer(.02).covers(LineString([h,e])):continue
            b=bind_leaf(l,shapes,policy);bindings.append((i,l,b))
        if not bindings:continue
        o['door_presence']='user_assumed_from_interior_arc'
        old=o.get('sides') or []
        if valid(old):
            # Preserve a valid original doorway. Do not add another flow edge for it.
            for _,_,b in bindings:
                if b['sides'] and set(b['sides'])==set(old) and b['confidence']=='inferred':
                    o['connection_confidence']='inferred';o['connection_evidence']=b;note(o,b)
            continue
        good=[(i,l,b) for i,l,b in bindings if b['sides']]
        if len(o['leaves'])==1 and good:
            b=good[0][2];o['sides']=b['sides'];o['connection_evidence']=b;o['connection_confidence']=b['confidence']
            record(o,'arc_door_connection',old,b['sides'],confidence=b['confidence'])
            if b['confidence']=='inferred':note(o,b)
        elif good:
            # Merge coplanar leaves serving the same pair rather than duplicating a double door.
            groups=[]
            for i,l,b in good:
                h=np.array(l['hinge']);e=np.array(l['closed']);u=(e-h)/np.linalg.norm(e-h);n=np.array([-u[1],u[0]])
                match=next((g for g in groups if set(g[0][2]['sides'])==set(b['sides']) and any(LineString([h,e]).distance(LineString([ll['hinge'],ll['closed']]))<=policy['boundary_tolerance_m'] for _,ll,_ in g) and all(abs((np.array(p)-h)@n)<=policy['boundary_tolerance_m'] for _,ll,_ in g for p in [ll['hinge'],ll['closed']])),None)
                if match is None:groups.append([(i,l,b)])
                else:match.append((i,l,b))
            children=[]
            for g in groups:
                i,l,b=g[0];merged=deepcopy(l)
                if len(g)>1:
                    points=np.array([p for _,ll,_ in g for p in [ll['hinge'],ll['closed']]]);u=np.array(l['closed'],float)-l['hinge'];u/=np.linalg.norm(u);proj=points@u
                    merged.update(hinge=points[np.argmin(proj)].tolist(),closed=points[np.argmax(proj)].tolist())
                new=child(o,merged,i,b);new['source_leaf_indices']=[x[0] for x in g];children.append(new['id'])
            o['superseded_by']=children
            record(o,'split_arc_bundle',old,children)
        for _,_,b in bindings:
            if not b['sides']:note(o,b)

    # All source interior arcs are doors under the user rule, even without an
    # identified closed leaf. Such arcs remain inventory, not invented flow vents.
    for arc in floor.get('cad_arcs',[]):
        if not arc.get('inside_building'):continue
        match=next(((o,i) for o,i,l in known if math.dist(arc['center'],l['hinge'])<=.03 and abs(arc['radius_m']-l['r'])<=.06),None)
        row=dict(id=arc['id'],door_presence='user_assumed_from_interior_arc',center=arc['center'],radius_m=arc['radius_m'])
        if match:
            o,i=match;links=[x for x in floor['openings'] if x.get('source_parent_id')==o['id'] and i in x.get('source_leaf_indices',[x.get('source_leaf_index')])]
            row.update(source_opening=o['id'],source_leaf_index=i,opening_ids=[x['id'] for x in links] or ([o['id']] if valid(o.get('sides') or []) and not o.get('superseded_by') else []))
        else:
            created=by_id.get(arc['id']);choices=[]
            # A radial CAD line identifies the leaf; the other arc endpoint is
            # tested as the closed plane too. Multiple distinct pairs stay unknown.
            support=arc.get('radial_line_support',[False,False])
            if any(support):
                # CAD can draw either the closed frame or the open leaf as a
                # radial line. Test both; accept only one consistent closed plane.
                # Verified against the 5F EPS/PS 15-degree inspection doors.
                for e in (arc['start'],arc['end']):
                    leaf=dict(hinge=arc['center'],closed=e,open=arc['end'] if e==arc['start'] else arc['start'],r=arc['radius_m'],r_std=arc['radius_m'])
                    b=bind_leaf(leaf,shapes,policy)
                    if b['sides']:choices.append((leaf,b))
            pairs={tuple(sorted(b['sides'])) for _,b in choices}
            if created is None and len(pairs)==1 and len(choices)==1:
                l,b=choices[0]
                plane=LineString([l['hinge'],l['closed']])
                duplicate=next((o for o in floor['openings'] if not o.get('superseded_by') and set(o.get('sides') or [])==set(b['sides']) and any(plane.hausdorff_distance(LineString([ll['hinge'],ll['closed']]))<=.06 for ll in o.get('leaves',[]))),None)
                if duplicate:
                    row.update(opening_ids=[duplicate['id']],connection_state='linked');inventory.append(row);continue
                parent=dict(id=arc['id'],kind='door',sides=[None,None],leaves=[],door_h=floor.get('door_h') or 2.1)
                created=child(parent,l,0,b);old_name=created['id'];created['id']=arc['id'];by_id.pop(old_name);by_id[created['id']]=created
                changes[-1]['id']=created['id']
                if reviews and reviews[-1]['id']==old_name:reviews[-1]['id']=created['id']
                created['source_arc_id']=arc['id'];created['source_parent_id']=None
            row['opening_ids']=[created['id']] if created else []
        row['connection_state']='linked' if row.get('opening_ids') else 'unresolved'
        inventory.append(row)
    floor['arc_door_inventory']=inventory
    missing=sum(x['connection_state']=='unresolved' for x in inventory)
    if missing:reviews.append(dict(floor=floor['name'],id='ARC_UNRESOLVED',kind='arc_doors_unresolved',detail=f'문으로 간주한 내부 호 {missing}개 · 연결 대상 미확정',count=missing))
    return dict(changes=changes,reviews=reviews,inventory=inventory)
