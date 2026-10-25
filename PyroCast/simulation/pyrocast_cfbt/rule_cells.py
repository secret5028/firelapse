"""r6 rectangular solver-cell input partition. No engine changes."""
from copy import deepcopy
import math
from .deck import fire_curve


def grid(w,d):
    choices=[]
    for nx in range(1,101):
        for ny in range(1,101//nx+1):
            x,y=w/nx,d/ny
            if min(x,y)>.6 and x*y<=150+1e-8 and max(x,y)/min(x,y)<=3+1e-8:
                choices.append((nx*ny,max(x,y)/min(x,y),nx,ny))
    if not choices:raise ValueError('No <=100-cell partition meets r6 geometry limits')
    return min(choices)[2:]


def partition(model, split_initial=False):
    m=deepcopy(model);original={r['id']:r for r in m['rooms']};parts={};rooms=[];manifest=[]
    for r in m['rooms']:
        w,d,h=r['size_m'];nx,ny=grid(w,d);cells=[]
        for ix in range(nx):
            for iy in range(ny):
                c=deepcopy(r);c.update(id=r['id'] if nx*ny==1 else f"{r['id']}_C{ix*ny+iy}",
                    origin_m=[r['origin_m'][0]+ix*w/nx,r['origin_m'][1]+iy*d/ny,r['origin_m'][2]],
                    size_m=[w/nx,d/ny,h],parent_room=r['id'],cell_index=[ix,iy])
                cells.append(c);rooms.append(c)
        parts[r['id']]=cells
        manifest.append({'room':r['id'],'grid':[nx,ny],'cells':[c['id'] for c in cells],'native_volume_preserved':True})
    if len(rooms)>100:raise ValueError('r6 partition exceeds native 100 compartments')
    def choose(rid,point):
        cells=parts[rid]
        return min(cells,key=lambda c:(sum(max(c['origin_m'][i]-point[i],0,point[i]-c['origin_m'][i]-c['size_m'][i])**2 for i in (0,1)),c['id']))
    groups=[];budget_notes=[]
    for g in m['fuel_groups']:
        r=original[g['room']];cells=parts[r['id']];point=g.get('solver_position_m',g['position_m'])
        if 'initial_time_s' in g:
            c=choose(r['id'],point);ng=deepcopy(g);ng['room']=c['id']
            t,q,a=fire_curve(g,r['size_m'][0]*r['size_m'][1]);ng['room_rule_curve']={'t':list(t),'q':list(q),'area':list(a),'energy_MJ':g['energy_MJ'],'initial_curve_preserved':True}
            native=[point[0],point[1],c['origin_m'][2]]
            # A source on a newly introduced cell boundary is assigned once and
            # nudged only inside that selected cell, recorded explicitly.
            native[:2]=[min(c['origin_m'][i]+c['size_m'][i]-.01,max(c['origin_m'][i]+.01,native[i])) for i in (0,1)]
            ng.update(position_m=native,solver_position_m=native)
            groups.append(ng)
            budget_notes.append({'group':g['id'],'assigned_cell':c['id'],'source_before':point,'source_after':native,
                'policy':'initial HRR/area/energy curve retained once; no duplicate reserve fuel in other cells from this budget'})
            if split_initial:
                fraction=math.prod(c['size_m'][:2])/math.prod(r['size_m'][:2])
                ng.update(energy_MJ=g['energy_MJ']*fraction,peak_kW=g['peak_kW']*fraction,
                          fuel_area_m2=g.get('fuel_area_m2',math.prod(r['size_m'][:2])*.5)*fraction)
                ng.pop('fuel_units',None)
                ng['room_rule_curve'].update(q=[float(v)*fraction for v in q],area=[float(v)*fraction for v in a],
                    energy_MJ=ng['energy_MJ'],initial_curve_preserved=False,shape_preserved=True,area_fraction=fraction)
                for sibling in cells:
                    if sibling['id']==c['id']:continue
                    share=math.prod(sibling['size_m'][:2])/math.prod(r['size_m'][:2]);reserve=deepcopy(g)
                    pos=[sibling['origin_m'][i]+sibling['size_m'][i]*v for i,v in enumerate((.5,.5,0))]
                    reserve.update(id=g['id']+'_'+sibling['id'].split('_')[-1],room=sibling['id'],
                        energy_MJ=g['energy_MJ']*share,peak_kW=g['peak_kW']*share,
                        fuel_area_m2=g.get('fuel_area_m2',math.prod(r['size_m'][:2])*.5)*share,
                        position_m=pos,solver_position_m=pos)
                    for key in ('initial_time_s','room_rule_curve','room_rule_trigger','room_vent_cap','fuel_units'):reserve.pop(key,None)
                    groups.append(reserve)
                budget_notes[-1].update(policy='r7 area-proportional energy allocation; initial curve scaled, siblings are independent standby budgets',area_fraction=fraction)
        else:
            for c in cells:
                fraction=(c['size_m'][0]*c['size_m'][1])/(r['size_m'][0]*r['size_m'][1]);ng=deepcopy(g)
                native=[c['origin_m'][0]+c['size_m'][0]/2,c['origin_m'][1]+c['size_m'][1]/2,c['origin_m'][2]]
                ng.update(id=g['id'] if len(cells)==1 else g['id']+'_'+c['id'].split('_')[-1],room=c['id'],
                          energy_MJ=g['energy_MJ']*fraction,peak_kW=g['peak_kW']*fraction,
                          fuel_area_m2=g.get('fuel_area_m2',r['size_m'][0]*r['size_m'][1])*fraction,
                          position_m=native,solver_position_m=native)
                for key in ('room_rule_curve','room_rule_trigger','room_vent_cap','fuel_units'):ng.pop(key,None)
                groups.append(ng)
    openings=[];maps=[]
    for v in m['openings']:
        if v.get('type')=='FLOOR':
            nv=deepcopy(v)
            for side in ('a','b'):
                if v[side]=='OUTSIDE':continue
                r=original[v[side]];point=v.get('center_m',[r['origin_m'][i]+r['size_m'][i]/2 for i in range(3)])
                nv[side]=choose(v[side],point)['id']
            openings.append(nv);maps.append({'opening':v['id'],'parts':[nv['id']]});continue
        r=original[v['a']];face=v['face'];axis=0 if face in ('FRONT','REAR') else 1;other=1-axis
        start=r['origin_m'][axis]+v.get('offset_m',0);end=start+v['width_m'];wall=r['origin_m'][other]+(r['size_m'][other] if face in ('REAR','RIGHT') else 0)
        children=[]
        for c in parts[r['id']]:
            if not (abs(wall-c['origin_m'][other])<1e-7 or abs(wall-c['origin_m'][other]-c['size_m'][other])<1e-7):continue
            lo=max(start,c['origin_m'][axis]);hi=min(end,c['origin_m'][axis]+c['size_m'][axis])
            if hi-lo<=1e-8:continue
            nv=deepcopy(v);nv.update(a=c['id'],width_m=hi-lo,offset_m=lo-c['origin_m'][axis])
            if v['b']!='OUTSIDE':
                peer=original[v['b']]
                if 'cad_geometry' in v and 'cad_bounds_m' in peer:
                    from .cad import native_point
                    point=native_point(peer,v['cad_geometry']['center_m'])
                else:point=[peer['origin_m'][i]+peer['size_m'][i]/2 for i in range(3)]
                nv['b']=choose(v['b'],point)['id']
            # Distances for pass-through use CAD centers if available, otherwise
            # per-compartment native aperture positions (never synthetic room gaps).
            nv['parent_opening']=v['id'];children.append(nv)
        if not math.isclose(sum(c['width_m'] for c in children),v['width_m'],rel_tol=1e-8,abs_tol=1e-7):
            raise ValueError('Cannot preserve aperture width during partition: '+v['id'])
        if len(children)>1:
            for i,nv in enumerate(children):nv['id']=v['id']+f'_P{i}'
        openings.extend(children);maps.append({'opening':v['id'],'parts':[c['id'] for c in children],'area_preserved':True})
    virtual=[]
    for rid,cells in parts.items():
        by_index={tuple(c['cell_index']):c for c in cells}
        for c in cells:
            ix,iy=c['cell_index']
            for axis,neighbor in ((0,(ix+1,iy)),(1,(ix,iy+1))):
                b=by_index.get(neighbor)
                if b is None:continue
                v={'id':f"VC_{c['id']}_{axis}",'a':c['id'],'b':b['id'],'face':'RIGHT' if axis==0 else 'REAR',
                   'width_m':c['size_m'][1-axis],'bottom_m':0,'top_m':c['size_m'][2],'offset_m':0,
                   'schedule':[[0,1]],'kind':'cell_boundary','virtual_cell_boundary':True}
                r=original[rid]
                if 'cad_bounds_m' in r:
                    # CAD vents and synthetic solver boxes are different frames.
                    # Map the virtual boundary back through the original box's
                    # declared affine CAD map before measuring passage distances.
                    p=[c['origin_m'][j]+c['size_m'][j]/2 for j in range(3)]
                    p[axis]=c['origin_m'][axis]+c['size_m'][axis]
                    x0,y0,x1,y1=r['cad_bounds_m']
                    p[0]=x0+(p[0]-r['origin_m'][0])/r['size_m'][0]*(x1-x0)
                    p[1]=y0+(p[1]-r['origin_m'][1])/r['size_m'][1]*(y1-y0)
                    v['cad_geometry']={'center_m':p,'tangent':[0,1,0] if axis==0 else [1,0,0],
                        'normal_a_to_b':[1,0,0] if axis==0 else [0,1,0]}
                    v['graph_position_basis']='inverse affine CAD bounds map; virtual boundary, not a detected physical door'
                openings.append(v);virtual.append(v['id'])
    m['rooms']=rooms;m['fuel_groups']=groups;m['openings']=sorted(openings,key=lambda v:v.get('type')=='FLOOR')
    m.pop('explicit_candidates',None)
    assert math.isclose(sum(g['energy_MJ'] for g in groups),sum(g['energy_MJ'] for g in model['fuel_groups']),rel_tol=1e-10)
    return m,{'partitions':manifest,'opening_map':maps,'virtual_openings':virtual,'initial_budget_policy':budget_notes,
              'geometry_basis':'partition existing rectangular native boxes; preserve native vent spans, CAD center assigns receiving cell; virtual centers inverse-affine mapped to CAD for graph distances; not reconstructed polygon CFD',
              'total_energy_MJ_before':sum(g['energy_MJ'] for g in model['fuel_groups']),'total_energy_MJ_after':sum(g['energy_MJ'] for g in groups)}
