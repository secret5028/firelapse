// Coordinate adapter: the established tools use (X, height, plan Z).
// CAD uses (X, plan Y, height). Keep tool state in its original convention.
const legacyContext=await (await fetch('legacy-context.json')).json();
window.LOCAL_JOB=window.CAD_OFFLINE?null:legacyContext.jobId;
if(window.CAD_OFFLINE?.hydraulics)window.HYDRAULIC_INITIAL=structuredClone(window.CAD_OFFLINE.hydraulics);
window.HYDRAULIC_CONFIG={buildingId:legacyContext.buildingId,name:'CAD 건물'};
const legacyRoot=new THREE.Group();legacyRoot.name='기존 웹앱 작전·설비';legacyRoot.rotation.x=Math.PI/2;legacyRoot.position.z=groundZ;S.add(legacyRoot);
const toLegacy=p=>[p.x,p.z-groundZ,-p.y];
const floorNumber=n=>n==='PH'?Math.max(1,...B.floors.map(f=>parseInt(f.name)||0))+1:n.startsWith('B')?-parseInt(n.slice(1)):parseInt(n);
function cadPage(f){
 const shapes=[];const xy=q=>[q[0],-q[1]];
 for(const band of f.bands.filter(b=>b.z0<1.3&&['wall','win_low'].includes(b.kind)))for(const poly of band.polys)for(const ring of [poly.o,...poly.h])ring.forEach((p,i)=>{const q=ring[(i+1)%ring.length];if(Math.hypot(q[0]-p[0],q[1]-p[1])>.005)shapes.push({type:'wall',a:xy(p),b:xy(q)})});
 for(const opening of f.openings.filter(o=>o.kind.startsWith('door')&&o.kind!=='door_elev')){
  const poly=opening.polys[0];if(!poly?.length)continue;let longest=0,a,b;
  poly.forEach((p,i)=>{const q=poly[(i+1)%poly.length],d=Math.hypot(q[0]-p[0],q[1]-p[1]);if(d>longest){longest=d;a=p;b=q}});
  if(a)shapes.push({type:'door',a:xy(a),b:xy(b),openingKind:'swing',id:opening.id});
 }
 return {building:'CAD',floor:floorNumber(f.name),levelLabel:f.name,height:f.h,elevation:f.z-groundZ,scale:1,origin:[0,0],included:true,shapes,
  floorPolygons:f.slab.map(p=>p.o.map(xy)),floorHoles:f.slab.flatMap(p=>p.h.map(r=>r.map(xy))),
  stairs:f.transport.filter(c=>c.kind==='stair').map(c=>{const points=c.anchor[0].o.map(xy);return {a:[Math.min(...points.map(p=>p[0])),Math.min(...points.map(p=>p[1]))],b:[Math.max(...points.map(p=>p[0])),Math.max(...points.map(p=>p[1]))],coreId:c.id}})};
}
const state={pages:B.floors.map(cadPage),operations:{version:1,vehicles:[],routes:[],fires:[],people:[]}};
const legacyStorage='cad-legacy-tools-v1:'+legacyContext.buildingId;
let restored=legacyContext.state;try{if(!restored)restored=JSON.parse(localStorage.getItem(legacyStorage)||'null')}catch{}
if(restored?.version===1&&restored.jobId===legacyContext.jobId&&restored.operations)state.operations=restored.operations;
state.operations.people??=[];
let mode='3d';const switchMode=()=>{};let saveQueue=Promise.resolve();
function persist(){
 const value={version:1,jobId:legacyContext.jobId,operations:structuredClone(state.operations)};
 const content=JSON.stringify(value);try{localStorage.setItem(legacyStorage,content)}catch{}
 const status=$ui('legacySaved');status.textContent='저장 중…';
 if(window.CAD_OFFLINE){status.textContent='현재 파일에서 편집 중 · HTML 내보내기로 변경사항 저장';return;}
 saveQueue=saveQueue.catch(()=>{}).then(async()=>{const r=await fetch('/api/jobs/'+legacyContext.jobId+'/cad-state',{method:'POST',headers:{'Content-Type':'application/json'},body:content});if(!r.ok)throw Error('저장 실패');status.textContent='건물 히스토리에 저장됨'}).catch(()=>{status.textContent='히스토리 저장 실패 · 파일 저장 가능'});
}
const legacyStyle=document.createElement('style');legacyStyle.textContent=`#v{left:176px}#legacyTools{position:fixed;left:0;top:64px;bottom:0;width:176px;padding:10px;box-sizing:border-box;overflow:auto;background:#132939;border-right:1px solid #355063}#legacyTools h2{font-size:13px;color:#efd16b;margin:8px 0}#legacyTools button,#legacyTools select{box-sizing:border-box;background:#19394d;color:#e6eff6;border:1px solid #3e6176;border-radius:4px;padding:6px;font:12px system-ui;width:100%;margin:3px 0}#legacyTools button{cursor:pointer}#legacyTools button:disabled{opacity:.4;cursor:default}#legacyTools p,#legacyTools label{font-size:11px;line-height:1.5}#legacyTools .opRow{display:flex;gap:4px}#legacyTools details{border-top:1px solid #355063;padding-top:10px;margin-top:10px}#legacyTools summary{cursor:pointer;font-size:12px}#legacySaved{color:#a7c5d8}@media(max-width:900px){#v{left:148px;right:190px}#legacyTools{width:148px}#p{width:190px}}`;
document.head.append(legacyStyle);
const toolsPanel=document.createElement('aside');toolsPanel.id='legacyTools';toolsPanel.innerHTML=`<h2>작전 설정</h2><section id="resultOperations"></section><h2>사람 배치</h2><button id="personAdd">＋ 사람 배치</button><select id="peopleSelect" aria-label="사람 선택"></select><button id="personDelete">선택 사람 삭제</button><p id="personNotice"></p><details><summary>작업 저장·불러오기</summary><button id="legacyExport">작전 파일 저장</button><button id="legacyImport">작전 파일 불러오기</button><input id="legacyFile" type="file" accept=".json" hidden><p id="legacySaved">건물별 작전 설정</p></details>`;
document.body.append(toolsPanel);
topBar.querySelector('a').id='mode2d';
const floorSelect=document.createElement('select');floorSelect.id='viewFloor';floorSelect.hidden=true;
for(const f of [{name:'all'},...B.floors])floorSelect.add(new Option(f.name,f.name==='all'?'all':'CAD|'+floorNumber(f.name)));document.body.append(floorSelect);
function syncLegacyFloor(){floorSelect.value=selFloor==='all'?'all':'CAD|'+floorNumber(selFloor);window.operationsRefresh?.();window.HydraulicUI?.refresh()}
const applyCadFloor=applyFloor;applyFloor=function(){applyCadFloor();syncLegacyFloor()};
for(const b of $ui('fbtn').children)b.addEventListener('click',syncLegacyFloor);
function cadPick(e,groundOnly){
 const rect=R.domElement.getBoundingClientRect(),ray=new THREE.Raycaster();ray.setFromCamera(new THREE.Vector2((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1),C);
 if(!groundOnly){const floors=groups.filter(g=>g.visible).flatMap(g=>g.children.filter(o=>o.isMesh&&o.visible&&(o.name.endsWith('_slab')||/^.+_R\d+$/.test(o.name))));const hit=ray.intersectObjects(floors,false)[0];return hit?toLegacy(hit.point):null}
 const point=new THREE.Vector3();return ray.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0,0,1),-groundZ),point)?toLegacy(point):null;
}
$ui('legacyExport').onclick=()=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify({version:1,jobId:legacyContext.jobId,operations:state.operations},null,2)],{type:'application/json'}));a.download='CAD-작전설정.json';a.click()};
$ui('legacyImport').onclick=()=>$ui('legacyFile').click();
$ui('legacyFile').onchange=async e=>{try{const file=e.target.files[0];if(!file||file.size>2000000)throw Error('2MB 이하 작업 파일이 필요합니다.');const v=JSON.parse(await file.text());if(v.jobId!==legacyContext.jobId||v.version!==1||!v.operations)throw Error('다른 건물의 작업 파일입니다.');for(const k of ['vehicles','routes','fires','people']){if(!Array.isArray(v.operations[k]||[])||(v.operations[k]||[]).length>300)throw Error('작전 설정 형식 오류');for(const item of v.operations[k]||[]){const points=k==='routes'?item.points:[item.position];if(!Array.isArray(points)||points.some(p=>!Array.isArray(p)||p.length!==3||!p.every(Number.isFinite)))throw Error('좌표 형식 오류')}}state.operations=v.operations;state.operations.people??=[];persist();window.operationsRefresh?.();refreshPeople()}catch(err){$ui('legacySaved').textContent=err.message}e.target.value=''};
rs();iso();
