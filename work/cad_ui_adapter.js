// Restore the established croquis viewer interaction without changing CAD geometry.
const $ui=id=>document.getElementById(id);
const uiStyle=document.createElement('style');uiStyle.textContent=`
:root{--bg:#0c1b28;--fg:#e6eff6;--pn:#132939;--ln:#355063;--ac:#efd16b}
body{overflow:hidden;background:#0c1b28}button,input{accent-color:#edc85f}
#v{inset:64px 236px 0 0;overflow:hidden;touch-action:none}
#p{inset:64px 0 0 auto;width:236px;max-height:none;border-radius:0;border-width:0 0 0 1px;padding:12px;box-shadow:none}
#p h2{font-size:13px;margin-top:16px}#p details{border-top:1px solid var(--ln);padding:12px 0}#p summary{cursor:pointer;color:#d8e5ed}
#p label{margin:9px 0}#p button,.uiTop button,.viewTools button{background:#19394d;color:#e6eff6;border:1px solid #3e6176;border-radius:5px;padding:7px 10px;cursor:pointer}
.uiTop{position:fixed;inset:0 0 auto;height:64px;display:flex;align-items:center;gap:12px;padding:0 14px;background:#132939;border-bottom:1px solid #355063;box-sizing:border-box}
.uiTop strong{color:#efd16b;white-space:nowrap}.uiTop #fbtn{flex-wrap:nowrap!important;overflow-x:auto;align-items:center;flex:1;white-space:nowrap}
.uiTop #fbtn button{min-width:44px;height:36px}.uiTop button[aria-pressed=true]{background:#edc85f;color:#172a35;border-color:#edc85f;font-weight:700}
.viewTools{position:absolute;right:14px;top:12px;z-index:2;display:flex;gap:5px}.viewHint{position:absolute;bottom:12px;left:12px;color:#c8dae7;background:#102737df;padding:8px 12px;border-radius:5px;pointer-events:none;font-size:12px}
#p .small{color:#a8bfce;font-size:11px;line-height:1.6}.lb{background:#142b3cce}.uiTop a{color:#cee4f5;text-decoration:none}.layerTitle{font-weight:700;color:#efd16b}
@media(max-width:750px){#v{right:190px}#p{width:190px}.uiTop strong{display:none}.viewHint{max-width:190px;font-size:11px}.viewTools{right:7px}}
`;document.head.append(uiStyle);
const panel=$ui('p'),advanced=document.createElement('details');
advanced.innerHTML='<summary>모델 상세 설정·저장</summary>';
while(panel.firstChild)advanced.append(panel.firstChild);
panel.innerHTML=`<div class="layerTitle">표시 레이어</div>
<label><input id="layer_wall" type="checkbox" checked> 벽체</label>
<label><input id="layer_opening" type="checkbox" checked> 출입문·창문</label>
<label><input id="layer_floor" type="checkbox" checked> 바닥·지붕</label>
<label><input id="layer_outline" type="checkbox" checked> 벽 외곽선</label>
<div id="coreLayers"></div><div id="nameLayer"></div>
<label><input id="layer_grid" type="checkbox" checked> 지표면 격자 (1m)</label>
<label><input id="layer_reference" type="checkbox" checked> 소방차·사람 크기 기준</label>
<h2>벽 투명도 <span id="opacityValue">55%</span></h2>
<input id="wallTransparency" aria-label="벽 투명도" type="range" min="0" max="100" value="55" style="width:100%">
<p class="small" id="groundInfo"></p><p class="small">금색 계단은 두 구간의 단과 계단참으로 표시합니다. 계단·승강기 위치는 추출 모델을 그대로 사용합니다.</p>`;
panel.append(advanced);
for(const id of ['show_stair','show_elev','show_ramp'])$ui('coreLayers').append($ui(id).closest('label'));
$ui('nameLayer').append($ui('rl').closest('label'));
const topBar=document.createElement('nav');topBar.className='uiTop';topBar.innerHTML='<strong>소방 크로키 업</strong><a href="plans.html">평면도</a>';
topBar.append($ui('fbtn'));document.body.append(topBar);
const toolbar=document.createElement('div');toolbar.className='viewTools';toolbar.innerHTML='<button id="resetView">시점 복원</button><button id="zoomIn" aria-label="확대">＋</button><button id="zoomOut" aria-label="축소">－</button>';
toolbar.append($ui('top'),$ui('iso'));el.append(toolbar);
const hint=document.createElement('div');hint.className='viewHint';hint.textContent='드래그: 회전 · Shift+드래그: 이동 · 휠: 확대/축소\n터치: 한 손가락 회전 · 두 손가락 이동/확대';hint.style.whiteSpace='pre-line';el.append(hint);
S.background.set('#0c1b28');O.screenSpacePanning=true;O.minDistance=1;O.maxDistance=2000;
O.mouseButtons={LEFT:THREE.MOUSE.ROTATE,MIDDLE:THREE.MOUSE.DOLLY,RIGHT:THREE.MOUSE.PAN};
O.touches={ONE:THREE.TOUCH.ROTATE,TWO:THREE.TOUCH.DOLLY_PAN};
// Reuse the original reference vehicle/person geometry. Rotate its Y-up frame
// into CAD Z-up, and place the ground at 1F, NOT at the lowest basement slab.
const groundFloor=B.floors.find(f=>f.name==='1F');
const groundZ=groundFloor?.z??0;
const bounds=new THREE.Box3();B.floors.forEach(f=>f.slab.forEach(p=>p.o.forEach(([x,y])=>bounds.expandByPoint(new THREE.Vector3(x,y,f.z)))));
const center=bounds.getCenter(new THREE.Vector3());
const references=new THREE.Group();references.rotation.x=Math.PI/2;references.position.z=groundZ;S.add(references);
addSceneReferences(THREE,references,[{floorOutline:[[bounds.min.x,0],[bounds.max.x,0],[bounds.max.x,bounds.max.y-bounds.min.y]],origin:[0,0],scale:1}]);
const groundGrid=references.children[0],referenceObjects=references.children[1];
groundGrid.position.set(center.x,-.19,-center.y);
const groundPoints=(groundFloor||B.floors[0]).slab.flatMap(p=>p.o);
referenceObjects.position.set((Math.min(...groundPoints.map(p=>p[0]))+Math.max(...groundPoints.map(p=>p[0])))/2,-.16,-Math.min(...groundPoints.map(p=>p[1]))+5);
$ui('groundInfo').textContent=groundFloor?'地表 기준: 1F · 격자 1칸 = 1m'.replace('地表','지표면'):'지표면: 모델 기준 높이 (1F 도면 없음) · 격자 1m';
// Separate floor tint, walls, openings and outline visibility. Never restore all
// child visibility blindly when switching floors, which previously reset layers.
const outlines=[];
groups.forEach(G=>{for(const m of [...G.children]){
  if(m.isMesh&&XR.some(k=>m.material===mat[k])){
    const edge=new THREE.LineSegments(new THREE.EdgesGeometry(m.geometry,30),new THREE.LineBasicMaterial({color:0x9bb8c9,transparent:true,opacity:.45}));
    edge.userData.cadOutline=true;G.add(edge);outlines.push(edge);
  }
}});
const shownFloors=B.floors.map(()=>true);
[...$ui('fl').children].filter((_,i)=>i%2===0).forEach((label,i)=>{label.querySelector('input').onchange=e=>{shownFloors[i]=e.target.checked;applyFloor()}});
const visibleByName=o=>{for(let x=o;x;x=x.parent)if(!x.visible)return false;return true};
applyFloor=function(){
 const si=B.floors.findIndex(f=>f.name===selFloor),above=$ui('above').checked;
 groups.forEach((G,i)=>{
  G.visible=shownFloors[i]&&(selFloor==='all'||i===si||(above&&i>si));
  for(const obj of G.children){
   if(obj.userData.cadOutline)obj.visible=$ui('layer_outline').checked&&$ui('layer_wall').checked;
   else if(XR.some(k=>obj.material===mat[k]))obj.visible=$ui('layer_wall').checked;
   else if(obj.name.endsWith('_slab')||/^.+_R\d+$/.test(obj.name))obj.visible=$ui('layer_floor').checked;
  }
 });
 applyCeil();
 ceilState.forEach(s=>s.beams.forEach(m=>m.visible=m.visible&&$ui('layer_wall').checked));
 syncLabels();syncTransport();
 leaves.forEach(s=>{s.piv.visible=$ui('layer_opening').checked&&$ui('dl').checked;s.guide.visible=s.piv.visible});
 glassM.forEach(m=>m.visible=$ui('layer_opening').checked&&$ui('gl').checked);
 groundGrid.visible=$ui('layer_grid').checked;referenceObjects.visible=$ui('layer_reference').checked;
 for(const bt of $ui('fbtn').children)bt.setAttribute('aria-pressed',String((bt.textContent==='전체'?'all':bt.textContent)===selFloor));
};
function viewBounds(){const box=new THREE.Box3();groups.forEach((G,i)=>{if(!G.visible)return;const f=B.floors[i];for(const p of f.slab)for(const[x,y]of p.o){box.expandByPoint(new THREE.Vector3(x,y,G.position.z));box.expandByPoint(new THREE.Vector3(x,y,G.position.z+f.h))}});
 if($ui('show_ramp').checked)for(const f of B.floors)for(const r of f.model_ramps||[])if(selFloor==='all'||selFloor===f.name||selFloor===r.to_floor)for(const [i,q] of r.outer.entries())box.expandByPoint(new THREE.Vector3(q[0],q[1],f.z+(r.rise_m||0)*i/(r.outer.length-1)));
 if($ui('layer_reference').checked&&(selFloor==='all'||selFloor===groundFloor?.name)){references.updateMatrixWorld(true);box.union(new THREE.Box3().setFromObject(referenceObjects))}
 if(window.cadAdditionalBounds)box.union(window.cadAdditionalBounds());
 return box.isEmpty()?bounds.clone():box}
function fitView(overhead=false){
 const box=viewBounds(),target=box.getCenter(new THREE.Vector3()),size=box.getSize(new THREE.Vector3());
 const direction=overhead?new THREE.Vector3(0,-.0001,1).normalize():new THREE.Vector3(.5,-1,.95).normalize();
 const right=new THREE.Vector3().crossVectors(direction,C.up).normalize(),up=new THREE.Vector3().crossVectors(right,direction).normalize();
 const tanV=Math.tan(THREE.MathUtils.degToRad(C.fov/2)),tanH=tanV*C.aspect;let distance=1;
 for(const x of [box.min.x,box.max.x])for(const y of [box.min.y,box.max.y])for(const z of [box.min.z,box.max.z]){
  const p=new THREE.Vector3(x,y,z).sub(target);distance=Math.max(distance,p.dot(direction)+Math.max(Math.abs(p.dot(right))/tanH,Math.abs(p.dot(up))/tanV));
 }
 O.target.copy(target);C.position.copy(target).addScaledVector(direction,distance*1.16);O.update();
}
iso=()=>fitView(false);top=()=>fitView(true);
$ui('iso').onclick=iso;$ui('top').onclick=top;$ui('resetView').onclick=iso;
function zoomBy(factor){C.position.copy(O.target.clone().add(C.position.clone().sub(O.target).multiplyScalar(factor)));O.update()}
$ui('zoomIn').onclick=()=>zoomBy(.8);$ui('zoomOut').onclick=()=>zoomBy(1.25);
for(const b of $ui('fbtn').children)b.onclick=()=>{const previous=viewBounds().getCenter(new THREE.Vector3());selFloor=b.textContent==='전체'?'all':b.textContent;applyFloor();const next=viewBounds().getCenter(new THREE.Vector3());const delta=next.sub(previous);C.position.add(delta);O.target.add(delta);O.update();if(selFloor==='all')iso()};
for(const id of ['layer_wall','layer_opening','layer_floor','layer_outline','layer_grid','layer_reference','above','gl','dl','cl','rl'])$ui(id).onchange=applyFloor;
function opacity(){const percent=+$ui('wallTransparency').value;$ui('opacityValue').textContent=percent+'%';for(const k of XR){mat[k].opacity=1-percent/100;mat[k].depthWrite=percent===0;mat[k].transparent=percent>0;mat[k].side=THREE.DoubleSide;mat[k].needsUpdate=true}}
$ui('wallTransparency').oninput=opacity;
// The legacy debug controls use the same opacity state instead of fighting it.
$ui('op').oninput=e=>{$ui('wallTransparency').value=Math.round((1-+e.target.value)*100);opacity()};
$ui('xr').closest('label').style.display='none';
$ui('ex').oninput=e=>{groups.forEach((G,i)=>G.position.z=G.userData.z+i*+e.target.value);applyFloor();iso()};
rs=function(){const w=el.clientWidth,h=el.clientHeight;R.setSize(w,h);L2.setSize(w,h);C.aspect=w/h;C.updateProjectionMatrix()};
new ResizeObserver(rs).observe(el);rs();
selFloor=groundFloor?.name??B.floors[0].name;applyFloor();opacity();iso();
// Read-only diagnostic state supports regression checks of the rendered scene.
window.cadViewerSnapshot=()=>({version:'cad-ui-v12',floor:selFloor,camera:C.position.toArray(),target:O.target.toArray(),visibleFloors:groups.filter(g=>g.visible).map(g=>g.name),groundZ,gridZ:groundZ-.19,gridVisible:groundGrid.visible,gridStep:1,stairs:transport.roots.filter(g=>g.userData.transportKind==='stair'&&visibleByName(g)).reduce((n,g)=>n+g.children.length,0),visibleWalls:groups.filter(g=>g.visible).flatMap(g=>g.children).filter(o=>XR.some(k=>o.material===mat[k])&&o.visible).length,viewport:[el.clientWidth,el.clientHeight]});
document.body.dataset.viewerVersion='cad-ui-v12';
const updateDiagnostic=()=>{document.body.dataset.viewerState=JSON.stringify(window.cadViewerSnapshot())};
O.addEventListener('change',updateDiagnostic);
document.addEventListener('change',updateDiagnostic);document.addEventListener('click',updateDiagnostic);updateDiagnostic();
// A pinch ending on a stationary second finger must not select a door/window.
const touchPoints=new Set();let suppressTouchPick=false;
R.domElement.addEventListener('pointerdown',e=>{if(e.pointerType==='touch'){if(!touchPoints.size)suppressTouchPick=false;touchPoints.add(e.pointerId);if(touchPoints.size>1)suppressTouchPick=true}},true);
R.domElement.addEventListener('pointerup',e=>{if(e.pointerType==='touch'){touchPoints.delete(e.pointerId);if(suppressTouchPick)down=null}},true);
R.domElement.addEventListener('pointercancel',e=>{touchPoints.delete(e.pointerId);down=null},true);
