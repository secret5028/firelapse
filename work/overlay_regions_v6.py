exec((__import__('pathlib').Path(__file__).parent/'probe_axes.py').read_text(encoding='utf8').split('for id in')[0])
p=json.loads((W/'cad-v6-runs/office-1F/plan.json').read_text(encoding='utf8'))
import cv2
for label,bounds in [('hall',(14055,-1779,14067,-1772)),('D6',(14041,-1795,14050,-1789))]:
 x0,y0,x1,y1=bounds;s=150;im=np.full((round((y1-y0)*s),round((x1-x0)*s),3),255,np.uint8)
 def px(q):return (round((q[0]-x0)*s),round((y1-q[1])*s))
 for r in p['rooms']:
  col=(190,230,255) if r['id']=='R9' else (220,255,200) if r['id']=='R15' else (250,220,215)
  for part in r['polys']:
   cv2.fillPoly(im,[np.int32([px(q) for q in part['o']])],col)
   for hole in part.get('h',[]):cv2.fillPoly(im,[np.int32([px(q) for q in hole])],(255,255,255))
 raw=json.loads((W/f'raw8-{label}.json').read_text(encoding='utf8'))
 for v in raw:
  if v['layer'] in ('CEN','TEX','TEXT1','K-FURNITURE','FUR'):continue
  cv2.polylines(im,[np.int32([px((q[0]*.001,q[1]*.001)) for q in v['points']])],False,(70,70,70),1)
 for o in p['openings']:
  for poly in o['polys']:
   cv2.polylines(im,[np.int32([px(q) for q in poly])],True,(0,0,240),2)
  q=np.mean([q for poly in o['polys'] for q in poly],axis=0)
  if x0<q[0]<x1 and y0<q[1]<y1:cv2.putText(im,o['id'],px(q),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,0,180),2)
 cv2.imencode('.png',im)[1].tofile(str(W/f'overlay-{label}.png'))

