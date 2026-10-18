"""Canonical wall axes and topology diagnostics; gaps need source evidence."""
import math
import numpy as np

def canonical(walls, image=None, openings=(), axis_tolerance=2.5, gap_limit=10):
 groups=[]
 for wall in walls:
  a,b=np.array(wall['a'],float),np.array(wall['b'],float);d=b-a;length=np.linalg.norm(d)
  if length<1:continue
  u=d/length
  if u[0]<0 or (abs(u[0])<1e-6 and u[1]<0):a,b=b,a;u=-u
  match=None
  for g in groups:
   n=np.array([-g['u'][1],g['u'][0]])
   if abs(float(u@g['u']))>.9995 and max(abs(float((a-g['origin'])@n)),abs(float((b-g['origin'])@n)))<=axis_tolerance:match=g;break
  if match is None:
   match={'u':u,'origin':a,'members':[]};groups.append(match)
  match['members'].append((a,b,wall))
 result=[];repairs=[]
 def evidence(a,b):
  if image is None:return False
  n=max(2,int(np.linalg.norm(b-a)));pts=np.linspace(a,b,n);hits=[]
  for x,y in pts:
   x,y=int(round(x)),int(round(y));block=image[max(0,y-2):y+3,max(0,x-2):x+3]
   hits.append(bool(block.size and np.min(block)<230))
  return sum(hits)/len(hits)>=.85
 def opening_between(a,b):
  return any(min(np.linalg.norm(np.array(o['a'])-a),np.linalg.norm(np.array(o['b'])-b))<gap_limit for o in openings)
 for g in groups:
  u,o=g['u'],g['origin'];intervals=[]
  for a,b,w in g['members']:
   lo,hi=sorted([float((a-o)@u),float((b-o)@u)]);intervals.append((lo,hi,w))
  intervals.sort(key=lambda x:x[0]);start,end,seed=intervals[0];sources=set(seed.get('sourcePages',[]))
  for lo,hi,w in intervals[1:]:
   gap=lo-end;bridge=0<gap<=gap_limit and not opening_between(o+u*end,o+u*lo) and evidence(o+u*end,o+u*lo)
   if gap<=.5 or bridge:
    if bridge:repairs.append({'a':(o+u*end).tolist(),'b':(o+u*lo).tolist(),'reason':'기준 도면에 연속 잉크 근거'})
    end=max(end,hi);sources.update(w.get('sourcePages',[]))
   else:
    result.append({**seed,'a':(o+u*start).tolist(),'b':(o+u*end).tolist(),'sourcePages':sorted(sources)});start,end,seed=lo,hi,w;sources=set(w.get('sourcePages',[]))
  result.append({**seed,'a':(o+u*start).tolist(),'b':(o+u*end).tolist(),'sourcePages':sorted(sources)})
 # Snap only a short endpoint-to-endpoint corner. Never span a door-sized gap.
 for i,w in enumerate(result):
  for v in result[i+1:]:
   for ka in ['a','b']:
    for kb in ['a','b']:
     a,b=np.array(w[ka]),np.array(v[kb]);dist=np.linalg.norm(a-b)
     if 0<dist<=2.5:w[ka]=v[kb]=((a+b)*.5).tolist()
 return result,repairs

def audit(walls,openings=(),tolerance=4):
 def point_distance(p,w):
  a,b=np.array(w['a']),np.array(w['b']);v=b-a;t=np.clip(float((p-a)@v)/max(float(v@v),1e-9),0,1);return float(np.linalg.norm(p-a-v*t))
 dangling=[]
 for i,w in enumerate(walls):
  for end in ['a','b']:
   p=np.array(w[end]);attached=any(point_distance(p,v)<=tolerance for j,v in enumerate(walls) if j!=i)
   opening=any(min(np.linalg.norm(p-np.array(o['a'])),np.linalg.norm(p-np.array(o['b'])))<=tolerance for o in openings)
   if not attached and not opening:dangling.append({'wall':i,'point':p.tolist(),'reason':'벽 끝의 연결 또는 개구부 판독 필요'})
 orphan=[o for o in openings if not any(point_distance(np.array(o['a']),w)<=tolerance and point_distance(np.array(o['b']),w)<=tolerance for w in walls)]
 return {'unresolvedWallEnds':dangling,'unhostedOpenings':orphan,'readyForRouting':False,'reason':'방·복도·계단·승강기 연결 및 출입구 의미 검증 필요'}
