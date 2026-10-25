"""One-way aperture exposure in explicit shared coordinates; incident kW/m²."""
import itertools
import math
import numpy as np
from functools import lru_cache
from .openings import realized_fraction
from .deck import opening_frame, active_fuels
from .thermal import SIGMA


def room_series(model,result):
    t=result['zone']['Time']; output={}
    if not result['rooms']:
        raise ValueError('CFBT room diagnostics required for supplementary exposure')
    for i,room in enumerate(model['rooms'],1):
        rows=[r for r in result['rooms'] if r['room_index']==i]
        if len(rows)!=len(t) or not np.allclose([r['time_s'] for r in rows],t):
            raise ValueError('Misaligned room diagnostics')
        output[room['id']]={k:np.array([r[k] for r in rows]) for k in rows[0]}
        mix=[r for r in result.get('mixture',[]) if r['room_index']==i]
        if mix:
            if len(mix)!=len(t):raise ValueError('Misaligned mixture diagnostics')
            output[room['id']].update({k:np.array([r[k] for r in mix]) for k in mix[0] if k not in ('time_s','room_index')})
        for layer,code in [('upper','ULOD'),('lower','LLOD')]:
            key=f'{code}_{i}'
            if key in result['zone']:
                output[room['id']][f'optical_density_{layer}_m_inv']=result['zone'][key]
    return output


def _transfer(a,b,state,boundary):
    distance=float(np.linalg.norm(b-a)); dz=b[2]-a[2]
    if abs(dz)<1e-12:
        low=(a[2]<state['interface']).astype(float)*distance
    else:
        low=np.clip((state['interface']-min(a[2],b[2]))/abs(dz),0,1)*distance
    tl=np.exp(-state['k'][0]*low); tu=np.exp(-state['k'][1]*(distance-low))
    el=SIGMA*state['T'][0]**4*(1-tl); eu=SIGMA*state['T'][1]**4*(1-tu)
    emission=el*tu+eu if dz>=0 else eu*tl+el
    return boundary*tl*tu+emission,tl*tu


def _inside(point,polys):
    def ring(points):
        x,y=point; yes=False
        for a,b in zip(points,points[1:]+points[:1]):
            if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:yes=not yes
        return yes
    return any(ring(p['o']) and not any(ring(h) for h in p.get('h',[])) for p in polys)


def _polygon_exit(p,direction,polys):
    hits=[0.]
    cross=lambda a,b:a[0]*b[1]-a[1]*b[0]
    for poly in polys:
        for ring in [poly['o'],*poly.get('h',[])]:
            for a,b in zip(ring,ring[1:]+ring[:1]):
                a=np.array(a);edge=np.array(b)-a;det=cross(direction[:2],edge)
                if abs(det)<1e-12:continue
                delta=a-p[:2];distance=cross(delta,edge)/det;fraction=cross(delta,direction[:2])/det
                if distance>1e-7 and -1e-7<=fraction<=1+1e-7:hits.append(distance)
    hits=sorted(set(hits))
    for a,b in zip(hits,hits[1:]):
        if _inside(p[:2]+direction[:2]*(a+b)/2,polys):return b
    return None


def _visible(a,b,polys,tolerance=.35):
    delta=b-a;distance=float(np.linalg.norm(delta))
    if distance<1e-10:return True
    exit_distance=_polygon_exit(a,delta/distance,polys)
    return exit_distance is not None and exit_distance>=distance-tolerance


@lru_cache(maxsize=16)
def _quadrature(n):
    nodes,weights=np.polynomial.legendre.leggauss(n)
    nodes.flags.writeable=False; weights.flags.writeable=False
    return nodes,weights


def _aperture(target,normal,halfwidth,zlo,zhi,bounds,src,recv,n,ambient_K=293.15,wall_epsilon=.94,physical_polys=None,receiver_polys=None):
    nodes,weights=_quadrature(n)
    total=np.zeros(len(src['interface']))
    if target[1]<=0:return total
    for i,x in enumerate(nodes):
        for j,z in enumerate(nodes):
            p=np.array([x*halfwidth,0.,(zlo+zhi+z*(zhi-zlo))/2])
            vec=p-target; distance=float(np.linalg.norm(vec)); direction=vec/distance
            cosine=max(0.,float(normal@direction)); cosdoor=-direction[1]
            if cosine<=0:continue
            if receiver_polys is not None and not _visible(target,p,receiver_polys):continue
            factor=cosine*cosdoor*weights[i]*weights[j]*halfwidth*(zhi-zlo)/2/(math.pi*distance**2)
            hits=[]
            for axis,(lo,hi) in enumerate(bounds):
                if physical_polys is not None and axis!=2:continue
                if direction[axis]>1e-12:hits.append(((hi-p[axis])/direction[axis],axis,hi))
                elif direction[axis]<-1e-12:hits.append(((lo-p[axis])/direction[axis],axis,lo))
            if physical_polys is not None:
                length=_polygon_exit(p,direction,physical_polys)
                if length is None:continue
                hits.append((length,0,float('nan')))
            hits=[h for h in hits if h[0]>1e-8]
            if not hits and physical_polys is not None:continue
            if not hits:raise ValueError('Aperture source box does not intersect ray')
            length,axis,face=min(hits,key=lambda h:h[0]); end=p+length*direction
            wall=(src['walls'][0] if axis==2 and abs(face-bounds[2][0])<1e-9 else
                  src['walls'][3] if axis==2 else np.where(end[2]>=src['interface'],src['walls'][2],src['walls'][1]))
            old=np.where(p[2]>=recv['interface'],recv['walls'][2],recv['walls'][1])
            emitted=wall_epsilon*SIGMA*wall**4+(1-wall_epsilon)*SIGMA*ambient_K**4
            background=wall_epsilon*SIGMA*old**4+(1-wall_epsilon)*SIGMA*ambient_K**4
            incoming,_=_transfer(end,p,src,emitted)
            _,attenuation=_transfer(p,target,recv,0.)
            total+=factor*attenuation*(incoming-background)/1000
    return total


def emission_points(room, original, count):
    """At most nine postprocessing points; no extra CFAST fires or plumes."""
    if count == 1:
        return [np.asarray(original,float)]
    side=int(math.sqrt(count)); points=[]
    if room.get('cad_polys'):
        xy=np.array([p for poly in room['cad_polys'] for p in poly['o']])
        lo=xy.min(axis=0);hi=xy.max(axis=0)
    else:
        lo=np.array(room['origin_m'][:2]);hi=lo+room['size_m'][:2]
    for x in range(side):
        for y in range(side):
            p=np.array([*(lo+(hi-lo)*np.array([(x+.5)/side,(y+.5)/side])),original[2]])
            if not room.get('cad_polys') or _inside(p[:2],room['cad_polys']):points.append(p)
    return points or [np.asarray(original,float)]


def emission_samples(room, group, original, count):
    """Area-weighted quadrature of the same fuel layout; no added energy/FIREs."""
    units=group.get('fuel_units',[])
    if not units:
        points=emission_points(room,original,count)
        return [(p,1/len(points)) for p in points]
    xy=np.array([u['position_m'][:2] for u in units]);lo=xy.min(axis=0);span=np.maximum(xy.max(axis=0)-lo,1e-9)
    side=int(math.sqrt(count));bins=np.minimum(side-1,((xy-lo)/span*side).astype(int));samples=[]
    for cell in sorted(set(map(tuple,bins))):
        indices=np.flatnonzero(np.all(bins==cell,axis=1))
        weights=np.array([units[i]['budget_fraction'] for i in indices]);weight=float(weights.sum())
        centre=np.average(xy[indices],axis=0,weights=weights)
        i=indices[np.argmin(np.linalg.norm(xy[indices]-centre,axis=1))]
        samples.append((np.array([*xy[i],original[2]]),weight))
    total=sum(weight for _,weight in samples)
    return [(p,weight/total) for p,weight in samples]


def supplementary(model,result,target,states,committed,transitions=None):
    t=result['zone']['Time']; count=len(t); settings=model['spread']
    visible_cache={};visible_shapes={}
    def cached_visible(a,b,polys):
        visible_shapes[id(polys)]=polys  # Retain objects so IDs cannot be reused within this exposure.
        key=(tuple(a[:2]),tuple(b[:2]),id(polys))
        if key not in visible_cache:visible_cache[key]=_visible(a,b,polys)
        return visible_cache[key]

    rooms={r['id']:r for r in model['rooms']}; receiver=target['room']
    point=np.array(target['xyz']); normal=np.array(target['normal'])
    terms={k:np.zeros(count) for k in ('aperture','fire_through_vent','djet')}
    near=np.zeros(count,bool)
    active=active_fuels(model,committed)
    event_positions={g['id']:g.get('position_m') for g in active}
    event_positions.update({e['group']:e['xyz'] for e in committed})
    switched={e['room']:e['t_ign_s'] for e in (transitions or [])}
    for vi,opening in enumerate(model.get('openings',[]),1):
        if opening.get('type')=='FLOOR':continue
        if receiver not in (opening['a'],opening['b']) or opening['b']=='OUTSIDE':continue
        source=opening['b'] if receiver==opening['a'] else opening['a']
        center,ex,ey=opening_frame(opening,rooms)
        if receiver==opening['a']: ey=-ey
        transform=np.array([ex,ey,[0,0,1]])
        local=lambda p:transform@(np.array(p)-center)
        localpoint=local(point); localnormal=transform@normal
        lo=np.array(rooms[source]['origin_m']); hi=lo+rooms[source]['size_m']
        corners=np.array([local(p) for p in itertools.product(*zip(lo,hi))])
        bounds=list(zip(corners.min(axis=0),corners.max(axis=0)))
        physical=None;receiver_physical=None
        if 'cad_polys' in rooms[source]:
            def local_polys(rid):return [{'o':[local([*p,center[2]])[:2].tolist() for p in poly['o']],
                       'h':[[local([*p,center[2]])[:2].tolist() for p in ring] for ring in poly.get('h',[])]}
                      for poly in rooms[rid]['cad_polys']]
            physical=local_polys(source);receiver_physical=local_polys(receiver)
        def gasstate(rid,indices):
            s=states[rid]
            return {'interface':s['interface_m'][indices]+rooms[rid]['origin_m'][2]-center[2],
                    'T':[s['T_lower_C'][indices]+273.15,s['T_upper_C'][indices]+273.15],
                    'k':[s['k_lower_m_inv'][indices],s['k_upper_m_inv'][indices]],
                    'walls':[s[k][indices] for k in ('floor_K','lower_wall_K','upper_wall_K','ceiling_K')]}
        fractions=realized_fraction(result,opening,t)
        # Same effective-width convention as CFAST horizontal vents; centered is a declared geometry assumption.
        for fraction in np.unique(fractions):
            if fraction<=0:continue
            indices=np.flatnonzero(fractions==fraction)
            src=gasstate(source,indices); recv=gasstate(receiver,indices)
            terms['aperture'][indices]+=_aperture(localpoint,localnormal,opening['width_m']*fraction/2,
                opening.get('bottom_m',0),opening['top_m'],bounds,src,recv,settings['quadrature_n'],model['ambient_C']+273.15,model['wall_material']['emissivity'],physical,receiver_physical)
        src=gasstate(source,np.arange(count)); recv=gasstate(receiver,np.arange(count))
        for fi,group in enumerate(active,1):
            if group['room']!=source:continue
            q=result['zone'].get(f'HRR_{fi}'); qc=result['zone'].get(f'HRRC_{fi}')
            if q is None or qc is None:raise ValueError('Missing actual fire radiation output')
            heights=result['zone'].get(f'FLHGT_{fi}')
            if heights is None:raise ValueError('Missing native flame height for aperture radiation')
            positions=emission_samples(rooms[source],group,event_positions[group['id']],model['flashover'].get('radiation_points',1))
            for j in range(count):
                if fractions[j]<=0 or q[j]<=0:continue
                blend=np.clip((t[j]-switched.get(source,float('inf')))/model['flashover']['transition_s'],0,1)
                weighted=[(event_positions[group['id']],1-blend)]+[(p,blend*weight) for p,weight in positions]
                for position,weight in weighted:
                    if weight<=0:continue
                    p=np.array(position,float).copy()
                    base=p[2];p[2]=base+min(max(0.,heights[j]),max(0.,rooms[source]['origin_m'][2]+rooms[source]['size_m'][2]-base))/3
                    a=local(p); ray=a-localpoint
                    if abs(ray[1])<1e-12:continue
                    lam=-localpoint[1]/ray[1];hit=localpoint+lam*ray
                    if not (0<lam<1 and abs(hit[0])<=opening['width_m']*fractions[j]/2 and opening.get('bottom_m',0)<=hit[2]<=opening['top_m']):continue
                    if physical is not None and (not cached_visible(a,hit,physical) or not cached_visible(localpoint,hit,receiver_physical)):continue
                    distance=max(.05,float(np.linalg.norm(p-point)))
                    unit=(p-point)/distance; cosine=max(0.,float(normal@unit))
                    ss={k:([v[j:j+1] for v in value] if isinstance(value,list) else value[j:j+1]) for k,value in src.items()}
                    rs={k:([v[j:j+1] for v in value] if isinstance(value,list) else value[j:j+1]) for k,value in recv.items()}
                    _,tau1=_transfer(a,hit,ss,0); _,tau2=_transfer(hit,localpoint,rs,0)
                    terms['fire_through_vent'][j]+=weight*max(0,float(q[j]-qc[j]))/1000*cosine/(4*math.pi*distance**2)*float(tau1[0]*tau2[0])
        src_index=next(i for i,r in enumerate(model['rooms'],1) if r['id']==source)
        recv_index=next(i for i,r in enumerate(model['rooms'],1) if r['id']==receiver)
        rows=[r for r in result['vents'] if r['vent_index']==vi and r['room_from']==src_index and r['room_to']==recv_index]
        if len(rows)!=count:raise ValueError('Missing per-vent directional combustion diagnostics')
        flame=center.copy(); flame[2]+=opening['top_m']
        vector=flame-point; distance=float(np.linalg.norm(vector)); cosine=max(0.,float(normal@(vector/max(distance,1e-12))))
        qv=np.array([r['HRR_W'] for r in rows])
        terms['djet']+=settings['djet_radiative_fraction']*qv/1000*cosine/(4*math.pi*max(distance,settings['djet_r_min_m'])**2)
        near|=(distance<settings['near_flame_m'])&(qv>0)
    return terms,near
