import pathlib,sys,json,math
W=pathlib.Path(__file__).resolve().parent
sys.path[:0]=[str(W/'cad-deps'),r'C:\Users\<user>\Documents\Codex\2026-09-07\2\CAD3D']
from cad_connectivity import aperture_frame
from cad_evidence import geometry,opening_parts,polygon_parts
from shapely.geometry import LineString,Point
from shapely.ops import unary_union
import numpy as np
for name in ['hotel-1F','office-1F','exhibition-1F']:
 p=json.loads((W.parent/'outputs/CAD-연결보강-v4'/name/'plan.json').read_text(encoding='utf8'))
 foot=geometry(p['footprint']);walls=geometry(p['walls'])
 vectors=[v for v in p['source_vectors'] if v['category'] in ('wall','column') and not v['excluded_from_boundary'] and not v.get('excluded_by_auto')]
 print('\n',name)
 for o in p['openings']:
  if o['connection_status'] not in ('same_space','unresolved'):continue
  g,c,u,n,hw,hd=aperture_frame(o)
  near=[]
  for v in vectors:
   pts=list(v['points']);pts=pts+[pts[0]] if v['closed'] else pts
   for a,b in zip(pts,pts[1:]):
    a,b=np.array(a),np.array(b);seg=LineString([a,b]);delta=b-a;length=np.linalg.norm(delta)
    if length<.05 or seg.distance(g)>1:continue
    cos=abs(delta@u/length);normal=min(abs((a-c)@n),abs((b-c)@n));proj=sorted([(a-c)@u,(b-c)@u])
    if cos>.94 and normal<hd+.22:near.append(dict(id=v['id'],proj=[round(x,3) for x in proj],off=round(float(normal),3),length=round(float(length),3)))
  print(json.dumps(dict(id=o['id'],kind=o['kind'],sides=o['sides'],span=o.get('span'),bounds=[round(x,3) for x in g.bounds],hw=round(hw,3),hd=round(hd,3),foot_distance=round(g.distance(foot.boundary),3),leaves=len(o.get('leaves',[])),parallel=near),ensure_ascii=False))
