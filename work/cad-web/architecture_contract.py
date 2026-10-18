"""Shared architectural topology contract in source-image coordinates.

No source-specific coordinates, inferred door types, or forced room closure.
An opening must be covered by a wall or supported by walls at BOTH jambs.
"""
import math
from copy import deepcopy

def _dist(a,b):return math.hypot(b[0]-a[0],b[1]-a[1])
def _projection(p,a,u):return (p[0]-a[0])*u[0]+(p[1]-a[1])*u[1]
def _point(a,u,t):return [a[0]+u[0]*t,a[1]+u[1]*t]

def bind_openings(shapes,tolerance=6):
 """Preserve opening endpoints/width; create host only across supported jambs.

 A generated host is full-height wall geometry with an opening cut by the renderer,
 NOT an opaque filler. Door/window upper/lower wall bands therefore survive.
 Unattached openings are retained in diagnostics, not silently discarded.
 """
 walls=[];other=[];issues=[];changes=[];rejected=[];seen=set()
 for i,original in enumerate(shapes):
  s=deepcopy(original);s.setdefault('id',f'structure-{i}')
  try:
   if not all(math.isfinite(float(v)) for k in ('a','b') for v in s[k]):raise ValueError()
   if _dist(s['a'],s['b'])<1e-6:raise ValueError()
  except (KeyError,TypeError,ValueError):
   rejected.append(s);issues.append({'kind':'invalid-segment','id':s['id']});continue
  if s['type']=='wall':
   key=tuple(sorted(tuple(round(float(x),3) for x in s[k]) for k in ('a','b')))
   if key in seen:changes.append({'kind':'duplicate-wall','id':s['id']});continue
   seen.add(key);walls.append(s)
  else:other.append(s)
 kept=[]
 for op in other:
  if op['type'] not in ('door','window'):kept.append(op);continue
  a,b=op['a'],op['b'];width=_dist(a,b);u=[(b[0]-a[0])/width,(b[1]-a[1])/width]
  aligned=[]
  for wall in walls:
   wa,wb=wall['a'],wall['b'];wl=_dist(wa,wb)
   # Both endpoints must lie on this opening's axis; perpendicular neighbors do not qualify.
   cross=lambda p:abs((p[0]-a[0])*u[1]-(p[1]-a[1])*u[0])
   if max(cross(wa),cross(wb))>tolerance:continue
   if abs(((wb[0]-wa[0])*u[0]+(wb[1]-wa[1])*u[1])/wl)<.995:continue
   lo,hi=sorted([_projection(wa,a,u),_projection(wb,a,u)])
   aligned.append((lo,hi,wall))
  hosts=[w for lo,hi,w in aligned if lo<=tolerance and hi>=width-tolerance]
  if hosts:
   host=min(hosts,key=lambda w:_dist(w['a'],w['b']))
  else:
   left=[w for lo,hi,w in aligned if lo<0 and abs(hi)<=tolerance]
   right=[w for lo,hi,w in aligned if hi>width and abs(lo-width)<=tolerance]
   if not left or not right:
    rejected.append(op);issues.append({'kind':'unattached-opening','id':op['id'],'reason':'opening needs full host or two collinear jamb supports'});continue
   host={'id':'opening-host:'+op['id'],'type':'wall','a':list(a),'b':list(b),'origin':'architectural-rule','rule':'two-jamb-opening-host','supportIds':[left[0]['id'],right[0]['id']],'reviewStatus':op.get('reviewStatus','candidate')}
   walls.append(host);changes.append({'kind':'opening-host-created','id':host['id'],'openingId':op['id']})
  op['hostWallId']=host['id'];op['sourceWidthPx']=width
  # Do not infer a hinged door, double leaf, swing direction or width from a bounding box.
  if op['type']=='door':op.setdefault('openingKind','unknown')
  kept.append(op)
 return walls+kept,{'issues':issues,'changes':changes,'unresolvedShapes':rejected,'ruleVersion':2}
