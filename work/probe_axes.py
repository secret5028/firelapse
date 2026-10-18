import pathlib,sys,json,math
W=pathlib.Path(__file__).resolve().parent;sys.path[:0]=[str(W/'cad-deps'),r'C:\Users\예방\Documents\Codex\2026-09-07\2\CAD3D']
from shapely.geometry import Point,LineString
from shapely.ops import unary_union
import numpy as np
p=json.loads((W.parent/'outputs/CAD-벽공리-v5/office-1F/plan.json').read_text(encoding='utf8'))
segments=[]
for v in p['source_vectors']:
 if v['category'] not in ('wall','column','window') or v.get('excluded_from_boundary') or v.get('excluded_by_auto'):continue
 pts=v['points']+[v['points'][0]] if v['closed'] else v['points']
 for a,b in zip(pts,pts[1:]):
  if math.dist(a,b)>.05:segments.append((LineString([a,b]),v['id']))
for id in ['D6','D13','D17','D18']:
 o=next(o for o in p['openings'] if o['id']==id)
 print(id,o['sides'])
 for leaf in o['leaves'][:1]:
  h=np.array(leaf['hinge']);r=leaf['r']
  for key in ('closed','open','open2'):
   if leaf.get(key) is None:continue
   end=np.array(leaf[key]);u=(end-h)/np.linalg.norm(end-h);span=LineString([h+u*.15,end-u*.15])
   close=sorted([(s.distance(Point(end)),vid) for s,vid in segments])[:3]
   overlap=[(vid,round(s.intersection(span.buffer(.05,cap_style=2)).length,3)) for s,vid in segments if s.intersection(span.buffer(.05,cap_style=2)).length>.15]
   print(key,close,overlap)
