from pathlib import Path
import json, math, sys, shutil
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'work/cad-deps'))
from shapely.geometry import Polygon,Point,box
from shapely.ops import unary_union
out=ROOT/'outputs/CAD-가연물묶음-v30'
out.mkdir(exist_ok=True)
(out/'backup').mkdir(exist_ok=True)
for name in ['cad_cfast_multifloor.py','cad_cfast_realistic.js','cad_cfast_multifloor_overlay.js']:
 p=out/'backup'/name
 if not p.exists():shutil.copy2(ROOT/'work'/name,p)
old=json.loads((ROOT/'work/cfast_spread_scenario_v26.json').read_text('utf8'))
baseline=json.loads((ROOT/'outputs/CAD-공식플룸-v29/cfast-demo.json').read_text('utf8'))
app=Path('C:/Users/예방/Desktop/소방 크로키 업-로컬웹앱')
b=json.loads((app/'data/d018b4bb75da4475b1fd75447603c1a0/cad-output/building.json').read_text('utf8'))
floor=next(f for f in b['floors'] if f['name']=='3F')
manifest=json.loads((ROOT/'outputs/CAD-속도검증-v27/final/connection-manifest.json').read_text('utf8'))
targets=old['targets'][:2]
for i,t in enumerate(targets):
 t['fuel_fraction']=1.;t['inventory_parent']=t['id'];t['placement_zone']='door_side' if i==0 else 'interior'
for oldt,doorid in zip(old['targets'][2:],['D14','D10']):
 r=next(r for r in floor['rooms'] if '3F_'+r['id']==oldt['room_key'])
 poly=unary_union([Polygon(p['o'],p['h']) for p in r['polys']])
 opening=next(o for o in floor['openings'] if o['id']==doorid)
 door=[sum(l['hinge'][i] for l in opening['leaves'])/len(opening['leaves']) for i in [0,1]]
 side=math.sqrt(5.95*.5);half=side/2
 xmin,ymin,xmax,ymax=poly.bounds;w,d=manifest['dims'][oldt['room_key']]
 candidates=[]
 for ix in range(math.ceil((xmax-xmin)/.25)):
  for iy in range(math.ceil((ymax-ymin)/.25)):
   x=xmin+half+.15+ix*.25;y=ymin+half+.15+iy*.25
   if poly.covers(box(x-half-.1,y-half-.1,x+half+.1,y+half+.1)):
    sx=(x-xmin)/(xmax-xmin)*w;sy=(y-ymin)/(ymax-ymin)*d
    if half<sx<w-half and half<sy<d-half:candidates.append((math.dist([x,y],door),x,y,sx,sy))
 assert candidates
 near=min(candidates)
 # Interior representative stays near the old inventory location, separated from door group.
 far=min((c for c in candidates if math.dist(c[1:3],near[1:3])>side+.5 and c[0]>near[0]+1),key=lambda c:math.dist(c[1:3],oldt['position_xy_m']))
 for zone,c in [('Door',near),('Inner',far)]:
  t=dict(oldt,id=oldt['id']+zone,name=oldt['name']+(' · 문 근처' if zone=='Door' else ' · 방 안쪽'),position_xy_m=list(c[1:3]),solver_xy_m=list(c[3:5]),width_m=side,depth_m=side,fuel_fraction=.5,inventory_parent=oldt['id'],placement_zone=zone.lower(),door_id=doorid,door_distance_m=c[0],placement='CAD interior grid candidate; bbox mapping to equivalent compartment, not a local door-jet model')
  targets.append(t)
old['targets']=targets
old['unit_profiles']={'desk':{'height_m':.75,'depth_limit_m':.8},'cabinet':{'height_m':1.2,'depth_limit_m':.65},'tall_cabinet':{'height_m':1.8,'depth_limit_m':.65}}
old['description']='v30: R9 최초 화원/추가 두 묶음 유지. 홀과 A/S 재고 각각을 문 근처/안쪽 두 대표 묶음에 50%씩 배분. 착화 기준/노출면 높이/물성 유지. 총 지정 HRR 곡선과 환산 연료량 보존. 표시 단위는 독립 화원이 아님.'
(ROOT/'work/cfast_fuel_groups_v30.json').write_text(json.dumps(old,ensure_ascii=False,indent=2),'utf8')
print(json.dumps([dict(id=t['id'],xy=t.get('position_xy_m'),fraction=t['fuel_fraction'],door_distance=t.get('door_distance_m')) for t in targets],ensure_ascii=False))
