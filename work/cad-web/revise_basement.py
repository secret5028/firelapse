from pathlib import Path
p=Path('work/app.js');s=p.read_text(encoding='utf-8')
s=s.replace('const floorGroups=[],','const basementGroups={},basementOverlays=[];\nconst floorGroups=[],')
a=s.index('const ground=new THREE.GridHelper')
s=s[:a]+'''// 지하층은 원본의 제한된 외곽만 재구성. 높이는 임시 -3.6m.
for(const id of ['B','C']){const g=new THREE.Group();scene.add(g);g.visible=false;basementGroups[id]=g;const w=id==='B'?10.7:11.4,d=id==='B'?18.8:16.0;
const info={name:id+'동 B1 · 지하층 외곽',body:(id==='B'?'12':'16')+'쪽 지하층 평면의 외곽을 근사한 것입니다. 바닥 -3.6m는 임시값이며 내부 설비·개구부·지상 연결 경로는 아직 구현하지 않았습니다.'};
const slab=box(g,w/2,-H-.1,d/2,w,.2,d,mat('#72a5b7',.3),info);outline(slab);layerNodes.structure.push(slab);
for(const [x,z,ww,dd]of [[w/2,0,w,.18],[w/2,d,w,.18],[0,d/2,.18,d],[w,d/2,.18,d]]){const wall=box(g,x,-H+1.4,z,ww,2.8,dd,mat('#bfdee7',.35),info);outline(wall);layerNodes.structure.push(wall)}
const grade=box(g,w/2,0,d/2,w+8,.025,d+8,mat('#72bea0',.075));outline(grade,'#7acead');
const frame=new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(-2,-H,0),new THREE.Vector3(-2,0,0)]),new THREE.LineBasicMaterial({color:'#b5f5d4'}));g.add(frame);
label(g,'지면 ±0.0m',w/2,.2,-3,'#9aebc7',.9);label(g,'B1 · -3.6m (임시)',w/2,-H+.3,d+2,'#a4ddeb',1);
const texture=new THREE.TextureLoader().load(window.ASSETS['basement'+id]);texture.colorSpace=THREE.SRGBColorSpace;const overlay=new THREE.Mesh(new THREE.PlaneGeometry(w,d),new THREE.MeshBasicMaterial({map:texture,transparent:true,opacity:.85,side:THREE.DoubleSide,depthWrite:false}));overlay.rotation.x=-Math.PI/2;overlay.position.set(w/2,-H+.015,d/2);overlay.visible=false;g.add(overlay);basementOverlays.push(overlay);
}
function updateFloorDock(){const dock=$('floorDock');dock.innerHTML='';const caption=document.createElement('span');caption.textContent='층';dock.appendChild(caption);
const add=(title,active,fn)=>{const b=document.createElement('button');b.textContent=title;b.className=active?'active':'';b.onclick=fn;dock.appendChild(b)};
if(state.mode==='detail'){for(const f of ['all','2','1'])add(f==='all'?'전체':f+'F',state.floor===f,()=>setFloor(f));}
else if(['B','C'].includes(state.building)){add('전체 배치',state.mode==='site',()=>setMode('site'));add('B1',state.mode==='basement',()=>showBasement(state.building));}
else add('D동 1·2층',false,()=>setMode('detail'));
$('gradeNote').style.display=state.mode==='basement'?'block':'none';}
function showBasement(id){setMode('site');state.building=id;state.mode='basement';state.pick=false;site.visible=false;model.visible=false;routesGroup.visible=targetGroup.visible=false;for(const [key,g]of Object.entries(basementGroups))g.visible=key===id;
$('building').value=id;$('viewTitle').textContent=id+'동 · B1';$('viewSubtitle').textContent='지하층 외곽 / 바닥 -3.6m 임시';$('status').textContent=(id==='B'?'12':'16')+'쪽 지하층 · 내부·지상 연결 경로 미구현';$('routeCount').textContent='0';$('routes').innerHTML='';$('targetName').textContent='지하층 · 경로 미구현';$('routeWarning').textContent='외곽과 원본 도면 대조';$('underlay').disabled=false;for(const o of basementOverlays)o.visible=$('underlay').checked;updateFloorDock();resetCamera();}
''' + s[a:]
s=s.replace("const n=new THREE.Vector3(state.mode==='site'?0:.707,0,state.mode==='site'?-1:-.707);", "const n=state.mode==='basement'?new THREE.Vector3(state.building==='B'?1:0,0,state.building==='B'?0:-1):new THREE.Vector3(state.mode==='site'?0:.707,0,state.mode==='site'?-1:-.707);")
s=s.replace('function resetCamera(top=false){if(', "function resetCamera(top=false){if(state.mode==='basement'){target.set(state.building==='B'?5.35:5.7,-1.8,state.building==='B'?9.4:8);cam.radius=42;cam.theta=state.building==='B'?-Math.PI/2:0;cam.phi=top?.02:.92;updateCamera();return}if(")
s=s.replace('renderRoutes();}\nfunction setMode', 'renderRoutes();updateFloorDock();}\nfunction setMode')
s=s.replace('function setMode(mode){state.mode=mode;', "function setMode(mode){for(const g of Object.values(basementGroups))g.visible=false;state.mode=mode;")
s=s.replace('renderRoutes();resetCamera();}\nfunction focusMass', 'renderRoutes();resetCamera();updateFloorDock();}\nfunction focusMass')
s=s.replace("$('viewSubtitle').textContent='내부 미구현 / 높이 임시 적용'}", "$('viewSubtitle').textContent='내부 미구현 / 높이 임시 적용';updateFloorDock()}")
s=s.replace("$('underlay').onchange=e=>overlayMeshes.forEach(o=>o.visible=e.target.checked)", "$('underlay').onchange=e=>[...overlayMeshes,...basementOverlays].forEach(o=>o.visible=e.target.checked)")
s=s.replace("(state.mode==='detail'?model:site).children", "(state.mode==='detail'?model:state.mode==='basement'?basementGroups[state.building]:site).children")
s=s.replace('ready:true};','showBasement,basementGroups,ready:true};')
p.write_text(s,encoding='utf-8')
p=Path('work/viewer.html');h=p.read_text(encoding='utf-8')
h=h.replace('<div id="fatal"></div>', '<div id="floorDock" class="floorDock"></div><div id="gradeNote">地面 ±0.0m<br><strong>B1 −3.6m</strong><small>深さは仮定</small></div><div id="fatal"></div>')
h=h.replace('地面','지면').replace('深さは仮定','깊이 임시값')
h=h.replace('<option value="10">', '<option value="12">12쪽 · B동 지하층</option><option value="16">16쪽 · C동 지하층</option><option value="10">')
h=h.replace('스튜디오 B동 · 외곽','스튜디오 B동 · 외곽 / B1').replace('스튜디오 C동 · 외곽','스튜디오 C동 · 외곽 / B1')
h=h.replace('</style>', '.floorDock{position:absolute;top:180px;right:20px;display:flex;flex-direction:column;gap:6px;background:#0f2036eb;padding:10px;border:1px solid #496077;border-radius:9px;min-width:70px}.floorDock>span{text-align:center;color:#93b0c6;font-size:12px}#gradeNote{display:none;position:absolute;left:20px;bottom:80px;padding:10px 14px;border:1px solid #69b89b;border-radius:7px;background:#102c30de;color:#99eac5;line-height:1.8;font-size:13px}#gradeNote small{display:block;font-size:11px;color:#a1bcb6}@media(max-width:720px){.floorDock{top:165px;right:12px;padding:6px}}</style>')
h=h.replace('<li>경로는 도면을', '<li>B·C동은 도면에 확인되는 지하층의 제한된 외곽을 추가했습니다. 지면 0m, 지하 바닥 -3.6m는 임시 기준입니다. 지하층의 상세 구조·설비·지상 연결 경로는 미구현이며, D동에는 지하층을 추가하지 않았습니다.</li><li>경로는 도면을')
p.write_text(h,encoding='utf-8')
p=Path('work/package_viewer.py');s=p.read_text(encoding='utf-8').replace('[4,10,20,21,33]', '[4,10,12,16,20,21,33]')
s=s.replace("assets[str(n)]=encode(im)", "assets[str(n)]=encode(im)\n    if n in [12,16]:\n        w,h=im.size\n        rect=(.566,.501,.700,.826) if n==12 else (.148,.537,.239,.716)\n        crop=im.crop(tuple(int(v*(w if i%2==0 else h)) for i,v in enumerate(rect)))\n        assets['basement'+('B' if n==12 else 'C')]=encode(crop)")
p.write_text(s,encoding='utf-8')
p=Path('work/folder_review.html');s=p.read_text(encoding='utf-8')
s=s.replace('floor< -20||floor>150', 'floor< -20||floor===0||floor>150')
s=s.replace('<label>동 / 층</label>', '<label>동 / 층 <span class="muted">지하 1층 = -1</span></label>')
s=s.replace('for(const p of floors){const all=', 'for(const p of floors){y=(p.floor<0?p.floor:p.floor-1)*p.height;const all=')
s=s.replace("text('수동 보정 구조 · 층별 원점은 외곽 최소 좌표 기준 · 동간 배치·방위·경로 미확정')", "text('지면 0m · 지하층은 음수 높이 · 층고 임시 / 동간 배치·방위·경로 미확정')")
s=s.replace("const bounds=new T.Box3().setFromObject(group);bounds.getCenter(target);", "const bounds=new T.Box3().setFromObject(group);const size=bounds.getSize(new T.Vector3()),center=bounds.getCenter(new T.Vector3());const grade=new T.Mesh(new T.PlaneGeometry(size.x+8,size.z+8),new T.MeshBasicMaterial({color:'#76c8a5',transparent:true,opacity:.10,side:T.DoubleSide,depthWrite:false}));grade.rotation.x=-Math.PI/2;grade.position.set(center.x,0,center.z);group.add(grade);bounds.getCenter(target);")
p.write_text(s,encoding='utf-8')
print('Added permanent floor dock and below-grade B/C basement outlines; negative floor elevations in general editor.')
