import json,pathlib,sys,math
W=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(W/'cad-deps'))
from PIL import Image,ImageDraw,ImageFont
from shapely.geometry import Polygon
from shapely.ops import triangulate
O=W.parent/'outputs/CAD-모델링-v10';b=json.loads((O/'building.json').read_text(encoding='utf8'));f=b['floors'][0]
im=Image.new('RGB',(1800,1250),'#eef2f5');d=ImageDraw.Draw(im);faces=[]
def face(q,color):faces.append((sum(p[0]+p[1]+p[2]*.1 for p in q)/len(q),q,color))
def prism(parts,z0,z1,col):
 for p in parts:
  for ring in [p['o'],*p['h']]:
   for i,a in enumerate(ring):
    v=ring[(i+1)%len(ring)];face([[*a,z0],[*v,z0],[*v,z1],[*a,z1]],col)
  pg=Polygon(p['o'],p['h'])
  for t in triangulate(pg):
   if pg.covers(t.representative_point()):face([[*a,z1] for a in list(t.exterior.coords)[:-1]],col)
for p in f['render_slab']:
 pg=Polygon(p['o'],p['h'])
 for t in triangulate(pg):
  if pg.covers(t.representative_point()):faces.append((-1e9,[[*q,0] for q in list(t.exterior.coords)[:-1]],'#d7dedf'))
for band in f['bands']:
 if band['kind']=='wall':prism(band['polys'],0,min(1.1,band['z1']),'#aab8be')
for c in f['transport']:
 for step in c['meshes']:prism(step['polys'],step['z0'],step['z1'],'#d9ae3d')
 if c['kind']=='elev':prism(c['region'],0,.25,'#a590bc')
for r in f['model_ramps']:
 for i in range(len(r['inner'])-1):
  z=lambda k:.035+r['length_m']*.1*k/(len(r['inner'])-1)
  face([[*r['inner'][i],z(i)],[*r['outer'][i],z(i)],[*r['outer'][i+1],z(i+1)],[*r['inner'][i+1],z(i+1)]],'#c89255')
proj=lambda p:((p[0]-p[1])*.866,(p[0]+p[1])*.5-p[2]*1.8)
points=[proj(q) for _,qs,_ in faces for q in qs];xs,ys=zip(*points);mnx,mny=min(xs),min(ys);scale=min(1640/(max(xs)-mnx),950/(max(ys)-mny))
for _,qs,col in sorted(faces):d.polygon([(80+(proj(q)[0]-mnx)*scale,150+(proj(q)[1]-mny)*scale) for q in qs],fill=col,outline='#9c873f' if col=='#d9ae3d' else None)
font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',30);small=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',22)
d.text((65,36),'B1 · 지하주차장 3D 모델 v10',font=font,fill='#233a4c')
d.text((65,85),'노랑: 계단·참   보라: 승강기 위치   갈색: 차량 램프',font=small,fill='#385369')
d.text((65,1170),'형상 데이터 정적 미리보기 · 내부 확인을 위해 벽을 낮게 표시 · 램프 경사 10%는 표시용 가정',font=small,fill='#385369')
im.save(O/'B1-모델-미리보기.png')
