import json
from pathlib import Path
from shapely.geometry import LineString
from shapely.ops import unary_union
p=Path('work/cad-input/model.json');d=json.loads(p.read_text(encoding='utf-8'))
for f in d[:2]:
 seg=[]
 for l in f['lines']:
  if l['type']!='walls':continue
  for a,b in zip(l['p'],l['p'][1:]):
   line=LineString([a,b])
   if line.length>.08:seg.append(line.buffer(.035,cap_style=2,join_style=2))
 raw=unary_union(seg);solid=raw.buffer(.14,join_style=2).buffer(-.14,join_style=2).simplify(.01,preserve_topology=True)
 polys=list(solid.geoms) if solid.geom_type=='MultiPolygon' else [solid]
 f['wallProfiles']=[{'outer':list(p.exterior.coords),'holes':[list(h.coords) for h in p.interiors]} for p in polys if p.area>.004]
 print(f['name'],len(seg),'segments ->',len(f['wallProfiles']),'wall regions')
p.write_text(json.dumps(d,ensure_ascii=False),encoding='utf-8')
p=Path('work/cad_viewer.js');s=p.read_text(encoding='utf-8');a=s.index("if(l.type==='walls'&&i<2){");b=s.index("if(['doors','windows']",a);s=s[:a]+s[b:];s=s.replace("if(l.type!=='stairs')poly", "if(l.type!=='stairs'&&l.type!=='walls')poly")
a=s.index('// Approximate floor outline')
new='''if(i<2)for(const profile of f.wallProfiles||[]){const sh=new T.Shape(profile.outer.map(([x,z])=>new T.Vector2(x,-z)));for(const hole of profile.holes)sh.holes.push(new T.Path(hole.map(([x,z])=>new T.Vector2(x,-z))));const geo=new T.ExtrudeGeometry(sh,{depth:i===0?5:4,bevelEnabled:false});geo.rotateX(-Math.PI/2);const mesh=new T.Mesh(geo,wallmat);mesh.position.y=f.y;ls.walls.add(mesh);selectable.push(mesh);const edge=new T.LineSegments(new T.EdgesGeometry(geo,30),new T.LineBasicMaterial({color:0x8dc5df,transparent:true,opacity:.65}));edge.position.y=f.y;ls.outlines.add(edge)}
'''
s=s[:a]+new+s[a:];p.write_text(s,encoding='utf-8')
p=Path('work/package_cad.py');s=p.read_text(encoding='utf-8');a=s.index("p=Path('outputs/");new='''# Reuse the established viewer shell rather than a separate CAD interface.
import re
base=(root/'factory.html').read_text(encoding='utf-8')
css=base.split('<style>',1)[1].split('</style>',1)[0]
side=html.split('<aside>',1)[1].split('</aside>',1)[0]
side=re.sub(r'<h1>.*?</h1><small>.*?</small><p>.*?</p>','',side,count=1)
side=side.replace('<p><button id="reset">시점 복원</button><button id="top">위에서</button></p>','')
side=side.replace('원본 DWG의 선·곡선·블록을 추출했습니다.','원본 DWG의 선·곡선·블록을 추출했습니다. 인접한 벽 선은 통합 영역으로 정리했으며 두께·개구부 상세는 검토값입니다.')
side='<section><h2>표시 레이어</h2>'+side.replace('<button id="start">','</section><section><h2>진입 경로</h2><button id="start">',1)+'</section>'
html='<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>소방공간뷰 · 두산위브 강화2지구</title><style>'+css+'#view{width:100%;height:100%}#view canvas{display:block;touch-action:none}label:has(#opacity){display:block}.top{z-index:2}#status{display:block;color:#b7cadb;font-size:12px;line-height:1.7}aside button{margin:3px}#opacityValue{float:right}</style><body><header><h1>소방공간뷰 <small> / 두산위브 강화2지구 · CAD 8장</small></h1></header><main><aside>'+side+'</aside><div id="stage"><div id="view"></div><div class="top"><div class="dock"><button data-floor="all" class="active">전체</button><button data-floor="2">지붕</button><button data-floor="1">2층</button><button data-floor="0">1층</button></div><div class="viewtools"><button id="top">위에서</button><button id="reset">시점 복원</button></div></div><div class="bottom"><span>클릭 중심 이동 · 드래그 회전 · Shift 이동 · 휠 확대</span></div></div></main><script>'+boot+'</script></body></html>'
''';s=s[:a]+new+s[a:];p.write_text(s,encoding='utf-8')
