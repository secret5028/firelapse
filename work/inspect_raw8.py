import pathlib,sys,json,collections
W=pathlib.Path(__file__).resolve().parent
sys.path[:0]=[str(W/'cad-deps'),r'C:\Users\예방\Documents\Codex\2026-09-07\2\CAD3D']
from cadio import load
import cv2,numpy as np
case=next(c for c in json.loads((W/'cad-runs/regression.json').read_text(encoding='utf8')) if c['label']=='office' and c['floor']=='1F')
doc,ps,ins=load(case['source'])
groups=[('hall',(14048,-1778,14069,-1757)),('D13',(14005,-1787,14012,-1780)),('D6',(14040,-1796,14051,-1789)),('W89',(13989,-1784,13997,-1778)),('W65',(14003,-1779,14008,-1772)),('W62',(14005,-1795,14010,-1789))]
for name,(x0,y0,x1,y1) in groups:
 scale=min(1900/(x1-x0),1400/(y1-y0));im=np.full((round((y1-y0)*scale)+40,round((x1-x0)*scale)+40,3),255,np.uint8)
 def pix(p):return (round((p[0]*.001-x0)*scale)+20,round((y1-p[1]*.001)*scale)+20)
 near=[]
 for i,p in enumerate(ps):
  xs,ys=zip(*p.pts)
  if max(xs)*.001<x0 or min(xs)*.001>x1 or max(ys)*.001<y0 or min(ys)*.001>y1:continue
  near.append(dict(index=i,layer=p.layer,kind=p.kind,lt=p.lt,arc=p.arc,source=p.source,ins=ins[p.ins] if p.ins is not None else None,points=p.pts))
  color=(180,180,180) if p.lt.startswith('DASHED') else (35,35,35)
  if 'WIN' in p.layer:color=(200,100,0)
  if 'DOOR' in p.layer:color=(0,130,0)
  cv2.polylines(im,[np.int32([pix(pt) for pt in p.pts])],p.closed,color,1)
 cv2.imencode('.png',im)[1].tofile(str(W/f'raw8-{name}.png'))
 (W/f'raw8-{name}.json').write_text(json.dumps(near,ensure_ascii=False,indent=2),encoding='utf8')
 print(name,collections.Counter(p['layer'] for p in near), 'arcs',[(p['index'],p['layer'],p['arc']) for p in near if p['arc'] and p['layer'] in ('DOOR','WID')])
