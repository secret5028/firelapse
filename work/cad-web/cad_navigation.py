import json,base64
import numpy as np
from shapely.geometry import Polygon,LineString
from shapely.ops import unary_union
from shapely import points,contains,intersects,linestrings
from pathlib import Path
p=Path('work/cad-input/model.json');d=json.loads(p.read_text(encoding='utf-8'));step=.2;nx=291;nz=251
xx,zz=np.meshgrid(np.arange(nx)*step-12,np.arange(nz)*step-10);xy=np.column_stack([xx.ravel(),zz.ravel()]);pts=points(xy)
foot=Polygon([[5.5,0],[31.2,0],[31.2,23.6],[.3,23.6],[.3,15.8],[5.5,15.8]])
nav=[]
for f in range(3):
 if f==0:valid=~intersects(foot.buffer(.05),pts);wall=foot.buffer(.05)
 else:
  wall=unary_union([Polygon(p['outer'],p['holes']) for p in d[f-1]['wallProfiles']]).buffer(.055)
  slab=foot if f==1 else foot.difference(Polygon([[4,16.2],[9.9,16.2],[9.9,19],[4,19]]))
  valid=contains(slab,pts)&~intersects(wall,pts)
 flags=np.zeros(nx*nz,dtype=np.uint8);flags[valid]=16
 for delta,bit in [(1,1),(nx,2)]:
  ids=np.arange(nx*nz-delta);ok=valid[ids]&valid[ids+delta]
  if delta==1:ok&=(ids%nx!=nx-1)
  ids=ids[ok];edges=linestrings(np.stack([xy[ids],xy[ids+delta]],axis=1));ids=ids[~intersects(wall,edges)];flags[ids]|=bit;flags[ids+delta]|=(4 if bit==1 else 8)
 nav.append(base64.b64encode(flags.tobytes()).decode());print(f,valid.sum())
d[0]['navigation']={'nx':nx,'nz':nz,'step':step,'x0':-12,'z0':-10,'flags':nav};p.write_text(json.dumps(d,ensure_ascii=False),encoding='utf-8')
