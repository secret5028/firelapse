"""CAD topology -> one coupled CFAST run, with explicit vertical-path assumptions."""
from pathlib import Path
import argparse, csv, hashlib, json, math, subprocess, time, sys
from cfast_design_fire import load_design, interpolate
from cfast_runtime import run_native
sys.path.insert(0,str(Path(__file__).resolve().parent/'cad-deps'))
from collections import defaultdict, deque
from shapely.geometry import Polygon, Point, mapping
from shapely.ops import unary_union

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'outputs/CAD-NIST가연물-v23'
SOURCE=Path('C:/Users/예방/Desktop/소방 크로키 업-로컬웹앱/data/d018b4bb75da4475b1fd75447603c1a0/cad-output/building.json')
OUT.mkdir(exist_ok=True)
raw=SOURCE.read_bytes(); B=json.loads(raw); floors={f['name']:f for f in B['floors']}
parser=argparse.ArgumentParser();parser.add_argument('--build-only',action='store_true');parser.add_argument('--parse-only',action='store_true');parser.add_argument('--duration',type=int,default=1800);parser.add_argument('--closed-vertical',action='store_true');parser.add_argument('--output');parser.add_argument('--ignition-config',default=str(ROOT/'work/cfast_nist_ignition.json'),help='Explicit conditional targets; default NIST desk scenario');parser.add_argument('--no-secondary',action='store_true',help='Run only the prescribed primary fire');parser.add_argument('--design-fire',default=str(ROOT/'work/cfast_nist_design_fire.json'))
parser.add_argument('--output-profile',choices=['web','full'],default='web',help='Web retains zone/compartment/device data at the original 5 s interval')
parser.add_argument('--max-time-step',type=float,help='Native MISC ceiling; error tolerances and all physical models remain unchanged')
parser.add_argument('--force',action='store_true',help='Recompute even if the input, engine and output checksums match')
parser.add_argument('--ceiling-config',help='Audited clear heights; structural storey levels and vertical shafts remain unchanged')
args=parser.parse_args()
assert args.max_time_step is None or args.max_time_step>0
if args.output:OUT=ROOT/'outputs'/args.output;OUT.mkdir(exist_ok=True)
duration=args.duration; stem='closed' if args.closed_vertical else 'multifloor'
design=load_design(args.design_fire,duration)
scenario_options=json.loads(Path(args.ignition_config).read_text('utf8')) if args.ignition_config and not args.no_secondary else {}
(OUT/'design-fire.json').write_text(json.dumps(design,ensure_ascii=False,indent=2),'utf8')
def key(f,r):return f'{f}_{r}'
def shape(ps):return unary_union([Polygon(p['o'],p.get('h',[])) for p in ps])
def polys(s):
    gs=[s] if s.geom_type=='Polygon' else list(s.geoms)
    return [{'o':list(g.exterior.coords)[:-1],'h':[list(h.coords)[:-1] for h in g.interiors]} for g in gs if g.geom_type=='Polygon' and g.area>.001]
rooms={}
for f in B['floors']:
    for r in f['rooms']:
        if 'outdoor' in r.get('tags',[]):continue
        rooms[key(f['name'],r['id'])]=dict(id=r['id'],floor=f['name'],name=' / '.join(r.get('names',[])[:2]) or r['id'],area=r['area'],height=f['h'],z=f['z'],c=r['c'],polys=r['polys'],core_kind=None)
nodes={(n['floor'],n['core_id']):n for n in B['core_nodes']}
used={(c[d+'_floor'],c[d+'_core']) for c in B['vertical_connections'] for d in ['from','to']}
core_keys={}; wall=[]; vertical=[]
for nk in sorted(used):
    n=nodes[nk]; fn,cid=nk
    if n['room_id']:
        k=key(fn,n['room_id']);rooms[k]['core_kind']=n['kind'];core_keys[nk]=k
    else:
        # Open staircase embedded in a hall: carve its existing footprint out of the host.
        assert n['association']=='contained_core_in_room',n
        host=key(fn,n['access_room_ids'][0]);transport=next(t for t in floors[fn]['transport'] if t['id']==cid)
        host_shape=shape(rooms[host]['polys']);foot=shape(transport['region']).intersection(host_shape)
        assert foot.area>1
        remain=host_shape.difference(foot);rooms[host]['polys']=polys(remain);rooms[host]['area']=remain.area
        k=key(fn,'CORE'+cid);core_keys[nk]=k
        rooms[k]=dict(id='CORE'+cid,floor=fn,name='개방형 계단',area=foot.area,height=floors[fn]['h'],z=floors[fn]['z'],c=[n['x'],n['y']],polys=polys(foot),core_kind=n['kind'])
        wall.append(dict(id=key(fn,'ACCESS'+cid),a=host,b=k,width=1.2,bottom=0,top=2.1,fraction=1,kind='stair_access',assumption='shared hall staircase access; 1.2m x 2.1m assumed'))
for f in B['floors']:
    for c in f['simulation_graph']['connections']:
        if c['kind'] not in ['door','door_elev']:continue
        aa,bb=c['sides'];a=key(f['name'],aa) if aa!='out' else 'OUTSIDE';b=key(f['name'],bb) if bb!='out' else 'OUTSIDE'
        if a=='OUTSIDE':a,b=b,a
        if a not in rooms or (b!='OUTSIDE' and b not in rooms) or a==b:continue
        d=c['dimensions'];frac=.01 if c['kind']=='door_elev' else (.5 if b=='OUTSIDE' else 1)
        wall.append(dict(id=key(f['name'],c['id']),a=a,b=b,width=d['width_m'],bottom=d['bottom_m'],top=d['top_m'],fraction=frac,kind=c['kind']))
for i,c in enumerate(B['vertical_connections']):
    low=core_keys[(c['from_floor'],c['from_core'])];up=core_keys[(c['to_floor'],c['to_core'])]
    n=nodes[(c['from_floor'],c['from_core'])];m=nodes[(c['to_floor'],c['to_core'])]
    # Effective flow area is a declared scenario assumption, not the whole stair-room area.
    fraction=.25 if c['kind']=='stair' else .8
    area=min(n['w']*n['h'],m['w']*m['h'],rooms[low]['area'],rooms[up]['area'])*fraction
    assert abs(rooms[low]['z']+rooms[low]['height']-rooms[up]['z'])<.02
    vertical.append(dict(id=f'V{i}',kind=c['kind'],a=up,b=low,area=area,from_floor=c['from_floor'],to_floor=c['to_floor'],from_room=rooms[low]['id'],to_room=rooms[up]['id'],position=[n['x'],n['y']],area_factor=fraction))
# The known ramp exits outdoors at the 1F level; it is not a door into a 1F room.
for f in B['floors']:
    for ramp in f.get('model_ramps',[]):
        end=[(a+b)/2 for a,b in zip(ramp['inner'][0],ramp['outer'][0])]
        from shapely.geometry import Point
        candidates=[(shape(r['polys']).distance(Point(end)),k) for k,r in rooms.items() if r['floor']==f['name'] and r['area']>100]
        dist,parking=min(candidates)
        assert dist<15,(dist,parking)
        vertical.append(dict(id='RAMP0',kind='ramp',a='OUTSIDE',b=parking,area=ramp['width_m']*3.0,from_floor=f['name'],to_floor=ramp['to_floor'],from_room=rooms[parking]['id'],to_room='out',position=end,assumption='equivalent ceiling vent to outdoors at 1F; width x 3m effective length, not a resolved sloping flow'))
# Isolated rooms with closed boundaries cannot receive advected smoke in this scenario.
height_config=json.loads(Path(args.ceiling_config).read_text('utf8')) if args.ceiling_config else None
if height_config:
    assert height_config['building_sha256']==hashlib.sha256(raw).hexdigest()
    vertical_endpoints={v[s] for v in vertical for s in ['a','b']}
    for k,r in rooms.items():
        audit=height_config['rooms'].get(k)
        r['structural_height']=r['height']
        if audit and not r['core_kind'] and k not in vertical_endpoints:
            r['height']=audit['height_m'];r['ceiling_evidence']=audit
        else:r['ceiling_evidence']={'basis':'structural height preserved for vertical passage','height_m':r['height']}
        assert 0<r['height']<=r['structural_height']
    for v in wall:
        assert v['top']<=min(rooms[k]['height'] for k in [v['a'],v['b']] if k in rooms),v
adj=defaultdict(set)
for v in wall+vertical:
    if v['a']!='OUTSIDE' and v['b']!='OUTSIDE':adj[v['a']].add(v['b']);adj[v['b']].add(v['a'])
fire='3F_R9';reachable={fire};q=deque([fire])
while q:
    for n in adj[q.popleft()]-reachable:reachable.add(n);q.append(n)
excluded=[dict(key=k,floor=r['floor'],id=r['id'],reason='closed/island; not solved') for k,r in rooms.items() if k not in reachable]
rooms={k:r for k,r in rooms.items() if k in reachable}
wall=[v for v in wall if v['a'] in rooms and (v['b'] in rooms or v['b']=='OUTSIDE')]
vertical=[v for v in vertical if (v['a'] in rooms or v['a']=='OUTSIDE') and v['b'] in rooms]
print(json.dumps(dict(rooms=len(rooms),wall=len(wall),vertical=len(vertical),excluded=len(excluded)),ensure_ascii=False),flush=True)
# Keep the fire floor and every vertical core independent. Only merge remote rooms
# through fully open ordinary doors, with explicit member-to-solver provenance.
import copy
display_rooms=copy.deepcopy(rooms);display_wall=copy.deepcopy(wall)
members={k:[k] for k in rooms};aliases={k:k for k in rooms}
while len(rooms)>100:
    choices=[]
    for v in wall:
        a,z=v['a'],v['b']
        if z not in rooms or a==z or v['kind']!='door' or v['fraction']!=1:continue
        ra,rz=rooms[a],rooms[z]
        if ra['floor']=='3F' or ra['core_kind'] or rz['core_kind']:continue
        choices.append((ra['area']+rz['area'],a,z))
    assert choices,'No permissible aggregation remains'
    _,a,z=min(choices);ra,rz=rooms[a],rooms[z]
    volume=ra['area']*ra['height']+rz['area']*rz['height']
    ra['area']+=rz['area'];ra['height']=volume/ra['area'] if height_config else ra['height'];ra['polys']+=rz['polys'];members[a]+=members.pop(z)
    for old in members[a]:aliases[old]=a
    del rooms[z]
    for v in wall:
        if v['a']==z:v['a']=a
        if v['b']==z:v['b']=a
    wall=[v for v in wall if v['a']!=v['b']]
    for v in vertical:
        if v['a']==z:v['a']=a
        if v['b']==z:v['b']=a
print('solver compartments:',len(rooms),'aggregated groups:',sum(len(m)>1 for m in members.values()),flush=True)
lines=["&HEAD VERSION=7500 TITLE='CAD coupled floors example' /",f'&TIME SIMULATION={duration+1} PRINT={120 if args.output_profile=="full" else 0} SMOKEVIEW=5 SPREADSHEET=5 /',
 '&INIT PRESSURE=101325 RELATIVE_HUMIDITY=50 INTERIOR_TEMPERATURE=20 EXTERIOR_TEMPERATURE=20 /',
 "&MATL ID='CONCRETE' MATERIAL='Assumed concrete' CONDUCTIVITY=1.75 DENSITY=2200 SPECIFIC_HEAT=1 THICKNESS=0.15 EMISSIVITY=0.94 /"]
dims={}
for i,(k,r) in enumerate(rooms.items()):
    w=max(math.sqrt(r['area']),max([v['width']+.2 for v in wall if k in [v['a'],v['b']]] or [0]));d=r['area']/w;dims[k]=(w,d)
    if k in scenario_options.get('preserve_aspect_rooms',[]):
        xmin,ymin,xmax,ymax=shape(r['polys']).bounds
        w=math.sqrt(r['area']*(xmax-xmin)/(ymax-ymin));d=r['area']/w
        assert all(v['width']<=w for v in wall if k in [v['a'],v['b']])
        dims[k]=(w,d)
    shaft=' SHAFT=.TRUE.' if r['core_kind'] else ''
    lines.append(f"&COMP ID='{k}' WIDTH={w:.8f} DEPTH={d:.8f} HEIGHT={r['height']} ORIGIN={i*60},0,{r['z']}{shaft} CEILING_MATL_ID='CONCRETE' WALL_MATL_ID='CONCRETE' FLOOR_MATL_ID='CONCRETE' LEAK_AREA_RATIO=0.00017,0.000052 /")
for v in wall:lines.append(f"&VENT TYPE='WALL' ID='{v['id']}' COMP_IDS='{v['a']}','{v['b']}' WIDTH={v['width']} BOTTOM={v['bottom']} TOP={v['top']} FACE='FRONT' OFFSET=0 CRITERION='TIME' T=0 F={v['fraction']} /")
for v in vertical:lines.append(f"&VENT TYPE='FLOOR' ID='{v['id']}' COMP_IDS='{v['a']}','{v['b']}' AREA={v['area']:.7f} SHAPE='SQUARE' CRITERION='TIME' T=0 F={0 if args.closed_vertical else 1} /")
w,d=dims[fire]
assert design['base_height_m']<rooms[fire]['height']
chemistry=' '.join(f'{k}={v}' for k,v in design['formula'].items())
lines += [f"&FIRE ID='ExampleFire' COMP_ID='{fire}' FIRE_ID='Wood' LOCATION={w/2:.5f},{d/2:.5f} /", f"&CHEM ID='Wood' {chemistry} HEAT_OF_COMBUSTION={design['heat_of_combustion_kJ_kg']} RADIATIVE_FRACTION={design['radiative_fraction']} /", "&TABL ID='Wood' LABELS='TIME','HRR','HEIGHT','AREA','CO_YIELD','SOOT_YIELD' /"]
for t,q in design['hrr_kW']:lines.append(f"&TABL ID='Wood' DATA={t},{q:.6f},{design['base_height_m']},{design['area_m2']},{design['co_yield']},{design['soot_yield']} /")
ignition=None;fuel_specs=[]
if args.ignition_config and not args.no_secondary:
    config_path=Path(args.ignition_config);ignition=json.loads(config_path.read_text('utf8'))
    if ignition.get('defaults_file'):
        preset=json.loads((config_path.parent/ignition['defaults_file']).read_text('utf8'))
        ignition['defaults']=preset
        ignition['material']={**preset['material'],**ignition.get('material',{})}
        ignition['growth']={**preset['growth'],**ignition.get('growth',{})}
        ignition['targets']=[{**preset['ignition'],**target} for target in ignition['targets']]
    if ignition.get('auto_place_other_rooms'):
        existing={t['room_key'] for t in ignition['targets']}
        for original,r in display_rooms.items():
            if original in existing or r['core_kind']:continue
            footprint=shape(r['polys']);interior=footprint.buffer(-.42)
            if interior.is_empty:interior=footprint
            point=Point(r['c'])
            if not interior.contains(point):point=interior.representative_point()
            k=aliases[original];w,d=dims[k];xmin,ymin,xmax,ymax=shape(rooms[k]['polys']).bounds
            xy=[point.x,point.y];sx=max(.05,min(w-.05,(point.x-xmin)/(xmax-xmin)*w));sy=max(.05,min(d-.05,(point.y-ymin)/(ymax-ymin)*d))
            ignition['targets'].append(dict(ignition['defaults']['ignition'],id='Fuel_'+original,name=f"{r['floor']} {r['id']} · {r['name']}",room_key=original,position_xy_m=xy,solver_xy_m=[sx,sy],target_height_m=.5,normal=[0,0,1],placement='one default fuel per solved noncore room; equivalent-compartment coordinate mapping'))
    material=ignition['material'];growth=ignition['growth']
    lines.append(f"&MATL ID='{material['id']}' MATERIAL='Declared target material' CONDUCTIVITY={material['conductivity_W_mK']} DENSITY={material['density_kg_m3']} SPECIFIC_HEAT={material['specific_heat_kJ_kgK']} THICKNESS={material['thickness_m']} EMISSIVITY={material['emissivity']} /")
    fire_definitions={}
    for target in ignition['targets']:
        original=target['room_key'];assert original in display_rooms
        k=aliases[original]
        assert target['criterion'] in ['TEMPERATURE','FLUX'] and target['setpoint']>0
        r=display_rooms[original];w,d=dims[k];z=target['target_height_m']
        if 'solver_xy_m' in target:x,y=target['solver_xy_m'];xy=target['position_xy_m']
        else:
            dx,dy=target['offset_xy_m'];x,y=w/2+dx,d/2+dy;xy=[r['c'][0]+dx,r['c'][1]+dy]
        assert 0<x<w and 0<y<d and 0<z<r['height']
        fraction=target.get('fuel_fraction',1.)
        assert 0<fraction<=1
        definition='Secondary' if fraction==1 else 'Secondary_'+target['id']
        fire_definitions[definition]=fraction
        if ignition.get('evidence_based'):
            half=math.sqrt(growth['area_m2']*fraction)/2
            assert half<x<w-half and half<y<d-half, 'Equivalent fire footprint outside solver compartment'
        assert shape(r['polys']).contains(Point(xy)),(target['id'],xy)
        # The ignition target is the exposed fuel surface, not necessarily its centre.
        tx,ty=x,y;target_xy=list(xy)
        if 'target_offset_xy_m' in target:
            tx=w/2+target['target_offset_xy_m'][0];ty=d/2+target['target_offset_xy_m'][1]
            target_xy=[r['c'][0]+target['target_offset_xy_m'][0],r['c'][1]+target['target_offset_xy_m'][1]]
        assert 0<tx<w and 0<ty<d and shape(r['polys']).contains(Point(target_xy))
        normal=target['normal'];assert abs(sum(x*x for x in normal)-1)<.001
        tid='T_'+target['id'];fid=target['id']
        lines.append(f"&DEVC ID='{tid}' COMP_ID='{k}' TYPE='PLATE' LOCATION={tx:.6f},{ty:.6f},{z} NORMAL={','.join(map(str,normal))} MATL_ID='{material['id']}' THICKNESS={material['thickness_m']} /")
        lines.append(f"&FIRE ID='{fid}' COMP_ID='{k}' FIRE_ID='{definition}' LOCATION={x:.6f},{y:.6f} IGNITION_CRITERION='{target['criterion']}' SETPOINT={target['setpoint']} DEVC_ID='{tid}' /")
        fuel_specs.append(dict(target,floor=r['floor'],position=xy,target_position=target_xy,solver_target_position=[tx,ty,z],solver_key=k,cluster_size=len(members[k]),solver_position=[x,y,z],base_height=growth['base_height_m'],area=growth['area_m2']*fraction,target_id=tid))
    for definition,fraction in fire_definitions.items():
        lines += [f"&CHEM ID='{definition}' CARBON=6 HYDROGEN=10 OXYGEN=5 HEAT_OF_COMBUSTION={growth['heat_of_combustion_kJ_kg']} RADIATIVE_FRACTION=0.33 /", f"&TABL ID='{definition}' LABELS='TIME','HRR','HEIGHT','AREA','CO_YIELD','SOOT_YIELD' /"]
        for t,q in growth['hrr_kW']:lines.append(f"&TABL ID='{definition}' DATA={t},{q*fraction},{growth['base_height_m']},{growth['area_m2']*fraction},{growth['co_yield']},{growth['soot_yield']} /")
    (OUT/'ignition-scenario.json').write_text(json.dumps(ignition,ensure_ascii=False,indent=2),'utf8')
if args.max_time_step is not None:lines.append(f'&MISC MAX_TIME_STEP={args.max_time_step} /')
lines.append('&TAIL /');(OUT/f'{stem}.in').write_text('\n'.join(lines),encoding='ascii')
manifest=dict(rooms=rooms,wall=wall,vertical=vertical,excluded=excluded,members=members,aliases=aliases,dims=dims)
(OUT/'connection-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False),encoding='utf8')
if args.build_only:raise SystemExit(0)
exe=ROOT/'work/smokeview-demo/firemodels/cfast7/cfast.exe';start=time.monotonic();runtime=None
if not args.parse_only:
    runtime=run_native(exe,OUT,stem,flags=['-k','-o:CD'] if args.output_profile=='web' else [],force=args.force)
elapsed=runtime['wall_seconds'] if runtime else time.monotonic()-start
log=(OUT/f'{stem}-execution.log').read_text(errors='replace')
if 'NORMAL EXIT' not in log.upper():raise RuntimeError(log[-5000:])
if args.parse_only:
    import re
    timing=OUT/f'{stem}-timing.json'
    elapsed=json.loads(timing.read_text())['wall_seconds'] if timing.exists() else float(re.search(r'execution time\s*=\s*([\d.eE+\-]+)',log).group(1))
with (OUT/f'{stem}_zone.csv').open() as stream:
    reader=csv.reader(stream);units=next(reader);headers=next(reader);values=[dict(zip(headers,map(float,row))) for row in reader if row]
assert values[-1]['Time']==duration
result=dict(schema='cad-cfast-overlay-v2',engine='CFAST 7.7.7',floor='3F',floors=list(floors),fire_room='R9',fire_key=fire,fire_name='공작실/설비보관실',building_sha256=hashlib.sha256(raw).hexdigest(),duration=duration,step=5,elapsed_seconds=round(elapsed,3),rooms=[],excluded=excluded,vents=display_wall,vertical_connections=vertical,solver_compartments=len(rooms),solver_members=members,
 assumptions=['3F R9 예시 화재: 5분에 1 MW 도달 후 유지. 초기 20°C, 목재 대리연료·콘크리트는 예제 물성',
 '일반 실내문 100%, 외부문 50%, 창 닫힘. 닫힌 승강기문 유효 누설면적 1% 가정, 소화설비 미작동',
 '계단·승강로는 층별 단일 혼합 구역과 수직 개구부로 연결. 계단 유효 개구 25%, 승강로 80%는 앵커 면적 대비 시연 가정',
 'B1 주차장↔1F 외기 램프는 등가 수직 개구부로 근사. 경사로 내부 유동을 직접 계산한 것이 아님',
 '닫힌 경계로 분리된 실·작은 샤프트는 미계산 표시. 테라스는 실외. 층간 이동은 실제 CFAST 연성 계산',
 'CFAST 구획 한도: 화재층·수직 코어는 개별 계산, 다른 층의 일부 열린 문 연결 실은 묶어 계산하며 같은 값 표시',
 '구획별 평균값이며 연기 소용돌이·불꽃 움직임은 표시 효과. 다른 실의 2차 착화나 백드래프트 판정은 포함하지 않음',
 '미리 계산한 예시: 문·창·화점 편집 후 자동 재계산은 아직 연결하지 않음'],
 sources=['https://pages.nist.gov/cfast/manuals.html','https://github.com/firemodels/cfast/blob/master/Manuals/CFAST_Users_Guide/Input_File_Chapter.tex'])
for i,(k,r) in enumerate(rooms.items(),1):
    series=[[v['Time'],v[f'ULT_{i}'],v.get(f'LLT_{i}',v[f'ULT_{i}']),v.get(f'HGT_{i}',0),v[f'ULOD_{i}'],v.get(f'LLOD_{i}',v[f'ULOD_{i}'])] for v in values]
    assert all(math.isfinite(x) for row in series for x in row)
    assert all(-.01<=row[3]<=r['height']+.01 for row in series)
    for original in members[k]:result['rooms'].append(dict(display_rooms[original],key=original,solver_key=k,cluster_size=len(members[k]),clear_height=display_rooms[original]['height'],height=r['height'],series=series))
result['hrr']=[v['HRR_1'] for v in values];result['flame_height']=[v['FLHGT_1'] for v in values]
result['design_fire']=design
result['sources'] += design.get('sources',[])
result['calculation_mode']=('nist_evidence_scenario' if ignition.get('evidence_based') else 'experimental_secondary_ignition') if ignition else 'prescribed_design_fire'
result['prescribed_hrr']=[interpolate(design['hrr_kW'],v['Time']) for v in values]
result['fires']=[dict(id='ExampleFire',name=design['name'],room_key=fire,floor='3F',position=rooms[fire]['c'],base_height=design['base_height_m'],area=design['area_m2'],criterion='TIME',setpoint=0,unit='s',ignition_time=0,hrr=result['hrr'],flame_height=result['flame_height'],ignited=[1]*len(values))]
result['total_hrr']=result['hrr'][:]
if design.get('curve_type')=='tabulated':
    result['assumptions'][0]=f"3F R9: {design['name']}, NIST 실측 도표 수치화, 최대 {design['peak_kW']:.1f} kW. 건물 용도의 대표 시나리오이며 실제 재고·최악 화재의 확정값 아님. 초기 20°C."
else:
    result['assumptions'][0]=f"3F R9 지정 화재: 최대 {design['peak_kW']} kW, 성장 {design['growth_seconds']}초, 유지 {design['steady_seconds']}초, 감쇠 {design['decay_seconds']}초. 끝값 {'유지' if design['end_behavior']=='hold' else '0'}. 초기 20°C. 수치는 비교용 가정이며 NIST 지정 표준값 아님."
result['assumptions'] += [design['basis'],design['fuel_basis'],f"입력곡선 적분 열량 {design['prescribed_energy_MJ']:.3f} MJ ({duration}초), 연소열 환산 연료 {design['equivalent_fuel_kg']:.2f} kg. 실제 건물 연료 재고량이 아니며 실제 방출 HRR은 산소 조건에 따라 달라짐.", 'CAD 실은 등면적 직사각형으로 변환. 벽 개구부의 실제 수평 위치·국소 문너머 화염 접촉을 해석하지 않음. 구획별 상·하부층 평균 결과로 해석.', 'CFAST의 조건부 추가 착화 기능은 보존하되 기본 계산에서는 미지정. 추가 착화를 계산하지 않았다는 것이 다른 방이 타지 않는다는 뜻은 아님.' if not ignition else '지정한 별도 대상만 조건부 착화 계산. 해당 NIST 시험 재료에 근거한 값이며 모든 가연물의 공통 기본값이 아님.']
if ignition:
    # Detailed spreadsheet files use four header rows and HRR in W (zone.csv uses kW).
    def detailed(suffix):
        with (OUT/f'{stem}_{suffix}.csv').open() as stream:
            rd=csv.reader(stream);head=next(rd);next(rd);ids=next(rd);units=next(rd)
            return [dict(zip(head,map(float,row))) for row in rd if row],dict(zip(head,units)),dict(zip(head,ids))
    comp,cu,ci=detailed('compartments');dev,du,di=detailed('devices')
    # Reject inconsistent native ignition output instead of inventing a flame.
    # A symmetric simultaneous-trigger case reproduced this in CFAST 7.7.7.
    import re
    native_log=(OUT/f'{stem}.log').read_text(errors='replace')
    native_events={m.group(1):float(m.group(2)) for m in re.finditer(r'Object #\d+ \(([^)]+)\) ignited at\s+(\d+) seconds',native_log)}
    assert len(comp)==len(dev)==len(values)
    for i,target in enumerate(fuel_specs,2):
        target_index=next(k.removeprefix('TRGSURT_') for k,v in di.items() if k.startswith('TRGSURT_') and v==target['target_id'])
        temp='TRGSURT_'+target_index;flux='TRGFLXI_'+target_index
        assert cu[f'HRR_{i}']=='W' and du[flux] in ['W/m^2','kW/m^2']
        flux_scale=1000 if du[flux]=='W/m^2' else 1
        assert ci[f'HRR_{i}']==target['id']
        flags=[int(v[f'IGN_{i}']) for v in comp]
        event=next((v['Time'] for v in comp if v[f'IGN_{i}']>0),None)
        if event is not None:
            assert target['id'] in native_events, f"Inconsistent native ignition: {target['id']} has IGN but no ignition log"
            assert abs(event-native_events[target['id']])<=5.5, 'Ignition time disagrees with native log'
            if any(interpolate(ignition['growth']['hrr_kW'],max(0,v['Time']-event))>0 for v in comp):
                assert any(v[f'HRR_E{i}']>0 for v in comp), 'Native ignition has no expected HRR despite prescribed growth'
        result['fires'].append(dict(target,ignition_time=event,ignited=flags,hrr=[v[f'HRR_{i}']/1000 for v in comp],flame_height=[v[f'FLHGT_{i}'] for v in comp],target_series=[[v['Time'],v[temp],v[flux]/flux_scale] for v in dev]))
    result['total_hrr']=[sum(f['hrr'][i] for f in result['fires']) for i in range(len(values))]
    result['ignition_scenario']=ignition
    result['assumptions']=[s.replace('다른 실의 2차 착화나 백드래프트 판정은 포함하지 않음','등록한 대상의 CFAST 조건부 2차 착화 포함. 백드래프트 판정은 포함하지 않음') for s in result['assumptions']]
    criteria=' / '.join(f"{t['name']}: {'표면온도' if t['criterion']=='TEMPERATURE' else '입사 열유속'} {t['setpoint']} {t['unit']}" for t in fuel_specs)
    result['assumptions'] += [ignition['description'],(f"기본 가연물 {len(fuel_specs)}개: 표면온도 300°C 조건" if ignition.get('auto_place_other_rooms') else criteria)+' — 해당 재료 시험에 근거한 조건. 점화원 존재는 별도 가정이며 보편적 재료 상수 아님.', '착화 후 성장·감쇠는 ignition_scenario.growth의 지정 곡선 사용.', '가연물 위치는 CAD 실 내부의 예시 배치. 계산은 동일 면적 직사각형 좌표로 대응하며 묶인 실들은 같은 구획 환경을 공유함. 미계산 구획에는 배치하지 않음. 실제 물품 위치나 문 너머 국소 화염 접촉을 재현한 것이 아님.','착화 시각은 CFAST IGN 출력의 첫 1인 시점(5초 간격). 연기 도달만으로 화염을 생성하지 않음']
    if ignition.get('defaults'):
        result['assumptions'].append(ignition['defaults']['description'])
        result['assumptions'] += ignition['defaults'].get('evidence',{}).get('assumptions',[])
        if ignition.get('defaults',{}).get('preset_id') != 'nist_paper_trigger_workstation' and ignition.get('evidence_based'):
            result['assumptions'].append('추가 상판 연소는 45kW/m² 콘 시험의 총열량212MJ/m²·평균연소시간1739초를 사용한 등가 일정 HRR. 실제 구획의 변화하는 노출에 따라 HRR이 다시 산정되는 모델은 아님.')
        result['sources'] += [v['url'] for v in ignition['defaults'].get('sources',[])]
# Native vent-jet burning is already coupled into compartment temperatures.
# Include its HRR in the total, without inventing a resolved door-flame shape.
if not ignition:
    with (OUT/f'{stem}_compartments.csv').open() as stream:
        rd=csv.reader(stream);head=next(rd);next(rd);next(rd);next(rd)
        comp=[dict(zip(head,map(float,row))) for row in rd if row]
jet_keys=[k for k in comp[0] if k.startswith('DJET_')]
result['registered_fire_hrr']=result['total_hrr'][:]
result['vent_jet_hrr']=[sum(v[k] for k in jet_keys)/1000 for v in comp]
assert len(result['vent_jet_hrr'])==len(result['total_hrr'])
result['total_hrr']=[a+b for a,b in zip(result['registered_fire_hrr'],result['vent_jet_hrr'])]
if max(result['vent_jet_hrr'],default=0)>.01:
    result['assumptions'].append('총 HRR은 등록 화원과 CFAST 개구부 미연소 가스 연소(DJET, 외기 포함)의 합. 개구부 연소 열은 구획 계산에 반영되지만 문·천장을 따라 이어지는 국소 화염 형상은 아직 표시하지 않음.')
for i,v in enumerate(vertical,1):
    # Signed mass flow by slab, mapped to the actual upper/lower compartment pair.
    v['flow_series']=[[x['Time'],x.get(f'VVENT_{i}',0),x.get(f'VSLABF_{i}_1',0),x.get(f'VSLABF_{i}_2',0)] for x in values]
result['floor_summary']={f:dict(max_upper=max((r['series'][-1][1] for r in result['rooms'] if r['floor']==f),default=20),max_od=max((r['series'][-1][4] for r in result['rooms'] if r['floor']==f),default=0)) for f in floors}
from cfast_combustion import add_combustion
add_combustion(result, OUT, json.loads(raw))
from cfast_plume_metadata import add_plume_metadata
add_plume_metadata(result, OUT/f'{stem}.in')
from cfast_fuel_inventory import add_fuel_inventory
add_fuel_inventory(result)
result['runtime']=dict(output_profile=args.output_profile,max_time_step=args.max_time_step,cache_hit=bool(runtime and runtime['cache_hit']),invocation_seconds=time.monotonic()-start,engine_unchanged=True)
if height_config:
    result['ceiling_config']=height_config
    result['assumptions'].append('실별 반자고: CAD 실번호와 함께 표시된 높이를 우선, 없으면 같은 건물 용도별 추정값. 반자 위 체적 생략. 수직 코어/램프 연결실은 층간 높이 유지. 원격 병합실 계산 높이는 체적 보존 면적가중 평균. 천장 경계 열물성은 기존 콘크리트 대리값을 유지하므로 반자 재료까지 확정한 모델은 아님.')
result['plume_postprocess']['not_solver_rerun']=False
(OUT/('closed-result.json' if args.closed_vertical else 'cfast-demo.json')).write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')),encoding='utf8')
print(json.dumps(dict(seconds=elapsed,summary=result['floor_summary']),ensure_ascii=False),flush=True)
