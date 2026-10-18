"""Conservative automatic simplification for compartment-based MVP geometry.
All dimensions are configurable geometric tolerances, not regulatory limits.
"""
import copy
import math
from collections import Counter
import numpy as np
import cv2
from shapely.geometry import Polygon,LineString,Point,box
from shapely.ops import unary_union
from cad_evidence import geometry,polygon_parts,opening_parts,normalize_plan
from cad_topology import connection_status


def repeated_tier_arcs(inreg,inserts,unit):
    """Repeated concentric lines + repeated nearby small block insertions.
    Neither window layer nor concentric arcs alone is enough to remove a line.
    """
    groups=[]
    for p,c in inreg:
        if c!='window' or p.kind!='ARC' or p.arc is None: continue
        x,y,r,a,b=p.arc
        if r*unit<3 or not 10<(b-a)%360<100: continue
        group=next((g for g in groups if math.dist(g[0].arc[:2],(x,y))*unit<.05),None)
        if group is None: groups.append([p])
        else: group.append(p)
    # INSERT origins may be far from their drawn content when block base points
    # are offset. Use the transformed content's centre rather than insertion x/y.
    centers={}
    for primitive,category in inreg:
        if primitive.ins is None:continue
        acc=centers.setdefault(primitive.ins,[0.,0.,0])
        for x,y in primitive.pts:acc[0]+=x*unit;acc[1]+=y*unit;acc[2]+=1
    excluded=set(); records=[]
    for group in groups:
        radii=sorted(set(round(p.arc[2]*unit,3) for p in group))
        if len(radii)<4: continue
        gaps=np.diff(radii)
        if not (.35<=float(np.median(gaps))<=2 and np.std(gaps)/np.mean(gaps)<.15): continue
        xs=[x*unit for p in group for x,y in p.pts]; ys=[y*unit for p in group for x,y in p.pts]
        bounds=box(min(xs),min(ys),max(xs),max(ys)).buffer(.25)
        blocks=Counter()
        for index,i in enumerate(inserts):
            acc=centers.get(index)
            pos=(acc[0]/acc[2],acc[1]/acc[2]) if acc else (i['x']*unit,i['y']*unit)
            if bounds.contains(Point(pos)):blocks[i['name']]+=1
        if not blocks or blocks.most_common(1)[0][1]<8: continue
        excluded.update(id(p) for p in group)
        records.append(dict(rule='AUTO반복단차선',n=len(group),block=blocks.most_common(1)[0][0],
            repeated_blocks=blocks.most_common(1)[0][1],spacing_m=round(float(np.median(gaps)),3),
            note='동심 원호의 일정 간격 반복 + 같은 영역의 반복 블록 근거로 객석 단차 후보를 구획 경계에서 제외'))
    return excluded,records


def partition_agreement(base, candidate, res_mm, doors=(), sides_fn=None):
    """Match region identities by overlap, rather than comparing counts alone."""
    b=np.maximum(base,0).astype(np.int64); c=np.maximum(candidate,0).astype(np.int64)
    nc=int(c.max())+1
    matrix=np.bincount((b*nc+c).ravel(),minlength=(int(b.max())+1)*nc).reshape(-1,nc)
    area=(res_mm/1000)**2
    base_sizes=np.bincount(b.ravel(),minlength=matrix.shape[0])
    cand_sizes=np.bincount(c.ravel(),minlength=nc)
    meaningful=[i for i in range(1,len(base_sizes)) if base_sizes[i]*area>=.25]
    mapping={};retention=[];changes=[];split=False
    for i in meaningful:
        j=int(np.argmax(matrix[i,1:]))+1 if nc>1 else 0
        fraction=matrix[i,j]/max(base_sizes[i],1) if j else 0
        retention.append(fraction)
        changes.append(abs(cand_sizes[j]-base_sizes[i])/max(base_sizes[i],1) if j else 1)
        split |= np.count_nonzero(matrix[i,1:]*area>=.25)>1
        mapping[i]=j
    merged=len(set(mapping.values()))!=len(mapping)
    reverse={v:k for k,v in mapping.items()}
    connections=True
    if sides_fn:
        for door in doors:
            old=sides_fn(base,door);new=sides_fn(candidate,door)
            if len(old)!=2 or 0 in old or old[0]==old[1]:continue
            resolved=[-1 if x==-1 else reverse.get(x) for x in new]
            if resolved!=list(old):connections=False;break
    safe=(not split and not merged and min(retention,default=1)>=.85
          and max(changes,default=0)<=.15 and connections)
    return dict(safe=bool(safe),minimum_region_retention=round(float(min(retention,default=1)),4),
        maximum_area_change=round(float(max(changes,default=0)),4),
        region_split=bool(split),region_merge=bool(merged),door_neighbors_preserved=connections)


def adaptive_close(bar,protected,labels_fn,doors,sides_fn,res_mm,max_gap_mm=160):
    """Try local closing scales. Retain only a plateau with no lost door split.
    Only newly filled pixels change; existing aperture boundaries are protected.
    """
    baseline=labels_fn(bar)
    def metrics(labels):
        cnt=np.bincount(labels[labels>0].ravel())
        rooms=int(np.count_nonzero(cnt*(res_mm/1000)**2>=.25))
        pairs=[sides_fn(labels,d) for d in doors]
        valid={i for i,(a,b) in enumerate(pairs) if a!=b and a!=0 and b!=0}
        return rooms,valid
    n0,valid0=metrics(baseline); trials=[]; chosen=bar; selected=0
    previous=None
    for radius in sorted(set(max(1,round(x/res_mm)) for x in (40,80,max_gap_mm/2))):
        kernel=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(2*radius+1,)*2)
        closed=cv2.morphologyEx(bar,cv2.MORPH_CLOSE,kernel)
        added=(closed>0)&(bar==0)&~protected
        candidate=bar.copy(); candidate[added]=255
        candidate_labels=labels_fn(candidate)
        n,valid=metrics(candidate_labels)
        topology=partition_agreement(baseline,candidate_labels,res_mm,doors,sides_fn)
        safe=valid0<=valid and n0<=n<=n0+max(2,int(n0*.15)) and topology['safe']
        record=dict(radius_px=radius,gap_mm=radius*2*res_mm,rooms=n,valid_doors=len(valid),added_pixels=int(added.sum()),safe=safe,topology=topology)
        trials.append(record)
        signature=(n,tuple(sorted(valid)))
        if (safe and previous is not None and previous[0]==signature
                and partition_agreement(previous[3],candidate_labels,res_mm,doors,sides_fn)['safe']):
            chosen=previous[1]; selected=previous[2]; break
        previous=(signature,candidate,radius,candidate_labels) if safe else None
    return chosen,dict(rule='AUTO틈보강',selected_radius_px=selected,trials=trials,
        note='실 수·영역 대응·면적 변화·문 이웃 공간을 함께 비교. 기존 연결을 보존하는 안정 구간의 작은 보강폭 사용')


def parts(g):
    if g.is_empty:return []
    if g.geom_type=='Polygon':return [dict(o=[list(p) for p in g.exterior.coords[:-1]],h=[[list(p) for p in r.coords[:-1]] for r in g.interiors])]
    return [p for child in getattr(g,'geoms',[]) for p in parts(child)]


def set_room_geometry(room,g):
    room['polys']=parts(g)
    largest=max(room['polys'],key=lambda p:Polygon(p['o'],p['h']).area)
    room['poly']=largest['o'];room['holes']=largest['h'];room['area']=round(g.area,4)
    c=g.representative_point(); room['center']=[round(c.x,4),round(c.y,4)]


def isolate_elevator_cores(plan,wall_m=.12):
    """Separate known elevator block footprints and connect one observed gap.
    Uses original gap segments as evidence; no arbitrary door is invented.
    """
    p=copy.deepcopy(plan); changes=[]
    foot=geometry(p['footprint']); walls=geometry(p['walls'])
    cores=[c for c in p.get('cores',[]) if c['kind']=='elev' and c.get('src')=='block']
    gaps=[f for f in p.get('heal',{}).get('flags',[]) if f['kind'] in ('gap_elev_closed','gap_unlabeled') and f.get('to')]
    for index,c in enumerate(cores):
        inner=box(c['cx']-c['w']/2,c['cy']-c['h']/2,c['cx']+c['w']/2,c['cy']+c['h']/2)
        if foot.intersection(inner).area<inner.area*.95: continue
        existing=[r for r in p['rooms'] if geometry(polygon_parts(r)).intersection(inner).area>inner.area*.7
            and r['area']<inner.area*2.5
            and any(o['kind']=='door_elev' and r['id'] in o.get('sides',[]) for o in p['openings'])
            and sum(geometry(polygon_parts(r)).contains(Point(other['cx'],other['cy'])) for other in cores)==1]
        if existing:
            r=max(existing,key=lambda r:geometry(polygon_parts(r)).intersection(inner).area)
            if 'elev' not in r.get('tags',[]):r.setdefault('tags',[]).append('elev')
            c['room_id']=r['id']; continue
        shell=inner.buffer(wall_m,join_style=2); ring=shell.difference(inner)
        targets=[r for r in p['rooms'] if geometry(polygon_parts(r)).intersection(inner).area>.01]
        if not targets:continue
        cid=f'CE{index}'
        for r in targets:
            remaining=geometry(polygon_parts(r)).difference(shell)
            if remaining.is_empty:break
        else:
            for r in targets:set_room_geometry(r,geometry(polygon_parts(r)).difference(shell))
            r=dict(id=cid,tags=['elev'],names=['승강로'],approximation='CAD elevator block envelope')
            set_room_geometry(r,inner); p['rooms'].append(r); c['room_id']=cid
            walls=walls.union(ring)
            minx,miny,maxx,maxy=inner.bounds
            edges=[((minx,miny),(maxx,miny),(0,-1)),((maxx,miny),(maxx,maxy),(1,0)),
                   ((maxx,maxy),(minx,maxy),(0,1)),((minx,maxy),(minx,miny),(-1,0))]
            candidates=[]
            for gap in gaps:
                a=np.array(gap['at'])/1000;b=np.array(gap['to'])/1000;line=LineString([a,b]);v=b-a;length=np.linalg.norm(v)
                if length<.4:continue
                midpoint=line.interpolate(.5,normalized=True)
                for e0,e1,normal in edges:
                    edge=LineString([e0,e1]); ev=np.array(e1)-e0; ev=ev/np.linalg.norm(ev)
                    if abs(np.dot(v/length,ev))<.95 or edge.distance(midpoint)>.8:continue
                    pos=edge.project(midpoint); width=min(length,edge.length*.8)
                    pos=min(max(pos,width/2),edge.length-width/2)
                    center=edge.interpolate(pos)
                    for distance in (.3,.5,.8,1.1):
                        point=Point(center.x+normal[0]*distance,center.y+normal[1]*distance)
                        neighbor=next((rr for rr in p['rooms'] if rr['id']!=cid and 'elev' not in rr.get('tags',[]) and geometry(polygon_parts(rr)).contains(point)),None)
                        if neighbor:
                            candidates.append((edge.distance(midpoint)+distance*.05,edge,pos,width,neighbor['id'],gap));break
            door=None
            if candidates:
                _,edge,pos,width,neighbor,gap=min(candidates,key=lambda t:t[0])
                a=edge.interpolate(pos-width/2);b=edge.interpolate(pos+width/2)
                aperture=LineString([a,b]).buffer(wall_m*1.5,cap_style=2)
                door=dict(id=cid+'_D',kind='door_elev',sides=[cid,neighbor],connection_status='interior',leaves=[],
                    door_h=2.1,span=round(width,3),width=round(width*1000),operation='sliding',guessed=True,
                    geometry_polys=parts(aperture),polys=[z['o'] for z in parts(aperture)],
                    automatic_evidence=dict(rule='elevator_core_and_observed_gap',source_gap=gap))
                p['openings'].append(door)
            changes.append(dict(rule='AUTO승강로분리',id=cid,source_core=index,door=door['id'] if door else None,
                note='검출된 승강기 블록 영역을 홀·복도에서 분리. 도면의 인접 틈 근거가 있을 때 승강기문 연결'))
    # Re-evaluate only previously unresolved/same-space openings; never replace
    # explicit exterior sides by a guessed exterior.
    ids={r['id'] for r in p['rooms']}
    for o in p['openings']:
        if connection_status(o,ids) not in ('unresolved','same_space'):continue
        g=geometry(opening_parts(o)); mr=g.minimum_rotated_rectangle
        if mr.geom_type!='Polygon':continue
        xy=np.array(mr.exterior.coords[:4]);u=xy[1]-xy[0];v=xy[2]-xy[1]
        normal=u if np.linalg.norm(u)<np.linalg.norm(v) else v
        normal=normal/max(np.linalg.norm(normal),1e-9); center=g.centroid
        sides=[]
        for sign in (-1,1):
            hits=[]
            for distance in (.2,.4,.6,.8):
                point=Point(center.x+sign*normal[0]*distance,center.y+sign*normal[1]*distance)
                hit=next((r['id'] for r in p['rooms'] if geometry(polygon_parts(r)).contains(point)),None)
                if hit:hits.append(hit)
            sides.append(hits[0] if hits else None)
        if all(sides) and sides[0]!=sides[1]:o['sides']=sides
    p['walls']=parts(walls);p['checks']+=changes
    for o in p['openings']:o['connection_status']=connection_status(o,ids)
    p['stats']['rooms']=len(p['rooms']);p['stats']['doors_elev']=sum(o['kind']=='door_elev' for o in p['openings'])
    p['automatic_repairs']=changes
    return normalize_plan(p)
