from pathlib import Path
import sys,json,shutil,hashlib
root=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(root/'work/cad-deps'),str(root/'work/cad-web/cad_engine')]
from cad_model_transport import prepare_model,geometry
from shapely.ops import unary_union
job=Path('C:/Users/예방/Desktop/소방 크로키 업-로컬웹앱/data/d018b4bb75da4475b1fd75447603c1a0/cad-output')
out=root/'outputs/CAD-테라스-v13';out.mkdir(exist_ok=True)
b=json.loads((job/'building.json').read_text('utf8'));plans={f['name']:json.loads((job/f['name']/'plan.json').read_text('utf8')) for f in b['floors']}
m,a=prepare_model(b,plans);f=next(f for f in m['floors'] if f['name']=='3F');old=next(f for f in b['floors'] if f['name']=='3F');t=f['outdoor_spaces'][0];mask=geometry(t['boundary_mask']);sky=geometry(t['open_sky_polys'])
assert m['movement_connections']==b['movement_connections']
for x,y in zip(b['floors'],m['floors']):
 assert x['slab']==y['slab'] and x['transport']==y['transport']
 if x['name']!='3F':
  for k in ['bands','glass','openings','rooms','ceiling','render_slab','render_ceiling']:assert x[k]==y[k],(x['name'],k)
for band in f['bands']:
 if band['z1']>1.1:assert geometry(band['polys']).intersection(mask).area<1e-7
for k in ('ceiling','render_ceiling'):assert geometry(f[k]).intersection(sky).area<1e-7
st=next(t for t in m['structural_tops'] if t['from_floor']=='3F')
for k in ('roof_polys','ceiling_polys'):assert geometry(st[k]).intersection(sky).area<1e-7
assert abs(geometry(old['slab']).area-geometry(f['slab']).area)<1e-8
again,_=prepare_model(m,plans);assert again==m,'idempotence'
report=dict(terrace_area_m2=geometry(t['polys']).area,parapet_height_m=1.1,prior_storey_height_m=f['h'],changed_openings=t['changed_openings'],slab_retained=True,shared_facade_retained=True,terrace_ceiling_removed=True,other_floors_unchanged=True,movement_connections=len(m['movement_connections']),idempotence=True,extraction_rerun=False,height_is_display_default=True)
(out/'building.json').write_text(json.dumps(m,ensure_ascii=False),'utf8');(out/'검증결과.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');shutil.copy2(root/'work/cad-web/cad_engine/cad_model_transport.py',out/'cad_model_transport.py');shutil.copy2(root/'work/3f-inspect.png',out/'3F-원본대조.png');print(json.dumps(report,ensure_ascii=False))
