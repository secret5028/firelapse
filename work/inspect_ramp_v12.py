from pathlib import Path
import json,math
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parent.parent
job=Path('C:/Users/<user>/Desktop/소방 크로키 업-로컬웹앱/data/d018b4bb75da4475b1fd75447603c1a0/cad-output')
p=json.loads((job/'B1/plan.json').read_text('utf8'));b=json.loads((job/'building.json').read_text('utf8'))
cx,cy=13918.87980991675,-1826.6773739486591
im=Image.new('RGB',(1000,1000),'white');d=ImageDraw.Draw(im)
at=lambda p:(500+(p[0]-cx)*25,500-(p[1]-cy)*25)
for v in p['source_vectors']:
 pts=v['points']
 if not any(abs(x-cx)<19 and abs(y-cy)<19 for x,y in pts):continue
 color={'wall':'#33445e','stair':'#c47a00','door':'#24a04a','window':'#d04673'}.get(v['category'],'#c2c8ce')
 if len(pts)>1:d.line([at(q) for q in pts],fill=color,width=2)
 if v['id'] in p['ramps'][0]['source_vector_ids']:d.text(at(pts[len(pts)//2]),v['id'],fill='red')
d.ellipse((495,495,505,505),fill='red')
im.save(root/'outputs/CAD-인터페이스복원-v12/램프-원본대조.png')
print('saved')
f0=b['floors'][0];wx=cx*f0['scale']+f0['shift'][0]-b['origin'][0];wy=cy*f0['scale']+f0['shift'][1]-b['origin'][1]
for f in b['floors'][:2]:
 p=json.loads((job/f['name']/'plan.json').read_text('utf8'))
 im=Image.new('RGB',(1000,1000),'white');d=ImageDraw.Draw(im)
 def at(q):return (500+(q[0]*f['scale']+f['shift'][0]-b['origin'][0]-wx)*25,500-(q[1]*f['scale']+f['shift'][1]-b['origin'][1]-wy)*25)
 for v in p['source_vectors']:
  pts=v['points'];screen=[at(q) for q in pts]
  if len(screen)<2 or not any(0<x<1000 and 0<y<1000 for x,y in screen):continue
  color={'wall':'#33445e','stair':'#c47a00','door':'#24a04a','window':'#d04673'}.get(v['category'],'#c2c8ce');d.line(screen,fill=color,width=2)
 d.text((15,15),f['name'],fill='black');im.save(root/f'outputs/CAD-인터페이스복원-v12/램프-{f["name"]}-정렬대조.png')
