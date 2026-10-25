"""Uniform CAD fuel sampling, with one shared finite room budget.

Cubes are area/budget symbols, not measured furniture or independent native fires.
Each point can be an ignition candidate; the first accepted point locates the
room's prescribed fire. Additional cubes never add fuel to that shared budget.
"""
from copy import deepcopy
import math


def layout(room, anchors=(), spacing_m=4., max_cells=64):
    from shapely.geometry import Point, box
    from .cad import footprint
    shape=footprint(room['cad_polys']); x0,y0,x1,y1=shape.bounds
    if shape.area<=.01:return []
    spacing=max(spacing_m,math.sqrt(shape.area/max_cells))
    while True:
        cells=[]
        for ix in range(math.ceil((x1-x0)/spacing)):
            for iy in range(math.ceil((y1-y0)/spacing)):
                cut=shape.intersection(box(x0+ix*spacing,y0+iy*spacing,x0+(ix+1)*spacing,y0+(iy+1)*spacing))
                if cut.area<.01:continue
                inner=cut.buffer(-.32)
                if inner.is_empty:inner=cut
                p=inner.representative_point()
                cells.append({'shape':cut,'points':[(p,None)]})
        if len(cells)<=max_cells or spacing>max(x1-x0,y1-y0):break
        spacing*=1.1
    for anchor in anchors:
        p=Point(anchor['xyz'][:2])
        if not shape.contains(p):continue
        cell=min(cells,key=lambda c:c['shape'].distance(p))
        nearest=min((p.distance(q) for q,_ in cell['points']),default=math.inf)
        if nearest<.7:
            # The opening/ignition location replaces a nearby representative.
            j=min(range(len(cell['points'])),key=lambda j:p.distance(cell['points'][j][0]))
            cell['points'][j]=(p,anchor)
        else:cell['points'].append((p,anchor))
    units=[]
    total=sum(c['shape'].area for c in cells)
    for cell in cells:
        for p,anchor in cell['points']:
            edge=.6
            while edge>.04 and not shape.covers(box(p.x-edge/2,p.y-edge/2,p.x+edge/2,p.y+edge/2)):edge*=.8
            if edge<=.04:continue
            units.append({'id':f"U_{room['key']}_{len(units)+1}", 'cad_key':room['key'],
                'position_m':[p.x,p.y,room['z_m']], 'edge_m':edge,
                'area_share_m2':cell['shape'].area/len(cell['points']),
                'budget_fraction':cell['shape'].area/len(cell['points'])/total,
                'opening_id':anchor.get('opening_id') if anchor else None,
                'anchor':deepcopy(anchor), 'placement':'uniform_clipped_grid_with_inside_opening_anchors'})
    weight=sum(u['budget_fraction'] for u in units)
    if not weight:return []
    for u in units:u['budget_fraction']/=weight
    return units


def apply(model):
    """Replace candidate-only doorway placement with shared-budget uniform samples."""
    from .cad import native_point
    old=model['explicit_candidates']; candidates=[]; rooms={r['id']:r for r in model['rooms']}
    displayed={r['key']:r for r in model['cad']['display_rooms']}
    units=[]
    for group in model['fuel_groups']:
        room=displayed[group['cad_key']]; solver=rooms[group['room']]
        faces=[c for c in old if c['group']==group['id']]
        anchors=[c for c in faces if c.get('distance_from_opening_m',0)<=.61]
        if 'initial_time_s' in group:anchors.append({'xyz':group['position_m'],'initial':True})
        local=layout(room,anchors)
        if not local:
            candidates.extend(deepcopy(faces))
            model['cad']['warnings'].append('안전한 연료 큐브 배치 불가: '+room['key']+' · 기존 판정 표본 유지')
            continue
        for u in local:
            u.update(group=group['id'],energy_MJ=group['energy_MJ']*u['budget_fraction'])
            u.pop('anchor',None)
        group['fuel_units']=local;units.extend(local)
        if 'initial_time_s' in group:continue
        mat=deepcopy(faces[0]['material'])
        for u in local:
            xyz=[*u['position_m'][:2],room['z_m']+u['edge_m']]
            anchor=next((c for c in faces if c.get('opening_id')==u['opening_id']),None) if u['opening_id'] else None
            c={'id':f"C_U{len(candidates)+1}", 'label':'uniform_fuel_unit_face','group':group['id'],
               'room':group['room'],'cad_key':group['cad_key'],'unit_id':u['id'],'xyz':xyz,
               'solver_xyz':native_point(solver,xyz),'normal':[0,0,1],'solver_normal':[0,0,1],
               'material':deepcopy(mat),'shared_budget_group':group['id'],
               'fuel_face_height_m':u['edge_m'],
               'placement_basis':'uniform CAD grid; clipped cube fully inside room; shared finite room inventory'}
            base=model['cad']['options'].get('fuel_source_base_m')
            if base is not None:
                if not 0<=base<room['height_m']-.1:raise ValueError('Fuel source base is outside the room')
                c['fire_source_xyz']=[*xyz[:2],room['z_m']+base]
                c['solver_fire_xyz']=native_point(solver,c['fire_source_xyz'])
                c['fire_source_base_m']=base
            if anchor:
                for k in ('normal','solver_normal','opening_id','source_cad_key','distance_from_opening_m'):
                    c[k]=deepcopy(anchor[k])
            candidates.append(c)
    model['explicit_candidates']=candidates
    model['cad']['candidate_basis']='uniform fuel cells plus inside opening anchors; first crossing activates shared room source'
    model['cad']['fuel_layout']={'version':1,'spacing_m':4,'max_grid_cells_per_room':64,
        'unit_count':len(units),'basis':'area-weighted shared room budget, not independent native FIRE objects'}
    model['cad']['warnings'].append('균등 연료 기호는 실 전체 연료 예산을 면적으로 나눈 대표 표본이다. 첫 착화 표본이 실 대표 화원 위치를 정하며 각 기호가 독립 발열하는 모델은 아니다.')
    return model


def present(payload):
    """Add honest fuel layout to old results; never change their events/HRR."""
    if payload.get('fuel_units'):return payload
    d=deepcopy(payload);units=[]
    for group in d.get('solid_groups',[]):
        room=next((r for r in d['rooms'] if r['key']==group['cad_key']),None)
        if room is None:continue
        anchors=[c for c in d.get('solid_candidates',[]) if c['group']==group['id'] and c.get('distance_from_opening_m',0)<=.61]
        anchors += [{'xyz':f['position_m']} for f in d['fires'] if f['cad_key']==room['key']]
        for u in layout(room,anchors):
            u.pop('anchor',None);u.update(group=group['id'],energy_MJ=group['energy_MJ']*u['budget_fraction'])
            units.append(u)
    d['fuel_units']=units
    d['fuel_layout_notice']='균등 연료 기호: 저장된 실별 연료량을 나눠 표시. 이 저장 결과는 새 균등 위치로 착화를 재계산한 결과가 아닙니다.'
    return d
