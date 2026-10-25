"""CAD topology adapter. Physical CAD geometry and equivalent solver geometry stay separate."""
from collections import defaultdict, deque
from copy import deepcopy
import hashlib
import json
import math
import re
from pathlib import Path
import sys
from .practical import apply_profile, room_defaults, wall_default, execution_limits


def cad_key(floor, item):
    label='CAD_'+str(floor)+'_'+str(item)
    return label if re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,35}',label) else 'CAD_'+hashlib.sha256(label.encode('utf-8')).hexdigest()[:24]


def dedicated_core_kind(room):
    """Dedicated room evidence only; an elevator hall is not an elevator shaft."""
    tags=set(room.get('tags',[]));names=[s for s in room.get('names',[]) if s and s not in ('갑','화','-')]
    text=' '.join(names).lower();dedicated_label=len(names)<=3
    if 'stair_inside' in tags or dedicated_label and '계단실' in text:return 'stair'
    if tags & {'elev','elev_inside'} or dedicated_label and '승강로' in text:return 'elev'
    return None


def resolve_building(project, requested=None):
    """Accept an extracted building, output directory, or an existing project."""
    root=Path(project).resolve()
    if requested:
        path=Path(requested).resolve()
        if not path.is_file():raise ValueError('building.json not found: '+str(path))
        return path
    if root.is_file():return root
    for path in (root/'building.json',root/'cad-output/building.json'):
        if path.is_file():return path
    choices=sorted(root.glob('work/cad-ui-test-data/*/cad-output/building.json'))
    if len(choices)==1:return choices[0]
    if not choices:raise ValueError('추출된 building.json이 없습니다. 도면 구획·개구부 추출을 먼저 실행하세요.')
    raise ValueError('건물 결과가 여러 개입니다. --building으로 사용할 building.json을 지정하세요.')


def geometry_dependencies(project):
    try:
        import shapely
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'deps'))
        sys.path.insert(0, str(Path(project) / 'work' / 'cad-deps'))
        try:
            import shapely
        except ImportError as exc:
            raise ValueError('Shapely가 필요합니다. simulation/requirements.txt를 simulation/deps에 설치하세요.') from exc


def footprint(polys):
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    return unary_union([Polygon(p['o'], p.get('h', [])).buffer(0) for p in polys])


def polygon_data(geom):
    parts = [geom] if geom.geom_type == 'Polygon' else list(geom.geoms)
    return [{'o': list(g.exterior.coords)[:-1],
             'h': [list(h.coords)[:-1] for h in g.interiors]}
            for g in parts if g.geom_type == 'Polygon' and g.area > .001]


def native_point(room, xyz):
    """An explicit, auditable affine map; CAD points are never native box coordinates."""
    x0, y0, x1, y1 = room['cad_bounds_m']
    ox, oy, oz = room['origin_m']
    w, d, h = room['size_m']
    return [ox + min(w-.05, max(.05, (xyz[0]-x0)/(x1-x0)*w)),
            oy + min(d-.05, max(.05, (xyz[1]-y0)/(y1-y0)*d)),
            oz + min(h-.02, max(.02, xyz[2]-oz))]


def opening_geometry(raw, a, b, rooms):
    import numpy as np
    rings = raw.get('polys', [])
    points = np.array([p for ring in rings for p in ring], float)
    if not len(points):
        raise ValueError('Opening has no CAD geometry: '+raw['id'])
    center = (points.min(axis=0)+points.max(axis=0))/2
    centered = points-center
    _, _, axes = np.linalg.svd(centered, full_matrices=False)
    tangent = axes[0]
    normal = np.array([-tangent[1], tangent[0]])
    # Use polygon sidedness near the opening, rather than a possibly concave room centroid.
    from shapely.geometry import Point
    shape = footprint(rooms[a]['cad_polys'])
    plus = sum(shape.covers(Point(*(center+normal*s))) for s in (.2,.4,.7,1.0))
    minus = sum(shape.covers(Point(*(center-normal*s))) for s in (.2,.4,.7,1.0))
    if plus > minus:
        normal *= -1
    elif plus == minus and (center-np.array(rooms[a]['cad_center_m'])) @ normal < 0:
        normal *= -1
    return {'center_m': [float(center[0]),float(center[1]),rooms[a]['origin_m'][2]],
            'tangent': [float(tangent[0]),float(tangent[1]),0.],
            'normal_a_to_b': [float(normal[0]),float(normal[1]),0.],
            'basis': 'CAD aperture major axis; room polygon sidedness'}


def opening_candidates(room, solver, group, material, openings, offsets=(.6,1.5), height=.76):
    """A small set of assumed fuel faces on the receiving side of actual CAD apertures."""
    from shapely.geometry import Point, LineString
    shape=footprint(room['cad_polys']); output=[]
    for opening in openings:
        a=opening.get('cad_a',opening['a']); b=opening.get('cad_b',opening['b'])
        if room['id'] not in (a,b) or 'OUTSIDE' in (a,b):continue
        if opening.get('type')=='FLOOR' or not any(f>0 for _,f in opening.get('schedule',[[0,1]])):continue
        frame=opening['cad_geometry']; center=frame['center_m']; normal=frame['normal_a_to_b']
        sign=-1 if room['id']==a else 1
        inward=[sign*normal[0],sign*normal[1]]
        for distance in offsets:
            xy=[center[i]+distance*inward[i] for i in range(2)]
            path=LineString([center[:2],xy])
            if not shape.contains(Point(xy)) or path.intersection(shape).length<distance-.35:continue
            z=min(height,room['height_m']-.1); xyz=[*xy,room['z_m']+z]
            facing=[-inward[0],-inward[1],0.]
            x0,y0,x1,y1=solver['cad_bounds_m']; w,d,_=solver['size_m']
            mapped=[facing[0]/(w/(x1-x0)),facing[1]/(d/(y1-y0)),0.]
            length=math.hypot(*mapped[:2]); mapped=[n/length for n in mapped]
            output.append({'id':f'C_{len(output)+1}','label':'opening_receiver_fuel_face',
                'group':group['id'],'room':solver['id'],'cad_key':room['id'],
                'xyz':xyz,'solver_xyz':native_point(solver,xyz),'normal':facing,'solver_normal':mapped,
                'material':deepcopy(material),'opening_id':opening['id'],
                'source_cad_key':b if room['id']==a else a,'distance_from_opening_m':distance,
                'fuel_face_height_m':z,'placement_basis':'assumed fuel face inside receiving CAD polygon; faces aperture; not surveyed furniture',
                'shared_budget_group':group['id']})
    return output


def adapt(project, options=None):
    project = Path(project).resolve(); options = options or {}
    geometry_dependencies(project)
    from shapely.geometry import Point
    source = resolve_building(project,options.get('building_path'))
    raw = source.read_bytes(); building = json.loads(raw)
    from .topology import corrected_building,vertical_selection
    building,topology_changes=corrected_building(building,hashlib.sha256(raw).hexdigest())
    warnings=[]
    warnings.extend(note for f in building['floors'] for note in f.get('classification_notes',[]))
    practical=options.get('profile','practical')=='practical'
    if not building.get('floors'):raise ValueError('도면에서 추출된 층이 없습니다.')
    assumed_z=0.
    for f in building['floors']:
        if 'h' not in f or not f['h']:
            f['h']=3.;warnings.append('층고 미확인 → 3m 가정: '+str(f['name']))
        if 'z' not in f:
            f['z']=assumed_z;warnings.append('층 표고 미확인 → 입력 층 순서로 누적: '+str(f['name']))
        assumed_z=f['z']+f['h']
    floors = {f['name']: f for f in building['floors']}
    fire_floor = options.get('fire_floor', '3F' if '3F' in floors else next(iter(floors)))
    if fire_floor not in floors:raise ValueError('선택한 화점 층이 도면에 없습니다.')
    eligible=[r['id'] for r in floors[fire_floor].get('rooms',[]) if 'outdoor' not in r.get('tags',[])]
    if not eligible:raise ValueError('선택한 층에 계산 가능한 실이 없습니다.')
    fire_room = options.get('fire_room', 'R9' if 'R9' in eligible else eligible[0])
    fire_key = cad_key(fire_floor,fire_room)
    key = cad_key
    rooms = {}; displayed = {}; horizontal = []; vertical = []; excluded = []
    selected_floor = options.get('scope_floor')
    vertical_smoke=bool(selected_floor and options.get('vertical_smoke',False))
    remote=vertical_selection(building,selected_floor) if vertical_smoke else {}
    with_vertical=not selected_floor or vertical_smoke
    for f in building['floors']:
        if selected_floor and f['name'] != selected_floor and not vertical_smoke:
            continue
        for r in f['rooms']:
            if vertical_smoke and f['name']!=selected_floor and r['id'] not in remote.get(f['name'],set()):
                excluded.append({'key':key(f['name'],r['id']),'reason':'remote_floor_non_access_room_not_in_vertical_smoke_scope'});continue
            k = key(f['name'], r['id'])
            if 'outdoor' in r.get('tags', []):
                excluded.append({'key': k, 'reason': 'outdoor'}); continue
            shape = footprint(r.get('polys',[]))
            if shape.is_empty or shape.area<=.4:
                excluded.append({'key':k,'reason':'invalid_or_tiny_footprint'})
                warnings.append('구획 형상 미확인: '+k);continue
            point = shape.representative_point()
            item = {'id': k, 'cad_floor': f['name'], 'cad_room': r['id'],
                    'cad_polys': r['polys'], 'cad_center_m': [point.x, point.y],
                    'area_m2': float(shape.area), 'z_m': f.get('z',0.), 'height_m': f.get('ceil_h') or f.get('h',3.),
                    'structural_height_m': f.get('h',3.), 'core_kind': dedicated_core_kind(r),
                    'cad_names':r.get('names',[]),
                    'fuel_default':room_defaults(r,building)}
            rooms[k] = item
    if fire_key not in rooms:
        raise ValueError('The selected fire room is absent from the requested CAD scope')
    nodes = {(n['floor'],n['core_id']):n for n in building.get('core_nodes',[])}
    # Core identity is independent of whether vertical connections are simulated.
    for n in nodes.values():
        k=key(n['floor'],n.get('room_id'))
        if n.get('room_id') and k in rooms:rooms[k]['core_kind']=n['kind']
    from .ceiling import apply_clear_heights
    apply_clear_heights(project,building,rooms,warnings)
    for r in rooms.values():
        if r['core_kind']:
            r['height_m']=r['structural_height_m']
            r['fuel_default']={'usage':'circulation_core','load_MJ_m2':10.,'occupancy_fraction':.01,
                'hrrpua_kW_m2':100.,'basis':'project_low_core_fuel_proxy; no_automatic_secondary_solid_inventory'}
    if selected_floor and not vertical_smoke and any(r['core_kind'] for r in rooms.values()):
        warnings.append('단일 층의 계단·승강로도 코어로 식별. 위아래 층 연결은 계산하지 않는 닫힌 경계 근사.')
    core_keys = {}
    if with_vertical:
        used = {(c[d+'_floor'],c[d+'_core']) for c in building.get('vertical_connections',[]) for d in ('from','to')}
        for nk in sorted(used):
            if nk not in nodes:
                warnings.append('수직 연결 노드 누락: '+str(nk));continue
            n=nodes[nk]; fn,cid=nk
            if n['room_id']:
                k=key(fn,n['room_id'])
                if k not in rooms: continue
            else:
                if n['association'] != 'contained_core_in_room':
                    warnings.append('수직 연결 미평가: '+str(nk));continue
                host=key(fn,n['access_room_ids'][0]); transport=next(t for t in floors[fn]['transport'] if t['id']==cid)
                shape=footprint(rooms[host]['cad_polys']); foot=footprint(transport['region']).intersection(shape)
                if foot.area <= 1: raise ValueError('Invalid shared stair footprint')
                remain=shape.difference(foot)
                rooms[host]['cad_polys']=polygon_data(remain); rooms[host]['area_m2']=remain.area
                k=key(fn,'CORE'+cid); p=foot.representative_point()
                rooms[k]={**deepcopy(rooms[host]),'id':k,'cad_room':'CORE'+cid,
                          'cad_polys':polygon_data(foot),'cad_center_m':[p.x,p.y],'area_m2':foot.area}
                # Existing shared staircase access assumption, with an actual footprint contact point.
                contact=foot.boundary.intersection(remain.buffer(.03)).representative_point()
                vector=[p.x-contact.x,p.y-contact.y]; norm=math.hypot(*vector) or 1
                normal=[vector[0]/norm,vector[1]/norm,0]
                horizontal.append({'id':key(fn,'ACCESS'+cid),'a':host,'b':k,'width_m':1.2,'bottom_m':0.,'top_m':2.1,
                    'kind':'stair_access','schedule':[[0,1]],'cad_floor':fn,
                    'cad_geometry':{'center_m':[contact.x,contact.y,rooms[host]['z_m']],
                                    'tangent':[-normal[1],normal[0],0],'normal_a_to_b':normal},
                    'assumed':'shared hall stair access 1.2 m x 2.1 m'})
            rooms[k]['core_kind']=n['kind']; rooms[k]['height_m']=rooms[k]['structural_height_m']; core_keys[nk]=k
            rooms[k].update(clear_height_m=rooms[k]['height_m'],height_basis='dedicated_core_structural_height',
                            height_confidence='structural_proxy',ceiling_tags=[])
        for i,c in enumerate(building.get('vertical_connections',[])):
            lower=core_keys.get((c['from_floor'],c['from_core'])); upper=core_keys.get((c['to_floor'],c['to_core']))
            if not lower or not upper: continue
            a=nodes[(c['from_floor'],c['from_core'])]; b=nodes[(c['to_floor'],c['to_core'])]
            factor=options.get('stair_area_factor',.25) if c['kind']=='stair' else options.get('shaft_area_factor',.8)
            area=min(a['w']*a['h'],b['w']*b['h'],rooms[lower]['area_m2'],rooms[upper]['area_m2'])*factor
            vertical.append({'id':'CAD_V'+str(i),'type':'FLOOR','a':upper,'b':lower,'area_m2':area,
                'kind':c['kind'],'schedule':[[0,1]],'cad_floor':c['from_floor'],
                'cad_geometry':{'center_m':[a['x'],a['y'],rooms[upper]['z_m']],
                    'normal_a_to_b':[0,0,-1],'tangent':[1,0,0]},
                'assumed_area_factor':factor,'evidence':c.get('evidence')})
    for f in building['floors']:
        if selected_floor and f['name'] != selected_floor and not vertical_smoke: continue
        originals={o['id']:o for o in f.get('openings',[])}
        if 'simulation_graph' not in f:warnings.append('개구부 연결망 없음: '+f['name'])
        for conn in f.get('simulation_graph',{}).get('connections',[]):
            aa,bb=conn['sides']; a=key(f['name'],aa) if aa!='out' else 'OUTSIDE'; b=key(f['name'],bb) if bb!='out' else 'OUTSIDE'
            outdoor={r['id'] for r in f['rooms'] if 'outdoor' in r.get('tags',[])}
            if aa in outdoor:a='OUTSIDE'
            if bb in outdoor:b='OUTSIDE'
            if a=='OUTSIDE':a,b=b,a
            if a not in rooms or (b!='OUTSIDE' and b not in rooms) or a==b:continue
            dims=conn['dimensions']; kind=conn['kind']
            fraction=options.get('window_fraction',0.) if 'window' in kind else (options.get('elevator_fraction',.01) if kind=='door_elev' else options.get('door_fraction',1.))
            fraction=options.get('opening_overrides',{}).get(key(f['name'],conn['id']),fraction)
            if kind=='open_passage':fraction=1.0  # No door leaf exists to close.
            horizontal.append({'id':key(f['name'],conn['id']),'a':a,'b':b,'kind':kind,
                'width_m':dims['width_m'],'bottom_m':dims['bottom_m'],'top_m':dims['top_m'],
                'schedule':[[0,fraction]],'cad_floor':f['name'],'cad_opening':conn['id'],
                'topology_correction':conn.get('topology_correction'),
                'raw_geometry':originals.get(conn['id'],{'id':conn['id']})})
    if not selected_floor:
        # Preserve the established ramp-to-exterior approximation.
        for f in building['floors']:
            for ramp in f.get('model_ramps',[]):
                end=[(a+b)/2 for a,b in zip(ramp['inner'][0],ramp['outer'][0])]
                candidates=[(footprint(r['cad_polys']).distance(Point(end)),k) for k,r in rooms.items() if r['cad_floor']==f['name'] and r['area_m2']>100]
                if not candidates:continue
                distance,parking=min(candidates)
                if distance>15:continue
                vertical.append({'id':key(f['name'],'RAMP'),'type':'FLOOR','a':'OUTSIDE','b':parking,
                    'area_m2':ramp['width_m']*3.,'kind':'ramp','schedule':[[0,1]],'cad_floor':f['name'],
                    'cad_geometry':{'center_m':[*end,rooms[parking]['z_m']+rooms[parking]['height_m']],
                        'normal_a_to_b':[0,0,-1],'tangent':[1,0,0]},'assumed':'equivalent outdoor ceiling vent; not resolved sloping flow'})
    # Reachability ignores closed windows; no invented links for unresolved isolated rooms.
    adj=defaultdict(set)
    for v in horizontal+vertical:
        if v['a'] in rooms and v['b'] in rooms and any(f>0 for _,f in v['schedule']):
            adj[v['a']].add(v['b']);adj[v['b']].add(v['a'])
    reachable={fire_key}; queue=deque([fire_key])
    while queue:
        for k in adj[queue.popleft()]-reachable:reachable.add(k);queue.append(k)
    if selected_floor and options.get('full_floor_search',True):
        # Closed doors restrict flow; they must not delete compartments from the floor.
        reachable=set(rooms)
        if len(rooms)>100:
            raise ValueError('선택 층이 CFAST 100구획 상한을 넘습니다. 계산 구획을 명시적으로 나누세요. 자동 절단하지 않습니다.')
    excluded += [{'key':k,'reason':'not connected under this opening scenario'} for k in rooms if k not in reachable]
    rooms={k:r for k,r in rooms.items() if k in reachable}
    horizontal=[v for v in horizontal if v['a'] in rooms and (v['b'] in rooms or v['b']=='OUTSIDE')]
    vertical=[v for v in vertical if (v['a'] in rooms or v['a']=='OUTSIDE') and v['b'] in rooms]
    displayed=deepcopy(rooms); members={k:[k] for k in rooms}; aliases={k:k for k in rooms}
    for opening in horizontal:
        opening['cad_a']=opening['a'];opening['cad_b']=opening['b']
    # The pinned native engine has 100 interior compartments. Keep the fire floor and cores distinct.
    while len(rooms)>100:
        choices=[]
        for v in horizontal:
            a,b=v['a'],v['b']
            if b not in rooms or a==b or v['kind']!='door' or v['schedule']!=[[0,1.]]:continue
            ra,rb=rooms[a],rooms[b]
            if ra['cad_floor']==fire_floor or ra['core_kind'] or rb['core_kind']:continue
            choices.append((ra['area_m2']+rb['area_m2'],a,b))
        if not choices:
            if not practical:raise ValueError('Native 100-room limit: no permissible remote-room merge')
            # Keep a connected BFS prefix. Cut boundary is closed, never invented as fresh air.
            order=[]; todo=deque([fire_key]); seen={fire_key}
            while todo and len(order)<100:
                current=todo.popleft();order.append(current)
                for v in horizontal+vertical:
                    if current not in (v['a'],v['b']):continue
                    other=v['b'] if v['a']==current else v['a']
                    if other in rooms and other not in seen and any(f>0 for _,f in v['schedule']):seen.add(other);todo.append(other)
            keep=set(order)
            excluded.extend({'key':m,'reason':'native_room_limit_closed_cut_boundary'} for k in rooms if k not in keep for m in members[k])
            rooms={k:r for k,r in rooms.items() if k in keep}
            displayed={k:r for k,r in displayed.items() if aliases[k] in keep}
            members={k:v for k,v in members.items() if k in keep}
            horizontal=[v for v in horizontal if v['a'] in keep and (v['b'] in keep or v['b']=='OUTSIDE')]
            vertical=[v for v in vertical if (v['a'] in keep or v['a']=='OUTSIDE') and v['b'] in keep]
            warnings.append('100구획 상한으로 계산 범위 축소. 절단 경계는 닫힘 근사이며 전체 건물 전파는 미평가.')
            break
        _,a,b=min(choices); ra,rb=rooms[a],rooms[b]
        volume=ra['area_m2']*ra['height_m']+rb['area_m2']*rb['height_m']
        ra['area_m2']+=rb['area_m2'];ra['height_m']=volume/ra['area_m2'];ra['cad_polys']+=rb['cad_polys']
        members[a]+=members.pop(b)
        for original in members[a]:aliases[original]=a
        del rooms[b]
        for v in horizontal+vertical:
            if v['a']==b:v['a']=a
            if v['b']==b:v['b']=a
        horizontal=[v for v in horizontal if v['a']!=v['b']]
    for i,(k,r) in enumerate(rooms.items()):
        maxwidth=max([v['width_m']+.2 for v in horizontal if k in (v['a'],v['b'])] or [0.])
        bounds=list(footprint(r['cad_polys']).bounds); x0,y0,x1,y1=bounds
        width=max(maxwidth,math.sqrt(r['area_m2']*(x1-x0)/(y1-y0)))
        depth=r['area_m2']/width
        if depth<=.6: # Preserve area while keeping the native minimum usable depth.
            width=r['area_m2']/.61;depth=.61
            if width<maxwidth:raise ValueError('Opening wider than usable equivalent room: '+k)
        r.update(origin_m=[i*100.,0.,r['z_m']],size_m=[width,depth,r['height_m']],cad_bounds_m=bounds,
                 shaft=bool(r['core_kind']),members=members[k])
    for v in horizontal:
        if 'raw_geometry' in v:
            raw_opening=v.pop('raw_geometry')
            if not raw_opening.get('polys'):
                raise ValueError('개구부 위치가 없어 실간 전이를 계산할 수 없습니다: '+v['id'])
            v['cad_geometry']=opening_geometry(raw_opening,v['a'],v['b'],rooms)
        v.update(face='FRONT',offset_m=(rooms[v['a']]['size_m'][0]-v['width_m'])/2)
        v['top_m']=min(v['top_m'],*[rooms[k]['size_m'][2] for k in (v['a'],v['b']) if k in rooms])
    fuel_source=project/'work/cfast_room_fuels_v35.json'
    legacy=json.loads(fuel_source.read_text('utf-8')) if fuel_source.is_file() and not practical else {'targets':[]}
    targets={key(*t['room_key'].split('_',1)):t for t in legacy['targets']}
    if practical:warnings.append('가연물은 실 용도 문구에 따른 대표 기본값. 실제 가구·적재물 조사값이 아님.')
    groups=[]; plates=[]
    for original,r in displayed.items():
        if vertical_smoke and r['cad_floor']!=selected_floor:continue  # Transport-only remote floors.
        target=targets.get(original)
        if target is None and original!=fire_key and not practical:continue
        if r['core_kind'] and original!=fire_key:continue
        solver=rooms[aliases[original]]; shape=footprint(r['cad_polys']);inner=shape.buffer(-.3)
        if inner.is_empty:inner=shape
        point=inner.representative_point()
        if target and shape.covers(Point(target['position_xy_m'])): point=Point(target['position_xy_m'])
        if not practical and original==fire_key and original=='CAD_3F_R9' and (project/'work/cfast_room_design_v35.json').is_file():
            profile=json.loads((project/'work/cfast_room_design_v35.json').read_text('utf-8'))
            spec=profile['energy_design']['spec']; hoc=profile['heat_of_combustion_kJ_kg']
        elif target:
            spec=target['growth']['energy_design']['spec']; hoc=target['growth']['heat_of_combustion_kJ_kg']
        else:
            defaults=r['fuel_default'];fuel_area=r['area_m2']*defaults['occupancy_fraction']
            spec={'energy_mj':r['area_m2']*defaults['load_MJ_m2'],'alpha_kw_s2':1/90.,'peak_cap_kw':fuel_area*defaults['hrrpua_kW_m2'],'decay_start_fraction':.7};hoc=18100.
        xyz=[point.x,point.y,r['z_m']+min(.76,r['height_m']*.4)]
        group={'id':'Fuel_'+original,'room':solver['id'],'cad_key':original,'cad_floor':r['cad_floor'],
            'cad_room':r['cad_room'],'energy_MJ':spec['energy_mj'],'heat_of_combustion_kJ_kg':hoc,
            'growth_kW_s2':spec['alpha_kw_s2'],'peak_kW':spec['peak_cap_kw'],'hrrpua_kW_m2':r['fuel_default']['hrrpua_kW_m2'] if practical else 1000.,
            'decay_after_fraction':spec['decay_start_fraction'],'position_m':xyz,'solver_position_m':native_point(solver,xyz),
            'basis':'retained v35 declared room fuel budget and t2 curve; proxy inventory'}
        if practical:group.update(fuel_area_m2=fuel_area,basis=r['fuel_default']['basis'],usage=r['fuel_default']['usage'])
        if original==fire_key:
            group['initial_time_s']=0.;group['position_m'][2]=r['z_m']+.02
            group['solver_position_m']=native_point(solver,group['position_m'])
        else:
            from .model import DEFAULTS
            mat={**(legacy['material_profiles'][target['material_profile']]['material'] if target else DEFAULTS['material']),
                 'ignition_C':options.get('solid_ignition_C',target['setpoint'] if target else 369.),
                 'proxy':True,'pilot':'assumed' if target is None or target.get('pilot_assumed') else 'none'}
            mat['absorptivity']=mat['emissivity']
            local=opening_candidates(r,solver,group,mat,horizontal)
            if not local and practical:
                xyz=[point.x,point.y,r['z_m']+.02]
                local=[{'id':'C_fallback','label':'room_floor_fuel_proxy','group':group['id'],
                        'room':solver['id'],'cad_key':original,'xyz':xyz,
                        'solver_xyz':native_point(solver,xyz),'normal':[0,0,1],
                        'solver_normal':[0,0,1],'material':deepcopy(mat),
                        'placement_basis':'fallback representative floor face; no valid opening-side face; not surveyed furniture',
                        'shared_budget_group':group['id']}]
                warnings.append('문 앞 후보 배치 불가 → 실 내부 대표 바닥면 사용: '+original)
            for candidate in local:
                candidate['id']='C_'+str(len(plates)+1);plates.append(candidate)
        groups.append(group)
    if not any('initial_time_s' in g for g in groups):raise ValueError('Missing initial fire fuel budget')
    display=[]
    for original,r in displayed.items():
        display.append({**r,'key':original,'solver_id':aliases[original], 'cluster_size':len(members[aliases[original]])})
    scenario={'name':'cad_building_cfbt','duration_s':options.get('duration_s',1800),'output_step_s':5.,'max_time_step_s':options.get('max_time_step_s',1.),
        'rooms':list(rooms.values()),'openings':horizontal+vertical,'fuel_groups':groups,'explicit_candidates':plates,
        'gas':{**options.get('gas',{}),'pilot_assumed':options.get('pilot_assumed',False if practical else True)},
        'criteria':options.get('criteria',{}),'flashover':options.get('flashover',{}),
        **({'room_fire_rule':deepcopy(options['room_fire_rule'])} if 'room_fire_rule' in options else {}),
        'window_breakage':deepcopy(options.get('window_breakage',{'enabled':False})),
        'spread':{'max_added_ignitions':options.get('max_added_ignitions',3),
                  'iteration_mode':options.get('iteration_mode','fixed_point' if practical else 'earliest_single'),
                  'max_runs':options.get('max_runs',6 if practical else options.get('max_added_ignitions',3)+1+(len(rooms) if options.get('flashover',{}).get('enabled') else 0)),
                  'wall_time_budget_s':execution_limits(options.get('duration_s',1800))['wall_time_budget_s'],
                  'run_timeout_s':execution_limits(options.get('duration_s',1800))['run_timeout_s'],
                  'quadrature_n':4 if practical else 6},
        'wall_material':{'conductivity_W_mK':1.75,'density_kg_m3':2200.,'specific_heat_kJ_kgK':1.,
                         'thickness_m':.15,'emissivity':.94,'assumed':True,'basis':'retained legacy concrete boundary proxy'},
        'cad':{'source_path':str(source),'building_sha256':hashlib.sha256(raw).hexdigest(),
               'candidate_basis':'two receiver-side assumed fuel faces per connected horizontal CAD aperture, 0.6/1.5 m; shared room fuel budget',
               'uncovered_fuel_groups':[g['id'] for g in groups if 'initial_time_s' not in g and not any(p['group']==g['id'] for p in plates)],
               'fuel_source_sha256':hashlib.sha256(fuel_source.read_bytes()).hexdigest() if not practical and fuel_source.is_file() else None,'fire_key':fire_key,
               'warnings':warnings,
               'display_rooms':display,'excluded':excluded,'members':members,'options':options,
               'geometry_basis':'equal-area equivalent native boxes; physical CAD polygons for display and supplementary aperture rays',
               'scope':'single_floor_with_cores' if vertical_smoke else 'single_floor' if selected_floor else 'coupled_building',
               'topology_corrections':topology_changes,
               'vertical_smoke':vertical_smoke,
               'vertical_basis':'native floor vents; stair25%/shaft80% effective area assumptions; equivalent outdoor ramp'}}
    if practical:
        scenario['wall_material']=wall_default(options.get('structure',building.get('structure','unconfirmed')))
    if topology_changes:warnings.append(f'원본 DXF 문 블록/벽 끝점 근거에 따라 개구부 {len(topology_changes)}곳 보정. 원본 building.json은 변경하지 않음.')
    if vertical_smoke:
        warnings.append('화재층 전체 + 다른 층의 확인된 수직 코어·인접 출입 공간만 연성 계산. 나머지 원격 실과 외벽 창→상층 고체 전파는 미평가. 원격층 고체 연료는 추가하지 않음.')
    if selected_floor and options.get('full_floor_search',True):
        remaining=sum('initial_time_s' not in g for g in groups)
        fo_rooms=len({g['room'] for g in groups})
        runs=2*(1+remaining+fo_rooms)  # finite allowance including one numerical retry per run
        scenario['spread'].update(full_floor_search=True,
            max_added_ignitions=options.get('max_added_ignitions',remaining),
            max_runs=options.get('max_runs',runs),max_passes=1+remaining+fo_rooms)
    if practical and options.get('uniform_fuel',True):
        from .fuel_layout import apply
        scenario=apply(scenario)
    return apply_profile(scenario,options.get('profile','practical'))
