exec(open('work/inspect_terrace.py',encoding='utf-8-sig').read().split("print('floor'")[0])
sys.path.insert(0,str(Path('work/cad-web/cad_engine').resolve()))
from cad_evidence import geometry
r=next(r for r in f['rooms'] if r['id']=='R27');g=geometry(r['polys']);u=next(q for q in b['floors'] if q['name']=='4F');cover=geometry(u['slab']);print('terrace_area',g.area,'overlap_upper',g.intersection(cover).area,'upper_bounds',cover.bounds)
for fl in b['floors']:
 upper=next((q for q in b['floors'] if abs(q['z']-fl['z']-fl['h'])<.02),None)
 if upper:
  uncovered=geometry(fl['slab']).difference(geometry(upper['slab']).buffer(.25));print(fl['name'],'exposed area',round(uncovered.area,2),'rooms mostly exposed',[(r['id'],round(geometry(r['polys']).area,1),round(geometry(r['polys']).intersection(uncovered).area/geometry(r['polys']).area,2)) for r in fl['rooms'] if geometry(r['polys']).area>10 and geometry(r['polys']).intersection(uncovered).area/geometry(r['polys']).area>.8])
