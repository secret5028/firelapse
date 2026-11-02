"""Opt-in polygon partition of the initial room; no combustion/solver changes."""
from copy import deepcopy
from functools import partial
import hashlib
import json
import math
from shapely.geometry import Polygon, Point, box
from shapely.ops import unary_union
from pyrocast_cfbt.rule_cells import partition as legacy_partition
from pyrocast_cfbt.deck import fire_curve


def settings(raw):
    value = {'cell_mode': raw.get('cell_mode', 'legacy'),
             'radial_r1_m': raw.get('radial_r1_m', 6.),
             'radial_r2_m': raw.get('radial_r2_m', 12.)}
    if value['cell_mode'] not in ('legacy', 'radial', 'radial_area'):
        raise ValueError('cell_mode must be legacy, radial or radial_area')
    if value['cell_mode']=='radial_area':
        return dict(cell_mode='radial_area',radial_area_basis='legacy_initial_cad_polygon')
    a, b = value['radial_r1_m'], value['radial_r2_m']
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in (a,b)) or not 0 < a < b:
        raise ValueError('Expected 0 < radial_r1_m < radial_r2_m')
    return value


def cache_key(raw, parameters, engine_sha256, resolved_geometry=None):
    """Canonical settings are explicit even when defaults were omitted."""
    data = deepcopy(raw)
    data.update(settings(raw))
    identity=[data, parameters, engine_sha256]
    if resolved_geometry is not None:identity.append(resolved_geometry)
    return hashlib.sha256(json.dumps(identity, sort_keys=True,
                                   ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def polygons(shape):
    parts = list(shape.geoms) if hasattr(shape, 'geoms') else [shape]
    return [dict(o=list(p.exterior.coords), h=[list(r.coords) for r in p.interiors])
            for p in parts if p.geom_type == 'Polygon' and p.area > 1e-9]


def circle(xy, radius):
    return Polygon([(xy[0]+radius*math.cos(i*math.tau/24), xy[1]+radius*math.sin(i*math.tau/24)) for i in range(24)])


def radius_for_area(shape, xy, target):
    """Deterministic geometric bisection only; no thermal/result feedback."""
    if not 0 < target <= shape.area+1e-8:raise ValueError('Invalid radial target area')
    xmin,ymin,xmax,ymax=shape.bounds
    hi=max(math.hypot(x-xy[0],y-xy[1]) for x in (xmin,xmax) for y in (ymin,ymax))/math.cos(math.pi/24)+1e-6
    lo=0.
    for _ in range(60):
        mid=(lo+hi)/2
        if shape.intersection(circle(xy,mid)).area < target:lo=mid
        else:hi=mid
    return hi


def legacy_cad_area(shape, original, cell):
    bounds=shape.bounds
    project=lambda xy:[bounds[k]+(xy[k]-original['origin_m'][k])/original['size_m'][k]*(bounds[k+2]-bounds[k]) for k in (0,1)]
    lo=project(cell['origin_m']);hi=project([cell['origin_m'][k]+cell['size_m'][k] for k in (0,1)])
    return shape.intersection(box(*lo,*hi)).area


def split_shape(shape, xy, r1, r2):
    c1, c2 = circle(xy,r1), circle(xy,r2)
    inner, middle, outer = shape.intersection(c1), shape.intersection(c2).difference(c1), shape.difference(c2)
    if outer.area < 20:
        middle = middle.union(outer); outer = Polygon()
    if middle.area < 20:
        inner = inner.union(middle); middle = Polygon()
    return [(name, s) for name,s in [('fire',inner),('middle',middle),('outer',outer)] if s.area > 1e-8]


def partition(model, split_initial=False, *, config):
    m, manifest = legacy_partition(model, split_initial=split_initial)
    initial = [g for g in model['fuel_groups'] if 'initial_time_s' in g]
    if len(initial) != 1 or not split_initial:
        raise ValueError('Radial partition requires one initial source and shared fuel allocation')
    source = initial[0]; rid = source['room']
    room = next(r for r in model['rooms'] if r['id'] == rid)
    w,d,h = room['size_m']
    if w*d <= 150 and max(w,d)/min(w,d) <= 3:
        manifest['radial'] = dict(config, applied=False, reason='initial room below split thresholds')
        return m, manifest
    if not room.get('cad_polys'):
        raise ValueError('Radial mode requires actual room polygons, not a fabricated rectangle')
    shape = unary_union([Polygon(p['o'],p.get('h',[])) for p in room['cad_polys']])
    if not shape.is_valid or not math.isclose(shape.area,w*d,rel_tol=1e-6):
        raise ValueError('Radial room polygon must be valid and match input floor area')
    xy = source['position_m'][:2]
    if not shape.covers(Point(xy)):
        raise ValueError('Initial CAD fire position is outside room polygon')
    config=deepcopy(config)
    if config['cell_mode']=='radial_area':
        initial_cell=next(g['room'] for g in m['fuel_groups'] if 'initial_time_s' in g)
        old_cell=next(r for r in m['rooms'] if r['id']==initial_cell)
        target=legacy_cad_area(shape,room,old_cell)
        config.update(radial_target_area_m2=target,legacy_initial_cell=initial_cell,
                      legacy_solver_area_m2=math.prod(old_cell['size_m'][:2]),
                      radial_r1_m=radius_for_area(shape,xy,target),
                      radial_r2_m=radius_for_area(shape,xy,min(2*target,shape.area)),
                      bisection_iterations=60,area_before_small_zone_merge=True)
    pieces = split_shape(shape,xy,config['radial_r1_m'],config['radial_r2_m'])
    old = {r['id'] for r in m['rooms'] if r.get('parent_room') == rid}
    cells=[]; shapes={}; groups=[]
    for i,(zone,s) in enumerate(pieces):
        point = Point(xy) if zone == 'fire' else s.centroid
        if not s.contains(point): point=s.representative_point()
        cx,cy=point.x,point.y; side=math.sqrt(s.area)
        c=deepcopy(room)
        # Area-equivalent proxy is used only by the shared input compiler.
        # The lite model/playback use the real polygon area and perimeter.
        c.update(id=f'{rid}_RAD{i}',parent_room=rid,cell_index=[i,0],radial_zone=zone,
                 origin_m=[cx-side/2,cy-side/2,room['origin_m'][2]],size_m=[side,side,h],
                 radial_polys=polygons(s),radial_area_m2=s.area,radial_perimeter_m=s.length,
                 radial_center_m=[cx,cy])
        cells.append(c);shapes[c['id']]=s
    for g in model['fuel_groups']:
        if g['room'] != rid: continue
        for c in cells:
            share=c['radial_area_m2']/shape.area;ng=deepcopy(g)
            pos=[*c['radial_center_m'],c['origin_m'][2]]
            ng.update(id=g['id'] if c['radial_zone']=='fire' else g['id']+'_'+c['id'].split('_')[-1],
                      room=c['id'],energy_MJ=g['energy_MJ']*share,peak_kW=g['peak_kW']*share,
                      fuel_area_m2=g.get('fuel_area_m2',shape.area*.5)*share,
                      position_m=pos,solver_position_m=pos,radial_position_m=pos)
            for key in ('fuel_units','room_rule_curve','room_rule_trigger','room_vent_cap'):ng.pop(key,None)
            if 'initial_time_s' in g and c['radial_zone']=='fire':
                t,q,a=fire_curve(g,shape.area)
                ng['room_rule_curve']=dict(t=list(t),q=[float(v)*share for v in q],area=[float(v)*share for v in a],
                    energy_MJ=ng['energy_MJ'],initial_curve_preserved=False,shape_preserved=True,area_fraction=share)
            else:ng.pop('initial_time_s',None)
            groups.append(ng)
    original_vents={v['id']:v for v in model['openings']}
    def assign(v):
        p=v.get('cad_geometry',{}).get('center_m')
        if p is None: raise ValueError('Radial opening requires a CAD centre: '+v['id'])
        pt=Point(p[:2])
        return min(cells,key=lambda c:(shapes[c['id']].distance(pt),c['id']))['id']
    openings=[]; remapped={}; assignments=[]
    for v in m['openings']:
        if not ({v['a'],v['b']}&old):openings.append(v);continue
        if v.get('virtual_cell_boundary'):continue
        nv=deepcopy(v);parent=nv.get('parent_opening',nv['id']);original=original_vents[parent]
        new=assign(original)
        for endpoint in ('a','b'):
            if nv[endpoint] in old:nv[endpoint]=new
        key=(parent,nv['a'],nv['b'])
        if key in remapped:remapped[key]['width_m']+=nv['width_m']
        else:remapped[key]=nv
        assignments.append(dict(opening=v['id'],cell=new,centre=original['cad_geometry']['center_m']))
    if config['cell_mode']=='radial_area':
        by_id={c['id']:c for c in cells}
        for v in remapped.values():
            if v['a'] in by_id:
                # Only the compiler's rectangular proxy target coordinate.
                # CAD aperture position/width and lite flow geometry stay intact.
                c=by_id[v['a']];axis=0 if v['face'] in ('FRONT','REAR') else 1
                v['offset_m']=(c['size_m'][axis]-v['width_m'])/2
                v['proxy_position_basis']='centred on area-equivalent box; actual CAD centre retained'
    openings.extend(remapped.values());virtual=[]
    for i,a in enumerate(cells):
        for b in cells[i+1:]:
            edge=shapes[a['id']].boundary.intersection(shapes[b['id']].boundary)
            if edge.length < 1e-7:continue
            p=edge.interpolate(.5,normalized=True)
            v=dict(id='VR_'+a['id']+'_'+b['id'].split('_')[-1],a=a['id'],b=b['id'],face='RIGHT',
                   width_m=edge.length,bottom_m=0,top_m=h,offset_m=0,schedule=[[0,1]],
                   kind='cell_boundary',virtual_cell_boundary=True,
                   cad_geometry=dict(center_m=[p.x,p.y,a['origin_m'][2]+h/2],tangent=[0,1,0],normal_a_to_b=[1,0,0]))
            openings.append(v);virtual.append(v['id'])
    m['rooms']=[r for r in m['rooms'] if r['id'] not in old]+cells
    m['fuel_groups']=[g for g in m['fuel_groups'] if g['room'] not in old]+groups
    m['openings']=sorted(openings,key=lambda v:v.get('type')=='FLOOR')
    manifest['partitions']=[p for p in manifest['partitions'] if p['room']!=rid]+[
        dict(room=rid,mode=config['cell_mode'],cells=[c['id'] for c in cells],native_volume_preserved=True)]
    manifest['virtual_openings']=[v['id'] for v in openings if v.get('virtual_cell_boundary')]
    manifest['opening_map']=[dict(opening=v['id'],parts=[x['id'] for x in openings if x.get('parent_opening',x['id'])==v['id']],area_preserved=True) for v in model['openings']]
    manifest['initial_budget_policy']=[dict(group=source['id'],assigned_cell=cells[0]['id'],
        policy='radial actual polygon area shares; initial shape preserved, standby independent fuel budgets',area_fraction=cells[0]['radial_area_m2']/shape.area)]
    manifest['radial']=dict(config,applied=True,room=rid,fire_position_m=xy,circle_vertices=24,
        cells=[dict(id=c['id'],zone=c['radial_zone'],area_m2=c['radial_area_m2'],perimeter_m=c['radial_perimeter_m'],center_m=c['radial_center_m']) for c in cells],
        openings=assignments,virtual_openings=virtual,
        limits=['centroid if inside; otherwise interior representative point; fire cell centre is fire position',
                'physical openings assigned by CAD centre, whole aperture kept; crossing-aperture distribution is unresolved',
                'disconnected pieces in one annulus share one zone state',
                'full polygon perimeter uses existing wall/leakage model, including virtual interfaces; no new wall-loss model'])
    assert math.isclose(sum(g['energy_MJ'] for g in m['fuel_groups']),sum(g['energy_MJ'] for g in model['fuel_groups']),rel_tol=1e-10)
    manifest['total_energy_MJ_after']=sum(g['energy_MJ'] for g in m['fuel_groups'])
    return m,manifest


def partitioner(raw):
    config=settings(raw)
    return partial(partition,config=config) if config['cell_mode']!='legacy' else None
