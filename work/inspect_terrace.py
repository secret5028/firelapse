from pathlib import Path
import json,sys
sys.path.insert(0,str(Path('work/cad-deps').resolve()))
from PIL import Image,ImageDraw
from shapely.geometry import Polygon
j=Path('C:/Users/<user>/Desktop/소방 크로키 업-로컬웹앱/data/d018b4bb75da4475b1fd75447603c1a0/cad-output')
b=json.loads((j/'building.json').read_text('utf8'));f=next(f for f in b['floors'] if f['name']=='3F');p=json.loads((j/'3F/plan.json').read_text('utf8'))
print('floor',f.keys());print('bands',[(x['kind'],x['z0'],x['z1'],len(x['polys'])) for x in f['bands']]);print('provenance',p['provenance'])
print('rooms',[(r['id'],r.get('name'),Polygon(r['polys'][0]['o']).centroid.coords[:]) for r in f['rooms']]);print('plan source',p['src'])
pts=[q for a in f['slab'] for q in a['o']];x0=min(q[0] for q in pts);x1=max(q[0] for q in pts);y0=min(q[1] for q in pts);y1=max(q[1] for q in pts);s=min(1300/(x1-x0),1000/(y1-y0));at=lambda q:(60+(q[0]-x0)*s,1060-(q[1]-y0)*s)
im=Image.new('RGB',(1450,1120),'white');d=ImageDraw.Draw(im)
for r in f['rooms']:
 for g in r['polys']:d.polygon([at(q) for q in g['o']],fill='#e5eedc',outline='#abbbaa')
 c=Polygon(r['polys'][0]['o']).representative_point();d.text(at((c.x,c.y)),r['id'],fill='black')
for v in p['source_vectors']:
 pts=[(q[0]*f['scale']+f['shift'][0]-b['origin'][0],q[1]*f['scale']+f['shift'][1]-b['origin'][1]) for q in v['points']]
 if len(pts)>1:d.line([at(q) for q in pts],fill={'wall':'#283c61','door':'green','window':'#00aad0'}.get(v['category'],'#cccccc'),width=1)
im.save('work/3f-inspect.png')
