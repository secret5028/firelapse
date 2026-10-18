exec((__import__('pathlib').Path(__file__).parent/'inspect_raw8.py').read_text(encoding='utf8').split('for name,')[0])
from shapely.geometry import LineString,box,Point
from cad_evidence import geometry,polygon_parts
p=json.loads((W.parent/'outputs/CAD-벽공리-v5/office-1F/plan.json').read_text(encoding='utf8'))
for name,xy in [('D16',(14064.875,-1761.209)),('W76',(14060.44,-1761.35)),('D18',(14063.885,-1775.135)),('W89',(13993.31,-1781.43))]:
 print('\n',name)
 for i,q in enumerate(ps):
  if q.layer not in ('DOOR','WID','4WID','WINE','우수드레인','WALL-UNKNOWN','0-내벽고정식'):continue
  ls=LineString([(a*.001,b*.001) for a,b in q.pts])
  if ls.distance(Point(xy))>.3:continue
  print(i,q.layer,q.kind,'arc',q.arc,'closed',q.closed,'handle',q.source,'block',ins[q.ins]['name'] if q.ins is not None else None,'bounds',tuple(round(v,3) for v in ls.bounds))
 print('rooms',[(r['id'],round(geometry(polygon_parts(r)).distance(Point(xy)),3)) for r in p['rooms'] if geometry(polygon_parts(r)).distance(Point(xy))<2])
for e in doc.modelspace():
 if e.dxftype() not in ('TEXT','MTEXT'):continue
 pos=e.dxf.insert; x,y=pos.x*.001,pos.y*.001
 if (14048<x<14069 and -1778<y<-1757) or (13989<x<13997 and -1785<y<-1778):
  print('TEXT',x,y,e.dxf.layer,e.plain_text())
