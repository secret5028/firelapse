"""Declared equivalent building/duct paths; not measured leakage or fan flow."""
import math
from .physics_config import defaults
from .basement_pressure import configure, below_grade

BOUNDARY_REVISION = 'basement_volume_boundary_v4'
AREA_KEYS = ('stair_area_m2', 'elevator_area_m2', 'fallback_area_m2')
NOTE_PREFIXES = ('최소 누기 가정 적용:', '지하 압력 간략식:', '지하 환기 경로 가정:')


def remove_assumed_leaks(model):
    """Before sampling/ranking real openings; regenerate for each chosen scenario."""
    model['openings']=[v for v in model.get('openings',[]) if not v.get('minimum_leakage')]
    for key in ('minimum_leakage', 'basement_pressure', 'below_grade_ventilation'):
        model.pop(key,None)
    model['limits']=[s for s in model.get('limits',[]) if not s.startswith(NOTE_PREFIXES)]
    return model


def parking(room, model):
    parent=room.get('parent_room',room['id'])
    use=model.get('approved_input',{}).get('room_uses',{}).get(parent,{})
    return room.get('usage_class',use.get('usage_class')) == 'parking'


def spread_area(area, candidates, settings):
    """Place an aggregate area on distinct rooms without exceeding FRONT width."""
    left=area;allocations=[]
    for room in candidates:
        height=min(settings['height_m'],room['size_m'][2])
        portion=min(left,room['size_m'][0]*height)
        if portion>0:allocations.append((room,portion,height))
        left-=portion
        if left<=1e-10:break
    if left>1e-10:raise ValueError('Equivalent leakage exceeds connected-room wall capacity')
    return allocations


def apply_minimum_leakage(model):
    model['boundary_revision'] = BOUNDARY_REVISION
    patch=model.get('leakage_defaults',{})
    settings = {**defaults('leakage'), **patch}
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<=0
           for k,v in settings.items() if k!='basis'):
        raise ValueError('Minimum leakage dimensions must be finite positive values')
    if not isinstance(settings.get('basis',''),str):raise ValueError('Leakage basis must be text')
    # The existing UI encodes leakage_area_m2 as these three equal overrides.
    # Retain that intent across repeated normalization, including a value of .02.
    explicit=model.get('minimum_leakage_user_area_m2',model.get('leakage_area_m2'))
    if explicit is None and all(k in patch for k in AREA_KEYS) and 'height_m' not in patch:
        if len({patch[k] for k in AREA_KEYS})==1:explicit=patch[AREA_KEYS[0]]
    if explicit is not None:
        if type(explicit) not in (int,float) or not math.isfinite(explicit) or explicit<=0:
            raise ValueError('User leakage area must be finite positive')
        model['minimum_leakage_user_area_m2']=explicit
        settings.update({k:explicit for k in AREA_KEYS})
    model['leakage_defaults'] = settings
    rooms = {r['id']: r for r in model['rooms']}
    warnings = model.setdefault('warnings', [])
    for r in rooms.values():
        if below_grade(r,model):
            r.setdefault('leak_area_ratio', [0., 0.])
            note = '지하 판정: '+r['id']+' (below_grade 또는 지반 대비 표고)'
            if note not in warnings: warnings.append(note)
    openings = [v for v in model.get('openings', []) if not v.get('minimum_leakage')]
    graph = {k: set() for k in [*rooms, 'OUTSIDE']}
    def link(a, b):
        if a in graph and b in graph: graph[a].add(b); graph[b].add(a)
    for v in openings:
        # A closing door or stopping fan is not a permanent passive ambient path.
        if min(row[1] for row in v.get('schedule', [[0, 1]])) > 0:link(v['a'],v['b'])
    for r in rooms.values():
        if any(x > 0 for x in r.get('leak_area_ratio', [.00017, .000052])):link(r['id'],'OUTSIDE')
    assumptions=[];volume_paths=[];visited=set()
    origins=[g['room'] for g in model['fuel_groups'] if 'initial_time_s' in g]
    for origin in origins:
        if origin in visited:continue
        component,pending=set(),[origin]
        while pending:
            rid=pending.pop()
            if rid in component:continue
            component.add(rid);pending.extend(graph[rid]-component)
        visited.update(component)
        if 'OUTSIDE' in component:continue
        members=[rooms[r] for r in sorted(component)]
        cores=[r for r in members if r.get('core_kind') in ('stair','stairs','stairwell','elevator','elev','lift')]
        candidates=cores or [max(members,key=lambda r:r['size_m'][0]*r['size_m'][1])]
        legacy=[]
        for room in candidates:
            key='elevator_area_m2' if room.get('core_kind') in ('elevator','elev','lift') else 'stair_area_m2' if cores else 'fallback_area_m2'
            legacy.append((room,settings[key],min(settings['height_m'],room['size_m'][2])))
        below=[r for r in members if below_grade(r,model)]
        basis='aggregate closed-door path through omitted building to ambient; not measured'
        allocations=legacy
        if below:
            if explicit is None:
                volume=sum(math.prod(r['size_m']) for r in below if not parking(r,model))
                area=sum(math.prod(r['size_m'][:2]) for r in members if parking(r,model))
                equivalent=(settings['below_grade_ach']*volume+settings['parking_m3_h_m2']*area)/(3600*settings['duct_velocity_m_s'])
                target=max(sum(a for _,a,_ in legacy),equivalent)
                basis=settings['basis']
                record=dict(rooms=sorted(component),general_below_volume_m3=volume,parking_area_m2=area,
                            calculated_area_m2=equivalent,area_m2=target,below_grade_ach=settings['below_grade_ach'],
                            parking_m3_h_m2=settings['parking_m3_h_m2'],duct_velocity_m_s=settings['duct_velocity_m_s'],basis=basis)
                volume_paths.append(record)
                # Keep the exceptional pressure guard attached to a below-grade vent.
                preferred=[r for r in candidates if below_grade(r,model)]
                preferred += sorted((r for r in below if r not in preferred),key=lambda r:(-math.prod(r['size_m'][:2]),r['id']))
                preferred += [r for r in members if r not in preferred]
                allocations=spread_area(target,preferred,settings)
            elif any(a/h>r['size_m'][0] for r,a,h in legacy):
                preferred=candidates+[r for r in members if r not in candidates]
                allocations=spread_area(sum(a for _,a,_ in legacy),preferred,settings)
        for room,area,height in allocations:
            if area/height>room['size_m'][0]+1e-12:raise ValueError('Leak opening exceeds room width')
            vent=dict(id='MINLEAK_'+room['id'],a=room['id'],b='OUTSIDE',type='WALL',
                      face='FRONT',offset_m=0.,bottom_m=0.,top_m=height,width_m=min(area/height,room['size_m'][0]),
                      schedule=[[0.,1.]],minimum_leakage=True,basis=basis)
            openings.insert(0,vent);assumptions.append(dict(room=room['id'],area_m2=area,basis=basis))
    model['openings']=openings;model['minimum_leakage']=assumptions
    model['below_grade_ventilation']=volume_paths
    model['limits']=[s for s in model.get('limits',[]) if not s.startswith(NOTE_PREFIXES)]
    if assumptions and not volume_paths:
        model['limits'].append('최소 누기 가정 적용: '+', '.join(a['room'] for a in assumptions)+f", 총 {sum(a['area_m2'] for a in assumptions):g} m² (건물 나머지 경로의 등가 가정)")
    for row in volume_paths:
        model['limits'].append(f"지하 환기 경로 가정: 체적 비례 등가 면적 {row['area_m2']:.6g} m² (환기 {row['below_grade_ach']:g}회/h, 풍속 {row['duct_velocity_m_s']:g} m/s) · 주차장 {row['parking_m3_h_m2']:g} m³/㎡·h · 실측 아님")
    configure(model)
    # Initial configuration alone is not a pressure-sizing rerun.
    if not model.get('basement_pressure',{}).get('history'):
        model['limits']=[s for s in model['limits'] if not s.startswith('지하 압력 간략식:')]
