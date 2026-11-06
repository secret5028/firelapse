from pathlib import Path
import shutil,re,json,urllib.request
W=Path(__file__).resolve().parent;S=W/'cad-web';S.mkdir(exist_ok=True)
OLD=Path('C:/Users/<user>/Desktop/소방 크로키 업-로컬웹앱');C=Path('C:/Users/<user>/Documents/Codex/2026-09-07/2/CAD3D')
for p in (OLD/'개발/work').glob('*.py'):shutil.copy2(p,S/p.name)
R=S/'local-resources';R.mkdir(exist_ok=True)
for p in (OLD/'_internal').iterdir():
 if p.suffix in ('.html','.js','.ps1','.json'):shutil.copy2(p,R/p.name)
shutil.copytree(OLD/'_internal/cad-tools',R/'cad-tools',dirs_exist_ok=True)
engine=S/'cad_engine';engine.mkdir(exist_ok=True)
for p in C.iterdir():
 if p.suffix in ('.py','.json','.html','.js') and not p.name.startswith('test_'):shutil.copy2(p,engine/p.name)
profiles=engine/'profiles';profiles.mkdir(exist_ok=True)
for floor in ['1F','PH']:shutil.copy2(W/f'office-{floor}-review-v7.json',profiles/f'office-{floor}.json')
v=(W.parent/'outputs/CAD-모델링-v10/index.html').read_text('utf8')
v=re.sub(r'const B=.*?;\nfunction ceilStateDefault',"const B=await (await fetch('building.json')).json();\nfunction ceilStateDefault",v,count=1,flags=re.S)
v=v.replace("selFloor='B1'","selFloor=B.floors[0].name").replace('../CAD-평면연결-v9/index.html','plans.html').replace('위치대조.html','plans.html').replace('계단·램프 위치 대조','층별 추출 결과').replace('2단계 · CAD 3D 모델 v10','2단계 · 3D 모델')
v=v.replace('https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js','/cad-assets/three.module.js').replace('https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/','/cad-assets/addons/')
(engine/'integrated_viewer.html').write_text(v,'utf8')
vendor=R/'cad-assets';vendor.mkdir(exist_ok=True)
for rel,src in [('three.module.js','build/three.module.js'),('addons/controls/OrbitControls.js','examples/jsm/controls/OrbitControls.js'),('addons/renderers/CSS2DRenderer.js','examples/jsm/renderers/CSS2DRenderer.js'),('addons/exporters/OBJExporter.js','examples/jsm/exporters/OBJExporter.js')]:
 dst=vendor/rel;dst.parent.mkdir(parents=True,exist_ok=True)
 if not dst.exists():dst.write_bytes(urllib.request.urlopen('https://cdn.jsdelivr.net/npm/three@0.160.0/'+src,timeout=30).read())
(vendor/'LICENSE').write_bytes(urllib.request.urlopen('https://cdn.jsdelivr.net/npm/three@0.160.0/LICENSE',timeout=30).read())
print(S)
