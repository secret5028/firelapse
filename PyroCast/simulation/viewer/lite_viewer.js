import {createRealView} from './legacy_real_bridge.js';
import {flameGrowthStyle} from './legacy_real_view.js';

export async function attachLite(viewer,initial){
 const {THREE:T,B,S,C,O,R,groups,shp,legacyRoot}=viewer;
 legacyRoot.visible=false;
 const style=document.createElement('link');style.rel='stylesheet';style.href='/cfbt/overlay.css';document.head.append(style);
 const panel=document.createElement('section');panel.id='cfbtPanel';panel.setAttribute('aria-label','간략 엔진 v8');
 panel.innerHTML=`<div class="row"><strong>PyroCast · 간략 엔진 v8</strong><output id="liteClock"></output><span id="liteVisible"></span><span class="grow"></span><button id="liteBuilding">건물 전체 맞춤</button><label><input id="liteCores" type="checkbox" checked>수직 공간 투시</label><button id="liteReal" aria-pressed="true">실감 보기</button><button id="liteFireFocus">연소점 확대</button><button id="litePlay">재생</button><button id="liteFold">접기</button><button id="liteReview">전체 메뉴 검토</button></div>
 <div class="row"><label><input id="liteExterior" type="checkbox" checked><span style="color:#62dcb0">외부 창 강조</span></label><small>보는 쪽 외부 창만 · 뒤편 투시 없음 · 큰 창·난간 제외 · 표시 전용</small></div>
 <div class="row"><label><input id="liteDoors" type="checkbox" checked><span style="color:#e6bd68">실내 문 위치</span></label><small>도면 문틀 · 연기 속 위치 표시 · 개폐 상태와 별도</small></div>
 <div id="liteCoreLegend" hidden><span style="color:#ffc342">■ 계단실·계단</span> · <span style="color:#55baff">■ 승강로</span> — 도면 수직 공간을 벽·슬래브 너머로 표시 (연기 전파 계산 아님)</div>
 <div id="liteBody"><div class="row"><select id="liteSpeed" aria-label="재생 배속"><option>1</option><option>5</option><option>10</option><option selected>20</option><option>30</option><option>60</option></select>배 <label><input id="liteSmoke" type="checkbox" checked>전체 연기층</label><label><input id="liteFuel" type="checkbox" checked>균등 연료 기호</label><span class="grow"></span><select id="liteCase" aria-label="간략 계산 사례"></select><button id="liteRefresh">MC 결과 새로고침</button></div>
 <div class="row"><label><input id="litePlumes" type="checkbox" checked>상승 플룸·천장 고온 가스</label><label><input id="liteHeatSmoke" type="checkbox" checked>연기 온도색</label></div><div>연기 밝은 무늬: 회색(낮은 온도) → 노랑(200℃) → 빨강(600℃ 이상). 층 평균 온도의 표시용 색상이며 실제 연기색·착화 기준이 아닙니다.</div>
 <input id="liteTime" type="range" aria-label="간략 시뮬레이션 시간" min="0" step="10" style="width:100%">
 <div id="liteRiskStatus" role="status"></div><div>위험 테두리: 방 안의 일부 셀이라도 해당하면 원래 방 외곽 전체에 표시 · 여러 유형은 높이를 조금 띄워 함께 표시</div><div id="liteLegend"><span style="color:#ef4444">■ FO</span> · <span style="color:#a855f7">■ FGI 가능</span> · <span style="color:#f97316">━ 롤오버 진행 조건 띠</span> · <span style="color:#facc15">■ 백드래프트 잠재</span> · 회색: 연기 주의 · 점선: 전이 온도 기준 ±30℃</div>
 <div>조건 충족 단계이며 발생 예측 아님. 문 분출 연소와 상층 연소는 별도입니다.</div>
 <div>화염 단계(표시용): <span style="color:#ff7a14">초기</span> → <span style="color:#ffa824">성장기</span> → <span style="color:#fff08c">최성기</span> → <span style="color:#ff3b09">쇠퇴기</span>. 각 화원 실제 발열량의 최고값 대비 크기·최고 시점 기준이며 실제 불꽃 온도·FO 판정이 아닙니다. 불꽃 범위는 발열량과 실·셀 면적에 따라 화원 주변에서 확대·축소됩니다. 최대 범위는 면적 65% 상당 원을 실 경계로 자른 표시용 가정이며, 불꽃 수는 계산 화원 수가 아닙니다.</div>
 <div class="row"><label>실·셀 <select id="liteRoom" aria-label="간략 실 선택"></select></label><button id="liteFocus">선택 실 확대</button><button id="liteWhole">층 전체</button><label>연기 불투명도 <select id="liteOpacity" aria-label="간략 연기 불투명도"><option value="1" selected>100% · 기본</option><option value=".4">40% · 내부 관찰</option><option value=".15">15%</option></select></label></div>
 <div id="liteDetail" aria-live="polite"></div><div id="liteScores"></div><div id="liteStatus"></div><div id="liteMC"></div>
 <details id="liteMCSummary" hidden><summary>MC 10표본 결과 · 발생확률 아님</summary><div id="liteMCTable"></div></details>
 <details><summary>가정과 한계</summary><div id="liteLimits"></div><div>연기 무늬·온도색·불투명도는 표시용입니다. 플룸·천장 가스는 간략 엔진 발열량과 층 상태에 CFAST 계열 상관식을 적용한 보조 표시이며 순정 CFAST 출력이나 CFD 속도장이 아닙니다. 광학밀도·폭압은 미평가입니다. 반응 조건을 만족해도 실제 현상 발생을 뜻하지 않습니다.</div></details>
 <span id="cfMeaning" hidden></span></div>`;
 document.body.append(panel);const $=id=>document.getElementById(id);
 // Dedicated x-ray display: reuse extracted floor-local core footprints and
 // stair treads. Do not invent shafts across floors missing from the model.
 const coreOverlay=new T.Group();coreOverlay.name='전체 건물 수직 공간 투시';S.add(coreOverlay);
 const exteriorOverlay=new T.Group();exteriorOverlay.name='외기 개구부 강조';S.add(exteriorOverlay);const exteriorViews=[];
 B.floors.forEach((f,i)=>{
  const group=new T.Group();exteriorOverlay.add(group);exteriorViews.push({group,i});
  for(const opening of f.openings||[]){
   const face=exteriorWindowFace(f,opening);if(!face)continue;
   const geometry=new T.BufferGeometry().setFromPoints(face.corners.map(p=>new T.Vector3(...p)));
   const frame=new T.LineLoop(geometry,new T.LineBasicMaterial({color:'#62dcb0',linewidth:1,transparent:true,opacity:.65,depthTest:true,depthWrite:false}));frame.name=`exterior-window-${f.name}-${opening.id}`;frame.renderOrder=30;frame.raycast=()=>{};group.add(frame);
   frame.userData.exteriorNormal=new T.Vector3(...face.normal);frame.userData.exteriorCenter=new T.Vector3(...face.center);
  }
 });
 // LineLoop has no face culling: explicitly hide the facade facing away from
 // the camera, even when architectural walls are displayed transparently.
 const interiorOverlay=new T.Group();interiorOverlay.name='실내 문 위치';S.add(interiorOverlay);const interiorViews=[];
 B.floors.forEach((f,i)=>{
  const group=new T.Group();interiorOverlay.add(group);interiorViews.push({group,i});
  for(const opening of f.openings||[]){
   if(opening.kind!=='door'||opening.connection_status!=='interior')continue;
   let spans=(opening.leaves||[]).map(l=>[l.hinge,l.closed]);
   if(!spans.length){
    let longest=0,span=null;for(const ring of opening.polys||[])for(let j=0;j<ring.length;j++){
     const a=ring[j],b=ring[(j+1)%ring.length],length=Math.hypot(b[0]-a[0],b[1]-a[1]);
     if(length>longest){longest=length;span=[a,b];}
    }if(span)spans=[span];
   }
   const height=opening.door_h||f.door_h||2.1;
   for(const [a,b] of spans){
    const vertices=[[...a,.035],[...b,.035],[...b,height],[...a,height]].map(p=>new T.Vector3(...p));
    const line=new T.LineLoop(new T.BufferGeometry().setFromPoints(vertices),new T.LineBasicMaterial({color:'#e6bd68',transparent:true,opacity:.9,depthTest:false,depthWrite:false}));
    line.name=`interior-door-${f.name}-${opening.id}`;line.renderOrder=46;line.raycast=()=>{};group.add(line);
   }
  }
 });
 const exteriorCameraDelta=new T.Vector3();
 function syncExteriorFacing(){for(const view of exteriorViews)for(const frame of view.group.children){
  exteriorCameraDelta.copy(C.position).sub(view.group.position).sub(frame.userData.exteriorCenter);
  frame.visible=exteriorCameraDelta.dot(frame.userData.exteriorNormal)>0;
 }}
 O.addEventListener('change',syncExteriorFacing);
 const coreViews=[];
 B.floors.forEach((f,i)=>{
  const group=new T.Group();group.position.copy(groups[i].position);coreOverlay.add(group);coreViews.push({group,i});
  for(const core of f.transport||[]){
   if(!['stair','elev'].includes(core.kind))continue;
   // Unconnected entrance/exterior stair symbols are not full-height shafts.
   if(!core.connected&&!core.to_floor&&!(core.meshes||[]).length)continue;
   const color=core.kind==='stair'?'#ffc342':'#55baff',polys=core.region?.length?core.region:core.anchor;
   if(!polys?.length)continue;
   const geometry=new T.ExtrudeGeometry(polys.map(shp),{depth:f.h,bevelEnabled:false,curveSegments:1});
   const shell=new T.Mesh(geometry,new T.MeshBasicMaterial({color,transparent:true,opacity:.10,depthTest:false,depthWrite:false,side:T.DoubleSide}));shell.renderOrder=70;shell.raycast=()=>{};group.add(shell);
   const edges=new T.LineSegments(new T.EdgesGeometry(geometry,25),new T.LineBasicMaterial({color,transparent:true,opacity:.95,depthTest:false,depthWrite:false}));edges.renderOrder=73;edges.raycast=()=>{};group.add(edges);
   if(core.kind==='stair')for(const step of core.meshes||[]){
    if(!step.polys?.length||!(step.z1>step.z0))continue;
    const tread=new T.Mesh(new T.ExtrudeGeometry(step.polys.map(shp),{depth:step.z1-step.z0,bevelEnabled:false,curveSegments:1}),new T.MeshBasicMaterial({color,transparent:true,opacity:.86,depthTest:false,depthWrite:false}));tread.position.z=step.z0;tread.renderOrder=72;tread.raycast=()=>{};group.add(tread);
   }
  }
 });
 const selectionLabel=document.createElement('div');selectionLabel.className='cfbtSceneCaption';selectionLabel.style.borderColor='#42e8ff';selectionLabel.style.color='#9af3ff';$('v').append(selectionLabel);
 function resize(){document.documentElement.style.setProperty('--cfbt-height',panel.getBoundingClientRect().height+'px');const v=$('v');if(!v)return;R.setSize(v.clientWidth,v.clientHeight);viewer.L2?.setSize(v.clientWidth,v.clientHeight);C.aspect=v.clientWidth/Math.max(1,v.clientHeight);C.updateProjectionMatrix();if(autoFit&&data)fitFloor();}
 new ResizeObserver(resize).observe(panel);window.addEventListener('resize',resize);
 let data,root,real,views=[],riskRooms=[],units=[],selected=null,index=0,playing=false,last=0,lastFloor='',chosen=initial.case_id||'stage4',clicked=false,autoFit=true;
 const stamp=t=>Math.floor(t/60).toString().padStart(2,'0')+':'+Math.floor(t%60).toString().padStart(2,'0');
 const name=r=>`${r.cad_floor} ${r.cad_room} · ${r.display_name||(r.cad_names||[]).slice(0,2).join(' / ')}`;
 // Floor buttons change visibility only. Preserve orbit position, target and zoom.
 for(const button of $('fbtn').children){const old=button.onclick;button.onclick=function(e){const position=C.position.clone(),target=O.target.clone(),zoom=C.zoom;autoFit=false;old?.call(this,e);C.position.copy(position);O.target.copy(target);C.zoom=zoom;C.updateProjectionMatrix();O.update();update();};}
 function selectionGeometry(room){
  const points=[];
  for(const polygon of room.cad_polys)for(const ribbon of joinedSelectionRibbons(polygon)){
   for(let i=0;i<ribbon.outer.length;i++){
    const j=(i+1)%ribbon.outer.length,q=[ribbon.outer[i],ribbon.outer[j],ribbon.inner[j],ribbon.inner[i]];
    for(const k of [0,1,2,0,2,3])points.push(q[k][0],q[k][1],room.z_m+.08);
   }
  }
  const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(points,3));return g;
 }
 function boundarySegments(room,original){
  // Smoke/risk outlines use exterior rings only; column/stair holes are not boxes.
  const edges=polys=>polys.flatMap(p=>p.o.map((a,i)=>[a,p.o[(i+1)%p.o.length]]).filter(([a,b])=>Math.hypot(b[0]-a[0],b[1]-a[1])>1e-7));
  const cellEdges=edges(room.cad_polys);if(!original)return cellEdges.map(([a,b])=>({a,b}));
  const outerEdges=edges(original.polys),segments=[];
  // Keep only overlap with the original CAD perimeter. Virtual cell cuts,
  // including their vertical uprights, are never drawn as room boundaries.
  for(const [a,b] of cellEdges){
   const dx=b[0]-a[0],dy=b[1]-a[1],len=Math.hypot(dx,dy),ux=dx/len,uy=dy/len;
   for(const [c,d] of outerEdges){
    if(Math.abs((c[0]-a[0])*uy-(c[1]-a[1])*ux)>.002||Math.abs((d[0]-a[0])*uy-(d[1]-a[1])*ux)>.002)continue;
    const tc=(c[0]-a[0])*ux+(c[1]-a[1])*uy,td=(d[0]-a[0])*ux+(d[1]-a[1])*uy;
    const lo=Math.max(0,Math.min(tc,td)),hi=Math.min(len,Math.max(tc,td));if(hi-lo<1e-6)continue;
    const q=[a[0]+lo*ux,a[1]+lo*uy],r=[a[0]+hi*ux,a[1]+hi*uy];
    segments.push({a:q,b:r});
   }
  }
  return segments;
 }
 function geometry(room){const pts=[];for(const {a,b} of room.displayBoundary||boundarySegments(room,null)){
  pts.push(a[0],a[1],0,b[0],b[1],0);
 }const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(pts,3));return g;}


 function install(payload){
  if(!payload.complete||payload.building_sha256!==initial.building_sha256)throw Error('완료·건물 대응 확인 실패');
  if(root){real.detach();root.traverse(o=>{o.geometry?.dispose();if(o.material&&!o.material.uniforms)o.material.dispose();});root.removeFromParent();}
  data=payload;index=0;playing=false;clicked=false;root=new T.Group();S.add(root);views=[];riskRooms=[];units=[];
  for(const f of B.floors)groups.find(g=>g.name===f.name)?.traverse(mesh=>{
   if(!mesh.material?.color)return;
   if(mesh.name?.startsWith(f.name+'_'))mesh.material.color.set('#aab7c0');
   else if([0x8a8a8a,0x8b5a2b,0x93acb5].includes(mesh.material.color.getHex()))mesh.material.color.set('#b8c3cb');
   if(mesh.isLineSegments&&mesh.userData.cadOutline){mesh.material.color.set('#bdcbd5');mesh.material.opacity=.42;}
  });
  for(const room of data.rooms){const group=new T.Group();root.add(group);
   const isCell=!!room.original_room&&room.original_room!==room.key;
   const original=isCell?B.floors.find(f=>f.name===room.cad_floor)?.rooms.find(r=>`CAD_${room.cad_floor}_${r.id}`===room.original_room):null;
   const boundaryRoom={...room,displayBoundary:isCell?(original?boundarySegments(room,original):[]):boundarySegments(room,null)};
   const selectionRoom=original?{...room,cad_polys:original.polys}:room;
   const floor=new T.Mesh(new T.ShapeGeometry(room.cad_polys.map(shp)),new T.MeshBasicMaterial({color:'#ffffff',transparent:true,opacity:0,side:T.DoubleSide,depthWrite:false}));floor.position.z=room.z_m+.07;floor.userData.liteRoom=room.key;group.add(floor);
   const line=new T.LineSegments(geometry(boundaryRoom),new T.LineDashedMaterial({color:'#fff',dashSize:.4,gapSize:0,transparent:true,opacity:.95,depthTest:false,depthWrite:false}));line.computeLineDistances();line.renderOrder=25;line.raycast=()=>{};group.add(line);
   const band=new T.LineSegments(geometry(boundaryRoom),new T.LineBasicMaterial({color:'#f97316',depthTest:false,depthWrite:false}));band.renderOrder=26;band.raycast=()=>{};group.add(band);
   const selection=new T.Mesh(selectionGeometry(selectionRoom),new T.MeshBasicMaterial({color:'#42e8ff',side:T.DoubleSide,transparent:true,opacity:.95,depthTest:false,depthWrite:false}));selection.renderOrder=40;selection.raycast=()=>{};group.add(selection);
   const interfaceLine=new T.LineSegments(geometry(boundaryRoom),new T.LineDashedMaterial({color:'#e7f2fa',dashSize:.35,gapSize:.2,transparent:true,opacity:.9,depthTest:false,depthWrite:false}));interfaceLine.computeLineDistances();interfaceLine.renderOrder=28;interfaceLine.raycast=()=>{};group.add(interfaceLine);
   const interfacePlane=new T.Mesh(floor.geometry.clone(),new T.MeshBasicMaterial({color:'#d8e9f5',transparent:true,opacity:.07,side:T.DoubleSide,depthTest:false,depthWrite:false}));interfacePlane.renderOrder=27;interfacePlane.raycast=()=>{};group.add(interfacePlane);
   views.push({room,isCell,group,floor,line,band,selection,interfaceLine,interfacePlane});
  }
  const byOriginal=new Map();
  for(const room of data.rooms){const key=room.original_room||room.key;if(!byOriginal.has(key))byOriginal.set(key,[]);byOriginal.get(key).push(room);}
  for(const [key,members] of byOriginal){
   const first=members[0],cad=B.floors.find(f=>f.name===first.cad_floor)?.rooms.find(r=>`CAD_${first.cad_floor}_${r.id}`===key);
   const polys=cad?.polys||first.cad_polys,verts=[];
   for(const p of polys)for(const ribbon of joinedSelectionRibbons({o:p.o,h:[]},.055,.04))for(let i=0;i<ribbon.outer.length;i++){
    const j=(i+1)%ribbon.outer.length,q=[ribbon.outer[i],ribbon.outer[j],ribbon.inner[j],ribbon.inner[i]];
    for(const k of [0,1,2,0,2,3])verts.push(q[k][0],q[k][1],0);
   }
   const geo=new T.BufferGeometry();geo.setAttribute('position',new T.Float32BufferAttribute(verts,3));
   const colors=['#ef4444','#a855f7','#facc15','#f97316'],meshes=colors.map(color=>{
    const mesh=new T.Mesh(geo.clone(),new T.MeshBasicMaterial({color,side:T.DoubleSide,transparent:true,opacity:1,depthTest:false,depthWrite:false}));mesh.renderOrder=35;mesh.raycast=()=>{};root.add(mesh);return mesh;
   });
   geo.dispose();riskRooms.push({key,members,colors,meshes});
  }
  for(const u of data.fuel_symbols){const g=new T.LineSegments(new T.EdgesGeometry(new T.BoxGeometry(.4,.4,.4)),new T.LineBasicMaterial({color:'#a6b4ba',transparent:true,opacity:.55}));g.position.set(...u.position_m);g.raycast=()=>{};root.add(g);units.push({u,g});}
  real=createRealView({THREE:T,C,groups,B},data,root);
  $('liteRoom').replaceChildren();for(const r of data.rooms)$('liteRoom').add(new Option(name(r),r.key));
  selected=data.rooms.find(r=>r.key===data.fire_key)||data.rooms[0];$('liteRoom').value=selected.key;
  $('liteTime').max=data.time_s.at(-1);$('liteTime').value=0;
  $('liteLimits').textContent=data.limits.join(' ');viewer.setFloor('3F');update();fitFloor();
 }
 function update(){if(!data)return;const time=data.time_s[index],floor=viewer.getFloor();lastFloor=floor;const sample=a=>a?.[index]??0;
  coreOverlay.visible=floor==='all'&&$('liteCores').checked;$('liteCoreLegend').hidden=!coreOverlay.visible;
  for(const v of coreViews){v.group.position.copy(groups[v.i].position);v.group.visible=groups[v.i].visible;}
  interiorOverlay.visible=$('liteDoors').checked;
  for(const v of interiorViews){v.group.position.copy(groups[v.i].position);v.group.visible=groups[v.i].visible&&(floor==='all'||B.floors[v.i].name===floor);}
  exteriorOverlay.visible=$('liteExterior').checked;
  for(const v of exteriorViews){v.group.position.copy(groups[v.i].position);v.group.visible=groups[v.i].visible&&(floor==='all'||B.floors[v.i].name===floor);}
  syncExteriorFacing();
  $('liteWhole').textContent=floor==='all'?'건물 전체 맞춤':'층 전체';
  real.update({enabled:$('liteReal').getAttribute('aria-pressed')==='true',time,sample,floor,smokeEnabled:$('liteSmoke').checked,smokeOpacity:+$('liteOpacity').value,customRiskBoundaries:true,legacySmokeTexture:true,flameDisplay:'growth',plumesEnabled:$('litePlumes').checked,temperatureSmoke:$('liteHeatSmoke').checked});
  const source=data.fires.find(f=>f.cad_key===selected.key),peak=source?Math.max(...source.Q_kW):0;
  const flameStage=source?flameGrowthStyle(source.Q_kW[index],peak,time,data.time_s[source.Q_kW.indexOf(peak)]).stage:'화원 없음';
  const zone=data.solvers[selected.solver_id],layerH=Math.max(0,Math.min(zone.height_m,zone.h[index]));
  selectionLabel.hidden=!(floor==='all'||selected.cad_floor===floor);selectionLabel.textContent=`선택: ${name(selected)}\n바닥 하늘색 = 선택한 방 · 내부 셀 경계 숨김\n화염 단계: ${flameStage} (발열량 기준 표시)\n상층 두께 ${(zone.height_m-layerH).toFixed(2)}m / 하층 높이 ${layerH.toFixed(2)}m\n외곽 수평선 = 연기층 경계 · 위험 조건 시 해당 색상`;
  const visibleRooms=data.rooms.filter(r=>floor==='all'||r.cad_floor===floor),visibleKeys=new Set(visibleRooms.map(r=>r.key));
  const smokeCount=$('liteSmoke').checked?visibleRooms.filter(r=>{const s=data.solvers[r.solver_id];return s.ODu[index]>0&&s.height_m-s.h[index]>.01;}).length:0;
  const fireCount=data.fires.filter(f=>visibleKeys.has(f.cad_key)&&f.Q_kW[index]>0).length;
  $('liteVisible').textContent=$('liteReal').getAttribute('aria-pressed')==='true'?`연기 ${smokeCount}구역 · 화염 ${fireCount}곳`:'실감 표시 꺼짐';
  const riskCounts={FO:0,FGI:0,backdraft:0,rollover:0},roomRisk=new Set();
  for(const row of riskRooms){const active=new Map();
   for(const r of row.members){const s=data.solvers[r.solver_id],d=s.display_v8;
    if(row.colors.includes(d.color[index]))active.set(d.color[index],Math.min(active.get(d.color[index])??Infinity,s.h[index]));
    // Recover independent existing v8 gas conditions before its single-colour
    // FO precedence. No new threshold or condition-table formula is introduced.
    if(d.smoke_stage[index]===2&&Number.isFinite(d.LOC_vol_fraction)){
     const gasColor=s.Ou[index]>=d.LOC_vol_fraction?'#a855f7':'#facc15';
     active.set(gasColor,Math.min(active.get(gasColor)??Infinity,s.h[index]));
    }
    if(d.rollover_band[index])active.set('#f97316',Math.min(active.get('#f97316')??Infinity,s.h[index]));
   }
   const floorVisible=floor==='all'||row.members[0].cad_floor===floor;
   if(active.size)roomRisk.add(row.key);
   const height=row.members[0].height_m,base=Math.max(.16,Math.min(height-.5,...active.values()));
   row.meshes.forEach((mesh,i)=>{mesh.visible=floorVisible&&active.has(row.colors[i]);mesh.position.z=row.members[0].z_m+Math.min(height-.04,base+i*.14);if(mesh.visible)riskCounts[['FO','FGI','backdraft','rollover'][i]]++;});
  }
  $('liteRiskStatus').textContent=`외곽 위험 표시: FO ${riskCounts.FO}실 · FGI ${riskCounts.FGI}실 · 백드래프트 ${riskCounts.backdraft}실 · 롤오버 ${riskCounts.rollover}실 (현재 층/시점, 저장된 판정)`;
  for(const v of views){const s=data.solvers[v.room.solver_id],d=s.display_v8,color=d.color[index];v.group.visible=floor==='all'||floor===v.room.cad_floor;const h=Math.max(0,Math.min(s.height_m,s.h[index]));
   v.selection.visible=v.room.key===selected.key;
   const hasInterface=$('liteSmoke').checked&&!s.single_zone&&s.ODu[index]>0&&h>.05&&h<s.height_m-.05;
   v.interfaceLine.visible=hasInterface&&!color&&!roomRisk.has(v.room.original_room||v.room.key);v.interfaceLine.position.z=v.room.z_m+h;
   v.interfacePlane.visible=hasInterface&&v.selection.visible&&!v.isCell;v.interfacePlane.position.z=v.room.z_m+h;
   v.line.position.z=v.room.z_m+h;v.line.visible=!!color&&!roomRisk.has(v.room.original_room||v.room.key);v.line.material.color.set(color||'#9ca3af');v.line.material.gapSize=d.boundary[index] ? 0.25 : 0;
   v.band.visible=false;v.band.position.z=v.room.z_m+h+.12;
   v.floor.material.color.set(color||'#fff');v.floor.material.opacity=color?.startsWith('#9c') ? 0.025 : color?.length ? 0.1 : 0;
  }
  for(const {u,g} of units){const r=data.rooms.find(r=>r.key===u.room);g.visible=$('liteFuel').checked&&(floor==='all'||floor===r?.cad_floor);g.material.color.set(data.solvers[u.room]?.Qsolid_kW[index]>0?'#ff8a3d':'#a6b4ba');}
  $('liteClock').textContent=`${stamp(time)} / ${stamp(data.time_s.at(-1))}`;$('liteTime').value=time;$('litePlay').textContent=playing?'일시정지':'재생';
  const s=data.solvers[selected.key],d=s.display_v8,event=data.events.find(e=>e.room===selected.key),burn=s.Qsolid_kW[index]>0;
  $('liteDetail').textContent=clicked?`${name(selected)} · ${d.phenomenon[index]} · ${burn?'연소 중':event&&time>=event.supply_start_s?'조건 충족, 산소 부족 미연소':'고체 연소 없음'} · 상층 ${s.Tu[index].toFixed(1)}℃ / 하층 ${s.Tl[index].toFixed(1)}℃ · 상/하층 O₂ ${(s.Ou[index]*100).toFixed(1)}/${(s.Ol[index]*100).toFixed(1)}% · 경계 ${s.h[index].toFixed(2)}m · 고체 ${s.Qsolid_kW[index].toFixed(1)}kW / 문 분출 ${s.Qvent_kW[index].toFixed(1)}kW / 상층 ${s.Qbulk_kW[index].toFixed(1)}kW`:'실을 클릭하거나 선택하면 계산값·현상 지수·판정 근거를 표시합니다.';
  $('liteScores').replaceChildren();if(clicked){for(const [key,title] of [['FO','FO'],['FGI','FGI'],['backdraft','백드래프트'],['rollover','롤오버']]){const q=s.conditions[key].scores,degree=q.degree[index],p=document.createElement('div');p.textContent=`${title} 지수 ${degree==null?'미평가':(degree*100).toFixed(0)} (100=조건 기준, 확률 아님) · 병목 ${q.weakest[index]||'미평가'} · 우세 ${q.strongest[index]||'미평가'}`;$('liteScores').append(p);}}
  $('liteStatus').textContent=`${data.label} · 3F 층 계산 · 문 분출 ON · 연기는 계산 상층 범위·온도의 표시 효과(광학밀도 미계산)`;
 }
 function select(key){selected=data.rooms.find(r=>r.key===key)||selected;$('liteRoom').value=selected.key;clicked=true;if(viewer.getFloor()!=='all'&&viewer.getFloor()!==selected.cad_floor)viewer.setFloor(selected.cad_floor);update();}
 $('liteRoom').onchange=()=>select($('liteRoom').value);
 $('liteFocus').onclick=()=>{clicked=true;autoFit=false;const p=selected.cad_center_m;O.target.set(p[0],p[1],selected.z_m+1);C.position.set(p[0]+15,p[1]-18,selected.z_m+18);O.update();update();};
 // Focus the actual source, not the centre of a large room. Keep compact flames
 // at their real CAD position; camera zoom must not enlarge them through walls.
 $('liteFireFocus').onclick=()=>{
  const burning=data.fires.filter(f=>f.Q_kW[index]>0);
  const fire=burning.find(f=>f.cad_key===selected.key)||burning[0];
  if(!fire){$('liteVisible').textContent='현재 시점에는 연소 중인 화원이 없습니다. 시간을 이동하거나 재생하세요.';return;}
  viewer.setFloor(fire.cad_floor);select(fire.cad_key);autoFit=false;
  $('liteReal').setAttribute('aria-pressed','true');$('liteSmoke').checked=true;
  const p=fire.position_m;O.target.set(p[0],p[1],p[2]+.8);
  C.position.set(p[0]+6,p[1]-8,p[2]+Math.max(6,selected.height_m+3));O.update();update();
 };
 function fitFloor(){
  autoFit=true;
  const rooms=data.rooms.filter(r=>viewer.getFloor()==='all'||r.cad_floor===viewer.getFloor());if(!rooms.length)return;
  const bounds=new T.Box3();
  if(viewer.getFloor()==='all'){for(const f of B.floors)for(const p of f.slab||[])for(const xy of p.o){bounds.expandByPoint(new T.Vector3(xy[0],xy[1],f.z));bounds.expandByPoint(new T.Vector3(xy[0],xy[1],f.z+f.h));}}
  else for(const r of rooms)for(const p of r.cad_polys)for(const xy of p.o){bounds.expandByPoint(new T.Vector3(xy[0],xy[1],r.z_m));bounds.expandByPoint(new T.Vector3(xy[0],xy[1],r.z_m+r.height_m));}
  const center=bounds.getCenter(new T.Vector3()),radius=bounds.getSize(new T.Vector3()).length()/2;
  const vertical=C.fov*Math.PI/180,horizontal=2*Math.atan(Math.tan(vertical/2)*C.aspect),distance=radius/Math.sin(Math.min(vertical,horizontal)/2)*1.05;
  O.target.copy(center);C.position.copy(center).add(new T.Vector3(1,-1,1.1).normalize().multiplyScalar(distance));O.update();
 }
 $('liteWhole').onclick=fitFloor;
 $('liteBuilding').onclick=()=>{viewer.setFloor('all');update();fitFloor();};$('liteCores').onchange=update;
 $('liteExterior').onchange=update;
 $('litePlay').onclick=()=>{playing=!playing;update();};$('liteTime').oninput=()=>{playing=false;index=Math.min(data.time_s.length-1,Math.floor(+$('liteTime').value/10));update();};
 $('liteReal').onclick=()=>{$('liteReal').setAttribute('aria-pressed',String($('liteReal').getAttribute('aria-pressed')!=='true'));update();};
 for(const id of ['liteSmoke','liteFuel','liteOpacity','litePlumes','liteHeatSmoke','liteDoors'])$(id).onchange=update;
 $('liteFold').onclick=()=>{$('liteBody').hidden=!$('liteBody').hidden;$('liteFold').textContent=$('liteBody').hidden?'펼치기':'접기';};
 const ray=new T.Raycaster(),mouse=new T.Vector2(),pointers=new Set();let down=null;
 R.domElement.addEventListener('pointerdown',e=>{autoFit=false;pointers.add(e.pointerId);down=pointers.size===1&&e.button===0?{id:e.pointerId,x:e.clientX,y:e.clientY,tolerance:e.pointerType==='touch'?10:5}:null;});
 R.domElement.addEventListener('pointermove',e=>{if(down&&Math.hypot(e.clientX-down.x,e.clientY-down.y)>down.tolerance)down=null;});
 R.domElement.addEventListener('pointercancel',e=>{pointers.delete(e.pointerId);down=null;});
 R.domElement.addEventListener('pointerup',e=>{pointers.delete(e.pointerId);const start=down;down=null;if(!start||start.id!==e.pointerId||pointers.size||Math.hypot(e.clientX-start.x,e.clientY-start.y)>start.tolerance)return;const b=R.domElement.getBoundingClientRect();mouse.set((e.clientX-b.x)/b.width*2-1,-(e.clientY-b.y)/b.height*2+1);ray.setFromCamera(mouse,C);const hit=ray.intersectObjects(views.filter(v=>v.group.visible).map(v=>v.floor))[0];if(hit)select(hit.object.userData.liteRoom);});
 async function catalog(){const r=await fetch('/cfbt/lite/catalog.json');if(!r.ok)return;const c=await r.json();$('liteCase').replaceChildren();for(const entry of c.cases||[])$('liteCase').add(new Option(entry.label,entry.id));$('liteCase').value=chosen;$('liteMC').textContent=c.progress_text||'';
  $('liteMCTable').replaceChildren();$('liteMCSummary').hidden=!c.mc_summary;
  if(c.mc_summary){const add=text=>{const p=document.createElement('div');p.textContent=text;$('liteMCTable').append(p);};
   add(`완주 ${c.mc_summary.completed}/10 · 전체 ${c.mc_summary.wall_s.toFixed(1)}초 · 필수 2표본은 무작위 비율에서 제외`);
   for(const x of c.mc_summary.rows)add(`${x.id}: ${x.complete?`연소 ${x.burning}실 / 연기 위험 ${x.smoke_risk}실`:'미완료 · 안전 판정 불가'}`);
   for(const [key,name] of [['FO','FO'],['FGI','FGI'],['backdraft','백드래프트'],['rollover','롤오버']]){const q=c.mc_summary.rates[key];add(`${name} 조건: 무작위 완주 ${q.numerator}/${q.denominator_completed_random}표본`);}
   add('연기 위험은 2단계 색 규칙, 현상 조건은 공통 조건표 기준. 실제 발생확률이 아닙니다.');
  }
 }
 $('liteRefresh').onclick=catalog;$('liteCase').onchange=async()=>{chosen=$('liteCase').value;const r=await fetch('/cfbt/lite/result/'+encodeURIComponent(chosen));if(r.ok)install(await r.json());};
 install(initial);await catalog();
 const review=await createMenuReview(panel,viewer);
 $('liteReview').onclick=()=>{review.hidden=false;};
 document.body.classList.add('cfbtReady');
 let fractional=0;function tick(ms){requestAnimationFrame(tick);if(document.hidden){last=ms;return;}if(playing){fractional+=Math.min(.2,(ms-last)/1000)*+$('liteSpeed').value;if(fractional>=10){index=Math.min(index+Math.floor(fractional/10),data.time_s.length-1);fractional%=10;if(index===data.time_s.length-1)playing=false;update();}}else if(lastFloor!==viewer.getFloor())update();real.animate(ms);last=ms;}requestAnimationFrame(tick);
}

// Display filter, not a window classification or a simulation geometry change.
function exteriorWindowFace(floor, opening) {
 if(opening.kind!=='window'||(opening.connection_status!=='exterior'&&!(opening.sides||[]).includes('out')))return null;
 const rooms=(floor.rooms||[]).filter(r=>(opening.sides||[]).includes(r.id));
 const labels=[opening.name,opening.label,...rooms.flatMap(r=>r.names||[])].join(' ');
 if(/테라스|난간|발코니|terrace|railing|balcony/i.test(labels))return null;
 const span=Number(opening.span),bottom=opening.sill??floor.sill??.9,top=opening.head??floor.head??2.4;
 if(!(span>=.4&&span<=3.01&&top>bottom&&top-bottom<=2.4))return null;
 // Use the opening footprint, not all decorative CAD line fragments.
 const rings=opening.polys?.length?opening.polys:(opening.geometry_polys||[]).map(p=>p.o);
 const points=(rings||[]).flat();if(points.length<3)return null;
 let box=null;
 for(const ring of rings)for(let i=0;i<ring.length;i++){
  const a=ring[i],b=ring[(i+1)%ring.length],len=Math.hypot(b[0]-a[0],b[1]-a[1]);if(len<1e-6)continue;
  const u=[(b[0]-a[0])/len,(b[1]-a[1])/len],v=[-u[1],u[0]];
  const us=points.map(p=>p[0]*u[0]+p[1]*u[1]),vs=points.map(p=>p[0]*v[0]+p[1]*v[1]);
  const lo=Math.min(...us),hi=Math.max(...us),near=Math.min(...vs),far=Math.max(...vs),area=(hi-lo)*(far-near);
  if(!box||area<box.area)box={u,v,lo,hi,near,far,area};
 }
 if(!box)return null;
 if(box.hi-box.lo<box.far-box.near){const {u,v,lo,hi,near,far,area}=box;box={u:v,v:u,lo:near,hi:far,near:lo,far:hi,area};}
 const {u,v,lo,hi,near,far}=box,width=hi-lo,depth=far-near;
 if(width<.4||width>3.6||depth>.65||depth<.01)return null;
 const middle=[u[0]*(lo+hi)/2+v[0]*(near+far)/2,u[1]*(lo+hi)/2+v[1]*(near+far)/2];
 function inRing(p,ring){let inside=false;for(let i=0,j=ring.length-1;i<ring.length;j=i++){
  const a=ring[i],b=ring[j];if((a[1]>p[1])!==(b[1]>p[1])&&p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0])inside=!inside;
 }return inside;}
 const inRoom=p=>rooms.some(r=>(r.polys||[]).some(poly=>inRing(p,poly.o)&&!(poly.h||[]).some(h=>inRing(p,h))));
 const offset=depth/2+.35,plus=inRoom([middle[0]+v[0]*offset,middle[1]+v[1]*offset]),minus=inRoom([middle[0]-v[0]*offset,middle[1]-v[1]*offset]);
 let outer;
 if(plus!==minus)outer=plus?near:far;
 else {const c=rooms.find(r=>r.c)?.c;if(!c)return null;outer=(c[0]-middle[0])*v[0]+(c[1]-middle[1])*v[1]>0?near:far;}
 const at=(t,z)=>[u[0]*t+v[0]*outer,u[1]*t+v[1]*outer,z];
 const sign=outer===near?-1:1;
 return {corners:[at(lo,bottom),at(hi,bottom),at(hi,top),at(lo,top)],normal:[v[0]*sign,v[1]*sign,0],center:at((lo+hi)/2,(bottom+top)/2)};
}

// Closed, shared corner vertices: adjacent ribbon edges cannot leave a gap.
// For very narrow CAD details reduce the whole ring's inset/width together,
// rather than deleting individual pieces of the selection outline.
function joinedSelectionRibbons(polygon,inset=.24,halfWidth=.035){
 const inRing=(p,ring)=>{let inside=false;for(let i=0,j=ring.length-1;i<ring.length;j=i++){
  const a=ring[i],b=ring[j];if((a[1]>p[1])!==(b[1]>p[1])&&p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0])inside=!inside;
 }return inside;};
 const inside=p=>inRing(p,polygon.o)&&!(polygon.h||[]).some(h=>inRing(p,h));
 const result=[];
 for(const [ri,raw] of [polygon.o,...(polygon.h||[])].entries()){
  const ring=raw.filter((p,i)=>!i||Math.hypot(p[0]-raw[i-1][0],p[1]-raw[i-1][1])>1e-7);
  if(ring.length>1&&Math.hypot(ring[0][0]-ring.at(-1)[0],ring[0][1]-ring.at(-1)[1])<1e-7)ring.pop();
  if(ring.length<3)continue;
  let area=0;for(let i=0;i<ring.length;i++){const a=ring[i],b=ring[(i+1)%ring.length];area+=a[0]*b[1]-b[0]*a[1];}
  const sign=(area>=0?1:-1)*(ri===0?1:-1);
  const normals=ring.map((a,i)=>{const b=ring[(i+1)%ring.length],len=Math.hypot(b[0]-a[0],b[1]-a[1]);return [-(b[1]-a[1])/len*sign,(b[0]-a[0])/len*sign];});
  const joins=ring.map((p,i)=>{const a=normals[(i+ring.length-1)%ring.length],b=normals[i],den=1+a[0]*b[0]+a[1]*b[1];
   let x=den>1e-6?(a[0]+b[0])/den:b[0],y=den>1e-6?(a[1]+b[1])/den:b[1];
   const length=Math.hypot(x,y);if(length>4){x*=4/length;y*=4/length;}return [x,y];
  });
  const offset=d=>ring.map((p,i)=>[p[0]+joins[i][0]*d,p[1]+joins[i][1]*d]);
  const fits=loop=>loop.every((a,i)=>{const b=loop[(i+1)%loop.length],n=Math.max(1,Math.ceil(Math.hypot(b[0]-a[0],b[1]-a[1])/.1));
   for(let j=0;j<=n;j++)if(!inside([a[0]+(b[0]-a[0])*j/n,a[1]+(b[1]-a[1])*j/n]))return false;return true;
  });
  for(let attempt=0;attempt<16;attempt++){
   const scale=2**(-attempt/2),outer=offset((inset-halfWidth)*scale),inner=offset((inset+halfWidth)*scale);
   if(fits(outer)&&fits(inner)){result.push({outer,inner,inset:inset*scale});break;}
  }
 }
 return result;
}

// Inventory of existing controls: read-only copies, no automatic calculation,
// tactical placements or changes to saved opening states.
async function createMenuReview(panel,viewer){
 const drawer=document.createElement('aside');drawer.id='pyroMenuReview';drawer.setAttribute('aria-label','전체 메뉴 검토');
 drawer.innerHTML='<header><strong>전체 메뉴·표시 검토</strong><button type="button" id="reviewClose">3D로 돌아가기</button></header><p>삭제 전 검토용입니다. 아래는 현재·이전 메뉴를 모두 펼친 읽기 전용 목록입니다. 숨겨졌던 기능도 나열하며, 표시 효과를 한꺼번에 켜거나 계산·저장을 실행하지 않습니다.</p><nav id="reviewNav"></nav><div id="reviewSections"></div>';
 document.body.append(drawer);drawer.querySelector('#reviewClose').onclick=()=>{drawer.hidden=true;};
 const sections=drawer.querySelector('#reviewSections'),nav=drawer.querySelector('#reviewNav');let serial=0;
 const section=title=>{const host=document.createElement('section');host.className='reviewSection';host.id='reviewSection'+(++serial);const h=document.createElement('h3');h.textContent=title;host.append(h);sections.append(host);const button=document.createElement('button');button.textContent=title;button.onclick=()=>host.scrollIntoView({block:'start'});nav.append(button);return host;};
 const reveal=root=>{
  for(const node of [root,...root.querySelectorAll('*')]){
   if(node.id)node.id='reviewCopy'+serial+'_'+node.id;
   node.removeAttribute('hidden');node.removeAttribute('onclick');
   if(node.style){node.style.removeProperty('display');node.style.removeProperty('visibility');node.style.removeProperty('position');node.style.removeProperty('inset');node.style.removeProperty('width');node.style.removeProperty('max-height');node.style.removeProperty('height');}
   if(node.tagName==='DETAILS')node.open=true;
   if(node.matches('button,input,select,textarea'))node.disabled=true;
   if(node.tagName==='A'){node.removeAttribute('href');node.setAttribute('aria-disabled','true');}
  }
  for(const script of root.querySelectorAll('script'))script.remove();
 };
 const snapshot=(title,node)=>{if(!node)return;const host=section(title),copy=node.cloneNode(true);
  const sourceControls=node.querySelectorAll('input,select,textarea'),copies=copy.querySelectorAll('input,select,textarea');
  sourceControls.forEach((source,i)=>{copies[i].value=source.value;if('checked' in source)copies[i].checked=source.checked;});
  reveal(copy);host.append(copy);
 };
 snapshot('1 · 현재 간략 재생 / 표시 / MC 결과',panel);
 snapshot('2 · 건물·층·문·창·계단·승강기 설정',document.getElementById('p'));
 snapshot('3 · 기존 작전 표시 / 차량·인원·화점·소방시설',document.getElementById('legacyTools'));
 try{
  const source=await (await fetch('/cfbt/overlay.js')).text(),match=source.match(/panel\.innerHTML=`([\s\S]*?)`;/);
  if(match){const node=document.createElement('div');node.innerHTML=match[1];snapshot('4 · 이전 CFAST 재생·점화 비교·계산 조건 (간략 결과에 미연결)',node);}
 }catch(e){const p=document.createElement('p');p.textContent='이전 메뉴 로드 실패: '+e.message;sections.append(p);}
 const modules=[['5 · 동결 정밀 r8 설정·저장된 결과','./frozen_rule_controls.js','attachFrozenRules'],['6 · 문 자동 분류·정정 메뉴','./lite_doors.js','attachLiteDoors'],['7 · 화점 선별·상위 N·비교 결과','./screening.js','attachScreening']];
 for(const [title,path,method] of modules){
  const host=section(title),disabled=document.createElement('fieldset');disabled.disabled=true;host.append(disabled);
  try{const module=await import(path);await module[method](disabled,method==='attachFrozenRules'?()=>{throw Error('메뉴 검토 화면에서는 계산하지 않습니다.');}:viewer);for(const d of disabled.querySelectorAll('details'))d.open=true;}
  catch(e){const p=document.createElement('p');p.textContent='메뉴 로드 실패: '+e.message;host.append(p);}
 }
 const note=document.createElement('p');note.textContent='입력란이 회색인 것은 검토용이기 때문입니다. 유지·삭제할 항목을 지정하면 실제 메뉴에 반영합니다. 기존 작전 표시는 계산된 화재·연기와 별개의 수동 기호입니다.';sections.append(note);
 return drawer;
}
