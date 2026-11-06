import pathlib,sys,json
W=pathlib.Path(__file__).resolve().parent;CAD=pathlib.Path(r'C:\Users\<user>\Documents\Codex\2026-09-07\2\CAD3D');sys.path[:0]=[str(W/'cad-deps'),str(CAD)]
from cad_evidence import geometry,polygon_parts,opening_parts
def compare(old,p):
 gs={r['id']:geometry(polygon_parts(r)) for r in p['rooms']};mapping={}
 for r in old['rooms']:
  a=geometry(polygon_parts(r));mapping[r['id']]=max(gs,key=lambda k:a.intersection(gs[k]).area)
 rows=[]
 for o in old['openings']:
  if o.get('connection_status') not in ('interior','exterior'):continue
  g=geometry(opening_parts(o));near=sorted(p['openings'],key=lambda n:g.centroid.distance(geometry(opening_parts(n)).centroid))
  n=near[0];ng=geometry(opening_parts(n));d=g.centroid.distance(ng.centroid)
  expected=set(mapping.get(s,s) for s in o['sides'])
  if d>.3 or set(n.get('sides',[]))!=expected:
   rows.append(dict(old=o['id'],new=n['id'],distance_m=round(d,3),before=o['sides'],expected=sorted(expected),now=n.get('sides')))
 return dict(old_rooms=len(old['rooms']),new_rooms=len(p['rooms']),changed=rows)
if __name__=='__main__':
 for folder in [W/'cad-v7-runs',W/'cad-v7-regression']:
  for out in folder.glob('*'):
   old=W.parent/'outputs/CAD-문판정-v6'/out.name/'plan.json'
   if not old.exists() or not (out/'plan.json').exists():continue
   result=compare(json.loads(old.read_text(encoding='utf8')),json.loads((out/'plan.json').read_text(encoding='utf8')))
   print(out.name,json.dumps(result,ensure_ascii=False),flush=True)
