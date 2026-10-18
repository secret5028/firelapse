exec(open('work/inspect_terrace.py',encoding='utf-8-sig').read().split("print('floor'")[0])
from shapely.geometry import Polygon,Point,LineString
r=next(r for r in f['rooms'] if r['id']=='R27');print('glass',type(f['glass']),str(f['glass'])[:120]);print('opening sample',str(f['openings'][0])[:350])
g=Polygon(r['polys'][0]['o']);print('bounds',g.bounds)
for o in f['openings']:
 q=o.get('geometry_polys') or [dict(o=v,h=[]) for v in o['polys']]
 if any(Polygon(a['o']).distance(g)<.4 for a in q):print('opening',o['id'],o['kind'],o.get('rooms'),o.get('center'),[Polygon(a['o']).bounds for a in q])
for v in p['source_vectors']:
 q=[(x*f['scale']+f['shift'][0]-b['origin'][0],y*f['scale']+f['shift'][1]-b['origin'][1]) for x,y in v['points']]
 if len(q)>1 and LineString(q).distance(g)<.25:print('source',v['id'],v['category'],v.get('layer'),v.get('arc'),q[:2])

