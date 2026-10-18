import json,pathlib,sys,shutil,re,hashlib
W=pathlib.Path(__file__).resolve().parent;C=pathlib.Path('C:/Users/예방/Documents/Codex/2026-09-07/2/CAD3D');sys.path[:0]=[str(W/'cad-deps'),str(C)]
from cad_model_transport import prepare_model
OLD=W.parent/'outputs/CAD-평면연결-v9';OUT=W.parent/'outputs/CAD-모델링-v10';OUT.mkdir(exist_ok=True)
b=json.loads((OLD/'building.json').read_text(encoding='utf8'));plans={f['name']:json.loads((OLD/('office-'+f['name'])/'plan.json').read_text(encoding='utf8')) for f in b['floors']}
model,audit=prepare_model(b,plans)
(OUT/'building.json').write_text(json.dumps(model,ensure_ascii=False),encoding='utf8');(OUT/'위치검사.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
template=(C/'viewer_template.html').read_text(encoding='utf8')
template=template.replace('ext(f.slab,-0.2,0,mat.slab)','ext(f.render_slab||f.slab,-0.2,0,mat.slab)').replace('ext(f.ceiling,0,0.03,mat.ceil)','ext(f.render_ceiling||f.ceiling,0,0.03,mat.ceil)').replace('new THREE.ShapeGeometry(r.polys.map(shp))','new THREE.ShapeGeometry((r.render_polys||r.polys).map(shp))')
start=template.index('// ---- 수직 공간(');end=template.index('function stepLeaves()',start)
transport=(C/'transport_view.js').read_text(encoding='utf8')
ui='''
const transport=addTransportGeometry(THREE,B,groups,ext);
function syncTransport(){const master=document.getElementById('sh').checked,si=B.floors.findIndex(f=>f.name===selFloor),above=document.getElementById('above').checked;
 for(const g of transport.roots){const fi=g.userData.floorIndex,kind=g.userData.transportKind,show=selFloor==='all'||fi===si||(above&&fi>si);g.visible=show&&master&&document.getElementById('show_'+kind).checked;}}
document.getElementById('sh').onchange=syncTransport;
for(const id of ['stair','elev','ramp','anchor'])document.getElementById('show_'+id).onchange=syncTransport;
function rampSlope(){const p=+document.getElementById('ramp_slope').value;document.getElementById('ramp_value').textContent=p+'%';transport.slope(p,document.getElementById('ramp_reverse').checked);}
document.getElementById('ramp_slope').oninput=rampSlope;document.getElementById('ramp_reverse').onchange=rampSlope;
'''
template=template[:start]+transport+'\n'+ui+'\n'+template[end:]
template=template.replace('계단실·승강로(층 관통)','계단·승강기·램프 표시')
template=template.replace('<h2>검사(공리)</h2>', '''<label><input id="show_stair" type="checkbox" checked> 계단·계단참</label><label><input id="show_elev" type="checkbox" checked> 승강기·승강장 문</label><label><input id="show_ramp" type="checkbox" checked> 차량 램프</label><label><input id="show_anchor" type="checkbox"> 원본 대조 경계(빨강: 기호 / 청록: 실)</label><label>램프 경사 <input id="ramp_slope" type="range" min="0" max="25" step="1" value="10"><span id="ramp_value">10%</span></label><label><input id="ramp_reverse" type="checkbox"> 램프 상승 방향 반전</label><p style="font-size:11px">램프는 확인된 곡선 구간입니다. 경사·상승 방향은 표시용 가정이며 상단 연결층은 미확정입니다.</p><h2>검사(공리)</h2>''')
# Respect floor and layer selection after the old viewer resets child visibility.
template=template.replace('  syncLabels();\n',"  syncLabels();applyCeil();syncTransport();\n")
template=template.replace('<h1>CAD 3D 층 모델</h1>','<h1>2단계 · CAD 3D 모델 v10</h1><p><a href="../CAD-평면연결-v9/index.html">1단계 평면</a> · <a href="위치대조.html">계단·램프 위치 대조</a></p>')
# Start at basement, with translucent walls, for the requested ramp/stair review.
template=template.replace('function animate()',"function animate()")
idx=template.rfind('</script>')
template=template[:idx]+"\nselFloor='B1';document.getElementById('xr').checked=true;setXray(true);applyFloor();syncTransport();\n"+template[idx:]
template=template.replace('/*__DATA__*/null',json.dumps(model,ensure_ascii=False))
(OUT/'index.html').write_text(template,encoding='utf8')
# Preserve reproducible source/template. No engine or source-plan mutation.
code=OUT/'code';code.mkdir(exist_ok=True)
for n in ['cad_model_transport.py','transport_view.js','viewer_template.html']:shutil.copy2(C/n,code/n)
shutil.copy2(__file__,code/'build_v10.py')
print('model generated',len(model['floors']),'floors',sum(len(f['transport']) for f in model['floors']),'core positions')
