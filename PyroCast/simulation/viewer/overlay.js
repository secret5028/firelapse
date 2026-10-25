// CFAST results on the preserved CAD scene. Values come exclusively from the completed payload.
import {createRealView} from './legacy_real_bridge.js';
import {riskFor} from './risk.js';
import {createCeilingJets} from './ceiling_jets.js';
import {createSmokeTransport,smokeTimeline,smokePresent} from './smoke_transport.js';
export async function attach(viewer){
 const liteResponse=await fetch('/cfbt/lite/active.json');
 if(liteResponse.ok&&!new URL(location.href).searchParams.has('legacy')){
  const lite=await liteResponse.json();if(lite?.engine_kind==='pyrocast_lite')return (await import('./lite_viewer.js')).attachLite(viewer,lite);
 }
 const {THREE:T,B,S,C,O,R,L2,groups,ext,shp,leaves,glassM,legacyRoot}=viewer;
 const style=document.createElement('link');style.rel='stylesheet';style.href='/cfbt/overlay.css';document.head.append(style);
 const panel=document.createElement('section');panel.id='cfbtPanel';panel.setAttribute('aria-label','CFBT 건물 시뮬레이션');
 panel.innerHTML=`<div class="row"><strong>CFBT · 기존 건물 연결</strong><span class="grow"></span><button id="cfbtFold" type="button" aria-expanded="true">접기</button></div>
 <div id="cfbtBody"><div class="row"><button id="cfbtBasic" type="button" aria-pressed="false">기본 모드</button><button id="cfbtReal" type="button" aria-pressed="true">실감 보기</button><button id="cfbtPlay" type="button" disabled>재생</button><select id="cfbtSpeed" aria-label="재생 배속"><option value="1">1배</option><option value="5">5배</option><option value="10">10배</option><option value="20" selected>20배</option><option value="30">30배</option><option value="60">60배</option></select><select id="cfbtMode" aria-label="계산 결과 표시"><option value="temperature">온도 + 연기</option><option value="smoke">연기 농도</option><option value="oxygen">산소 농도</option></select><span class="grow"></span><output id="cfbtClock">계산 결과 대기</output></div>
 <div class="row"><button id="cfbtSmokeReplay" type="button">층 전체 연기 확산 재생</button><button id="cfbtVerticalReplay" type="button" disabled>층간 코어 연기 보기</button><label><input id="cfbtSmokeFlow" type="checkbox" checked>문 통과 회색 연기</label><label><input id="cfbtJets" type="checkbox" checked>천장 제트</label><label>저장 결과 <select id="cfbtCases" aria-label="저장 결과"><option value="latest">현재 / 최근 계산</option></select></label></div>
 <div class="row"><label>조건 <select id="cfbtPhenomenon"><option value="all">위험 유형 전체</option><option value="fo">FO 조건</option><option value="upper_gas">상층 가스 반응 조건</option><option value="backdraft">백드래프트 조건</option><option value="fgi">FGI 선별 조건</option><option value="rapid">급격한 온도 상승 조건</option></select></label><label><input id="cfbtVentHeat" type="checkbox" checked>개구부 연소 · 청록 화살표/kW</label><label><input id="cfbtFuelMarkers" type="checkbox" checked>연료군 위치 기호</label><span>설정한 조건의 충족 여부와 모델 계산량 표시입니다. 발생 예측이 아닙니다.</span></div>
 <div id="cfbtGeometryNotice" class="warning" role="status"></div><div id="cfbtIteration" role="status"></div><div id="cfbtActualState" role="status"></div><div id="cfbtWindowStatus" role="status"></div><details><summary>선택 실 조건표 · 정도</summary><div id="cfbtConditions"></div><div id="cfbtVentDetails"></div></details>
 <div class="row"><button id="cfbtIgnite" type="button">선택 실·현재 시점 점화 비교</button><label>반응률(1/s) <input id="cfbtIgniteRate" type="number" min=".01" max="1" step=".01" value=".2"></label><select id="cfbtCompareView" aria-label="점화 비교 결과" disabled><option value="baseline">기준 계산</option><option value="ignited">점화 가정</option></select><button id="cfbtDemoCompare" type="button">저장된 예시 점화 비교</button></div>
 <div class="row"><button id="cfbtGasReplay" type="button" disabled>FGI 가정 점화 재생</button><button id="cfbtGasBefore" type="button" disabled>가스 점화 직전</button><button id="cfbtGasAfter" type="button" disabled>가스 점화 5초 후</button><span>가스 화염 표현 끔 · 추가연소에 따른 온도·산소·연기는 계산값으로 표시</span></div><div id="cfbtGasDetail" role="status"></div><div id="cfbtComparison" role="status">점화원 30초 유지 가정 · 기존 연기층 연료·산소만 사용 · 발생 확률 아님</div>
 <input id="cfbtTime" type="range" min="0" max="1" step="1" value="0" disabled aria-label="시뮬레이션 시간">
 <div id="cfbtLegend"><span class="gradient"></span> 20→600℃ · 회색: 미계산 · 화살표: 문·층간 유량</div>
 <div id="cfbtSmokeScope" role="status"></div><details><summary>실별 연기 확산 순서 · 첫 관측</summary><div id="cfbtSmokeTimeline"></div></details><div id="cfMeaning"></div><output id="cfbtRealStats" aria-label="실감 보기 표시 상태"></output>
 <div class="row"><label>실 <select id="cfbtRoom" aria-label="계산 실 선택"></select></label><button id="cfbtFocus" type="button">실 확대</button><label><input id="cfbtArrows" type="checkbox" checked>유동</label><label><input id="cfbtSmoke" type="checkbox" checked>연기층</label></div>
 <div class="row"><label>연소점 <select id="cfbtFirePoint" aria-label="연소점 선택"></select></label><button id="cfbtFireFocus" type="button">연소점 확대</button><button id="cfbtBefore" type="button">착화 30초 전</button><button id="cfbtAfter" type="button">착화 60초 후</button><button id="cfbtReplay" type="button">착화 장면 재생</button><label>화염 표시 <select id="cfbtFlameDisplay" aria-label="화염 표시 크기"><option value="compact">작은 화염 기호</option><option value="native">계산 크기 · 실 경계 제한</option></select></label><label>연기 표시 불투명도 <select id="cfbtSmokeOpacity" aria-label="연기 표시 불투명도"><option value="1">100%</option><option value=".4">40% · 내부 관찰</option><option value=".15">15% · 내부 관찰</option></select></label></div><div id="cfbtEventDetail" role="status"></div>
 <div id="cfbtDetail" role="status">저장된 결과를 불러오는 중…</div><canvas id="cfbtChart" aria-label="선택 실 온도와 연기 농도 시계열"></canvas>
 <div class="row" id="cfbtEvents" aria-label="착화 사건"></div><div id="cfbtStatus" role="status"></div><div id="cfbtBusy" role="status"></div><div id="cfbtError" role="alert"></div>
 <details id="cfbtConfig"><summary>계산 조건 · 임계값 변경</summary><div id="cfbtConfigGrid">
 <label>범위 <select id="cfbtScope"><option value="floor">화재층</option><option value="vertical">화재층 + 전층 코어·출입 공간</option><option value="building">연결 건물 전체</option></select></label>
 <label>화점 층 <select id="cfbtFireFloor"></select></label><label>화점 실 <select id="cfbtFireRoom"></select></label>
 <label>기간 <select id="cfbtDuration"><option value="1800">30분</option><option value="3600">1시간</option></select></label>
 <label>계산 방식 <select id="cfbtIterationMode"><option value="fixed_point">기존 · 일괄 반영 최대 3회</option><option value="earliest_single">기존 · 사건 1건씩</option><option value="native_room_rule" disabled>검증 중 · 실 전환 규칙 (기본 적용 보류)</option></select></label>
 <label>실 전환 프리셋 <select id="cfbtRoomPreset"><option value="conservative">착화기준 1.2배 · 180초</option><option value="standard" selected>착화기준 1배 · 60초</option><option value="aggressive">착화기준 0.8배 · 30초</option></select></label>
 <label>변경할 연료 착화기준 배율 <input id="cfbtRoomFlux" type="number" min=".1" step=".1" placeholder="프리셋"></label><label>변경할 상승시간(초) <input id="cfbtRoomRamp" type="number" min="1" placeholder="프리셋"></label><span>실 전환 규칙: 가스 추가연소·개별 연료 착화·별도 FO 확대는 끔. 30분 시나리오 회차당 10분, 1시간 시나리오 20분 제한.</span>
 <label>추가연소 <select id="cfbtGasModel"><option value="mixture">혼합물 · 공통 반응률</option><option value="legacy">기존 미연 연료</option></select></label><label>가스 착화(℃) <input id="cfbtGasT" type="number" min="20" max="1500" value="520"></label>
 <label>고온 조건(℃) <input id="cfbtHotT" type="number" min="20" max="1500" value="300"></label>
 <label>최소 O₂(체적%) <input id="cfbtO2" type="number" min=".1" max="30" step=".1" value="12"></label>
 <label>FGI 위험 연료(질량%) <input id="cfbtFGIFuel" type="number" min=".01" max="20" step=".1" value=".5"></label>
 <label>FGI 위험 O₂(체적%) <input id="cfbtFGIO2" type="number" min=".1" max="21" step=".1" value="10"></label>
 <label>연소 속도 기준(1/s) <input id="cfbtRate" type="number" min="0" max="10" step=".01" value=".1"></label>
 <label>화원 기부 높이(m·비우면 착화면) <input id="cfbtFireBase" type="number" min="0" max="3" step=".01" placeholder="착화면 높이"></label><label>고체 착화(℃) <input id="cfbtSolidT" type="number" min="30" max="1500" value="369"></label>
 <label><input id="cfbtFullFloor" type="checkbox" checked>선택 층 전체 · 착화 용량 자동</label>
 <label>수동 추가 착화 상한 <input id="cfbtLimit" type="number" min="0" max="1000" value="3"></label>
 <label><input id="cfbtWindowEnabled" type="checkbox">화재에 의한 외기 창 파괴</label>
 <label>창 기준 <select id="cfbtWindowCriterion"><option value="TEMPERATURE">판 표면온도(℃)</option><option value="FLUX">순정 가중 전면 열유속(kW/㎡)</option></select></label>
 <label>창 파괴 기준값 <input id="cfbtWindowThreshold" type="number" min="0.01" step="any" value="450"></label>
 <label>파괴 후 최종 개방률(%) <input id="cfbtWindowPost" type="number" min="0" max="100" value="100"></label>
 <label><input id="cfbtFOEnabled" type="checkbox" checked>FO 후 실 단위 공급 확대</label>
 <label>FO 기준(℃) <input id="cfbtFOT" type="number" min="100" max="1500" value="600"></label>
 <label><input id="cfbtPilot" type="checkbox" checked>점화원 가정</label>
 <label>문·창 조건 <select id="cfbtDoors"><option value="retain">마지막 계산 유지</option><option value="viewer">현재 3D 개방률 적용</option><option value="open">문 열림·창 닫힘</option></select></label>
 </div><p>창 기본값: 일반 단판 6 mm 대용 · 표면 450℃ 초과 · 5초 관측. 문헌 참고값이며 NIST 공통 파괴온도가 아닙니다. 파괴 후 100%는 사용자 개방 가정입니다. 유리 투과·창틀·균열은 생략하며 불투명 판 근사로 개방이 일러질 수 있습니다.</p><button id="cfbtRun" type="button">이 조건으로 계산</button><div id="cfbtMeta">층평균 탐색 계산 · 임계값은 사용자 가정 · 추가 착화는 성공한 재계산 뒤 확정</div></details><details><summary>계산의 간략화·한계</summary><div id="cfbtLimits"></div></details></div>`;
 document.body.append(panel);
 const sceneCaption=document.createElement('div');sceneCaption.className='cfbtSceneCaption';sceneCaption.setAttribute('role','status');
 document.getElementById('v').append(sceneCaption);
 document.getElementById('cfbtMode').add(new Option('위험 유형 · 조건 표시','risk'));
 document.getElementById('cfbtMode').value='risk';
 const menu=document.createElement('button');menu.id='cfbtMenuToggle';menu.textContent='건물 설정';menu.type='button';document.body.append(menu);
 const $=id=>document.getElementById(id);let data=null,now=0,playing=false,last=0,mode='risk',selected=null,busy=false,poll=null,lastFloor='',activeRequest=null,comparison=null,comparisonCase='latest';
 let ceilingJets=null,periodRisk=new Set(),roomViews=[],flowViews=[],fireViews=[],fuelViews=[],windowViews=[],repairViews=[],hiddenGlass=[],smokeRows=[],smokeTransport=null,root=null,realRenderer=null,realView=true,selectedFire=null,currentCase='latest',fireFocused=false,remembering=false,lastSaved=-Infinity,restoredView=null;
 try{restoredView=JSON.parse(localStorage.getItem('pyrocast-cfbt-scene')||'null');}catch{}
 try{realView=localStorage.getItem('pyrocast-cfbt-view')!=='basic';}catch{}
 const info=await (await fetch('/cfbt/model-info')).json();
 const rgba=new T.Color();
 const hatchCanvas=document.createElement('canvas');hatchCanvas.width=hatchCanvas.height=32;const hc=hatchCanvas.getContext('2d');hc.fillStyle='#7a8790';hc.fillRect(0,0,32,32);hc.strokeStyle='#3f4a52';hc.lineWidth=7;hc.beginPath();hc.moveTo(-8,24);hc.lineTo(24,-8);hc.moveTo(8,40);hc.lineTo(40,8);hc.stroke();const hatchTexture=new T.CanvasTexture(hatchCanvas);hatchTexture.wrapS=hatchTexture.wrapT=T.RepeatWrapping;hatchTexture.repeat.set(.35,.35);let conditionStamp='';
 const color=temp=>{const stops=[[20,'#2c73bc'],[100,'#f3c34b'],[300,'#ec6029'],[600,'#9b1337']];if(temp<=20)return new T.Color(stops[0][1]);for(let i=1;i<stops.length;i++)if(temp<=stops[i][0])return new T.Color(stops[i-1][1]).lerp(new T.Color(stops[i][1]),(temp-stops[i-1][0])/(stops[i][0]-stops[i-1][0]));return new T.Color(stops.at(-1)[1]);};
 const stamp=t=>`${Math.floor(t/60).toString().padStart(2,'0')}:${Math.floor(t%60).toString().padStart(2,'0')}`;
 function sample(values,time=now){if(!values||!data)return 0;const times=data.time_s;let lo=0,hi=times.length-1;while(hi-lo>1){const m=(hi+lo)>>1;if(times[m]<=time)lo=m;else hi=m;}const f=Math.max(0,Math.min(1,(time-times[lo])/(times[hi]-times[lo]||1)));if(Array.isArray(values[lo]))return values[lo].map((v,i)=>v+(values[hi][i]-v)*f);return values[lo]+(values[hi]-values[lo])*f;}
 function sampleIndex(){let i=0;while(i+1<data.time_s.length&&data.time_s[i+1]<=now)i++;return i;}
 function heatLabel(){const canvas=document.createElement('canvas');canvas.width=384;canvas.height=64;const context=canvas.getContext('2d'),texture=new T.CanvasTexture(canvas),sprite=new T.Sprite(new T.SpriteMaterial({map:texture,transparent:true,depthTest:false,depthWrite:false}));sprite.scale.set(4.8,.8,1);sprite.renderOrder=30;return {sprite,set(text){if(canvas.dataset.text===text)return;canvas.dataset.text=text;context.clearRect(0,0,384,64);context.fillStyle='#102838ed';context.fillRect(0,0,384,64);context.font='bold 25px sans-serif';context.fillStyle='#46ede2';context.fillText(text,8,43);texture.needsUpdate=true;}};}
 const field=(state,name)=>sample(state[name]);
 function roomLabel(room){const raw=B.floors.find(f=>f.name===room.cad_floor)?.rooms.find(r=>r.id===room.cad_room);const names=(room.cad_names||raw?.names||[]).filter(x=>x&&!['갑','화','-','유'].includes(x));return `${room.cad_floor} ${room.cad_room} · ${[...new Set(names)].join(' / ')||((raw?.tags||[]).includes('stair_inside')?'계단실':'용도 미확인')}`;}
 function resize(){document.documentElement.style.setProperty('--cfbt-height',panel.getBoundingClientRect().height+'px');const viewport=$('v'),w=Math.max(1,viewport.clientWidth),h=Math.max(1,viewport.clientHeight);R.setSize(w,h);L2?.setSize(w,h);C.aspect=w/h;C.updateProjectionMatrix();}
 window.addEventListener('resize',resize);
 new ResizeObserver(resize).observe(panel);
 menu.onclick=()=>{document.body.classList.toggle('cfbtMenus');menu.textContent=document.body.classList.contains('cfbtMenus')?'3D로 돌아가기':'건물 설정';resize();};
 $('cfbtFold').onclick=()=>{const closed=$('cfbtBody').hidden=!$('cfbtBody').hidden;$('cfbtFold').textContent=closed?'펼치기':'접기';$('cfbtFold').setAttribute('aria-expanded',String(!closed));resize();};
 info.floors.forEach(f=>$('cfbtFireFloor').add(new Option(f.name,f.name)));$('cfbtFireFloor').value=info.floors.some(f=>f.name==='3F')?'3F':info.floors[0]?.name;
 function fireRooms(){const floor=info.floors.find(f=>f.name===$('cfbtFireFloor').value);$('cfbtFireRoom').replaceChildren();if(!floor)return;floor.rooms.forEach(r=>$('cfbtFireRoom').add(new Option(`${r.id} · ${Number(r.area_m2||0).toFixed(1)}㎡`,r.id)));if(floor.rooms.some(r=>r.id==='R9'))$('cfbtFireRoom').value='R9';}
 fireRooms();$('cfbtFireFloor').onchange=fireRooms;
 function dispose(){for(const [mesh,visible] of hiddenGlass)mesh.visible=visible;hiddenGlass=[];windowViews=[];repairViews=[];fuelViews=[];if(root){const seen=new Set();root.traverse(obj=>{if(obj.geometry&&!seen.has(obj.geometry)){seen.add(obj.geometry);obj.geometry.dispose();}if(obj.material){for(const mat of Array.isArray(obj.material)?obj.material:[obj.material]){for(const uniform of Object.values(mat.uniforms||{})){const texture=uniform.value;if(texture?.isTexture&&!seen.has(texture)){seen.add(texture);texture.dispose();}}if(!seen.has(mat)){seen.add(mat);mat.dispose();}}}});root.removeFromParent();}realRenderer?.detach();realRenderer=null;roomViews=[];flowViews=[];fireViews=[];}
 function install(payload){
  if(payload.schema!=='pyrocast-cad-playback-1'||payload.building_sha256!==info.building_sha256)throw Error('다른 건물의 계산 결과입니다. 표시하지 않습니다.');
  if(!payload.complete||!payload.time_s?.length)throw Error('완료되지 않은 계산 결과입니다.');
  dispose();data=payload;now=0;playing=false;fireFocused=false;root=new T.Group();root.name='CFBT 계산 결과';S.add(root);legacyRoot.visible=false;
  $('cfbtGeometryNotice').textContent=[data.geometry_correction_notice,data.fuel_layout_notice].filter(Boolean).join(' · ');
  for(const f of B.floors)for(const room of f.rooms.filter(r=>(r.tags||[]).includes('terrace'))){
   const label=heatLabel();label.set('테라스 · 실외');label.sprite.scale.set(12,2,1);label.sprite.position.set(room.c[0],room.c[1],f.z+1.3);label.sprite.userData.terraceFloor=f.name;root.add(label.sprite);
  }
  smokeRows=smokeTimeline(data);smokeTransport=createSmokeTransport(T,data,root);ceilingJets=createCeilingJets(T,data,root);
  periodRisk=new Set(data.rooms.filter(r=>data.time_s.some(t=>riskFor(data.solvers[r.solver_id],t,data.time_s).color)).map(r=>r.key));
  $('cfbtGasModel').value=data.gas_model==='mixture_v1'?'mixture':'legacy';
  $('cfbtSmokeTimeline').replaceChildren();
  for(const row of [...smokeRows].sort((a,b)=>(a.first_s??Infinity)-(b.first_s??Infinity))){const button=document.createElement('button');button.type='button';button.textContent=`${row.room.cad_floor} ${row.room.cad_room} · ${row.first_s===null?(row.internal_openings?'연기 미관측':'연결 미확인·연기 미관측'):stamp(row.first_s)+' 첫 관측'}`;button.onclick=()=>{selected=row.room;$('cfbtRoom').value=selected.key;viewer.setFloor(selected.cad_floor);now=row.first_s??now;playing=false;update();};$('cfbtSmokeTimeline').append(button);}
  // Existing saved tactical flames are not simulation events.
  for(const f of B.floors)for(const r of f.rooms){const mesh=groups.find(g=>g.name===f.name)?.children.find(o=>o.name===f.name+'_'+r.id);if(mesh?.material?.color)mesh.material.color.set((r.tags||[]).includes('outdoor')?'#829a84':'#626d76');}
  for(const room of data.rooms){
   const solver=data.solvers[room.solver_id];if(!solver)throw Error('실 대응 정보 누락: '+room.key);
   const rg=new T.Group();rg.name='cfbt_'+room.key;root.add(rg);
   const lowMat=new T.MeshBasicMaterial({color:'#2c73bc',transparent:true,opacity:.06,depthWrite:false,side:T.DoubleSide});
   const upperMat=lowMat.clone();const polygons=room.cad_polys;
   const low=ext(polygons,0,1,lowMat),upper=ext(polygons,0,1,upperMat);rg.add(low,upper);
   const floor=new T.Mesh(new T.ShapeGeometry(polygons.map(shp)),new T.MeshBasicMaterial({color:'#2c73bc',transparent:true,opacity:.50,depthWrite:false,side:T.DoubleSide}));floor.position.z=room.z_m+.045;rg.add(floor);
   const outline=new T.LineSegments(new T.EdgesGeometry(new T.ShapeGeometry(polygons.map(shp))),new T.LineBasicMaterial({color:'#ffe39a',transparent:true,opacity:0}));outline.position.z=room.z_m+.065;rg.add(outline);
   const ceiling=new T.Mesh(new T.ShapeGeometry(polygons.map(shp)),new T.MeshBasicMaterial({color:'#a7c4d4',transparent:true,opacity:.07,depthWrite:false,side:T.DoubleSide}));ceiling.position.z=room.z_m+solver.height_m;rg.add(ceiling);const ceilingLine=new T.LineSegments(new T.EdgesGeometry(ceiling.geometry),new T.LineBasicMaterial({color:'#a7c4d4',transparent:true,opacity:.35}));ceilingLine.position.z=ceiling.position.z;rg.add(ceilingLine);
   roomViews.push({room,solver,rg,low,upper,floor,outline});
  }
  for(const opening of data.openings){
   const geometry=opening.cad_geometry;if(!geometry)continue;
   const group=new T.Group();root.add(group);
   const arrows=[];for(let di=0;di<2;di++){const arrow=new T.ArrowHelper(new T.Vector3(1,0,0),new T.Vector3(),1,'#73d3e8',.35,.18);for(const part of [arrow.line,arrow.cone]){part.material.depthTest=false;part.material.depthWrite=false;part.renderOrder=20;}group.add(arrow);arrows.push(arrow);}
   const heatGroup=new T.Group();root.add(heatGroup);const heat=[];
   for(let di=0;di<2;di++){const arrow=new T.ArrowHelper(new T.Vector3(1,0,0),new T.Vector3(),1,'#46ede2',.45,.24);heatGroup.add(arrow);const label=heatLabel();heatGroup.add(label.sprite);heat.push({arrow,label});}
   flowViews.push({opening,group,arrows,heatGroup,heat});
   if(opening.topology_correction){
    const repair=new T.Group(),frame=opening.cad_geometry,height=opening.top_m-(opening.bottom_m||0);root.add(repair);
    repair.position.set(...frame.center_m);repair.position.z+=(opening.bottom_m||0)+height/2;
    repair.rotation.z=Math.atan2(frame.tangent[1],frame.tangent[0]);
    const outline=new T.LineSegments(new T.EdgesGeometry(new T.BoxGeometry(opening.width_m,.05,height)),new T.LineBasicMaterial({color:'#f1b954',transparent:true,opacity:.8}));repair.add(outline);repairViews.push({opening,repair});
    for(const mesh of glassM)if(mesh.userData.win?.floor===opening.cad_floor&&mesh.userData.win?.id===opening.cad_opening){hiddenGlass.push([mesh,mesh.visible]);mesh.visible=false;}
   }
   if(opening.window_state){
    const wg=new T.Group(),frame=opening.cad_geometry,height=opening.top_m-(opening.bottom_m||0);root.add(wg);
    wg.position.set(...frame.center_m);wg.position.z+=(opening.bottom_m||0)+height/2;
    wg.rotation.z=Math.atan2(frame.tangent[1],frame.tangent[0]);
    const panes=[-1,1].map(sign=>{const pane=new T.Mesh(new T.BoxGeometry(1,.025,height),new T.MeshBasicMaterial({color:'#84c9dc',transparent:true,opacity:.28,depthWrite:false}));wg.add(pane);return {pane,sign};});
    const outline=new T.LineSegments(new T.EdgesGeometry(new T.BoxGeometry(opening.width_m,.05,height)),new T.LineBasicMaterial({color:'#7ec8de',transparent:true,opacity:.45}));wg.add(outline);
    windowViews.push({opening,wg,panes,outline});
    for(const mesh of glassM)if(mesh.userData.win?.floor===opening.cad_floor&&mesh.userData.win?.id===opening.cad_opening){hiddenGlass.push([mesh,mesh.visible]);mesh.visible=false;}
   }
   if(opening.cad_opening){for(const leaf of leaves.filter(l=>l.floor===opening.cad_floor&&l.id===opening.cad_opening))leaf.pct=opening.schedule[0][1]*100;}
  }
  for(const fire of data.fires){
   const g=new T.Group();g.position.set(...fire.position_m);root.add(g);
   const disc=new T.Mesh(new T.CircleGeometry(.65,28),new T.MeshBasicMaterial({color:fire.kind==='initial'?'#ff6c30':'#ffe16a',transparent:true,opacity:.9,side:T.DoubleSide,depthWrite:false,depthTest:false}));disc.renderOrder=25;g.add(disc);
   const marker=new T.Mesh(new T.ConeGeometry(.28,1.1,12),new T.MeshBasicMaterial({color:fire.kind==='initial'?'#ff6c30':'#ffe16a',transparent:true,opacity:.9,depthWrite:false,depthTest:false}));marker.renderOrder=25;marker.rotation.x=Math.PI/2;marker.position.z=.55;g.add(marker);
   const anchor=new T.Group();root.add(anchor);
   const opening=data.openings.find(v=>v.id===fire.placement?.opening_id);
   if(opening){const frame=opening.cad_geometry,c=new T.Vector3(...frame.center_m),tangent=new T.Vector3(...frame.tangent),p=new T.Vector3(...fire.position_m),half=opening.width_m/2;
    const left=c.clone().addScaledVector(tangent,-half),right=c.clone().addScaledVector(tangent,half),bottom=opening.bottom_m||0,top=opening.top_m;
    const points=[left.clone().add(new T.Vector3(0,0,bottom)),right.clone().add(new T.Vector3(0,0,bottom)),right.clone().add(new T.Vector3(0,0,top)),left.clone().add(new T.Vector3(0,0,top)),left.clone().add(new T.Vector3(0,0,bottom))];
    const material=new T.LineBasicMaterial({color:'#ffe16a',depthTest:false,depthWrite:false});
    const outline=new T.Line(new T.BufferGeometry().setFromPoints(points),material);outline.renderOrder=26;anchor.add(outline);
    const guide=new T.Line(new T.BufferGeometry().setFromPoints([new T.Vector3(c.x,c.y,p.z),p]),material);guide.renderOrder=26;anchor.add(guide);
    const n=fire.placement.normal||[1,0,0],u=new T.Vector3(-n[1],n[0],0).multiplyScalar(.25),z=new T.Vector3(0,0,.25);
    const face=new T.Line(new T.BufferGeometry().setFromPoints([p.clone().sub(u).sub(z),p.clone().add(u).sub(z),p.clone().add(u).add(z),p.clone().sub(u).add(z),p.clone().sub(u).sub(z)]),material);face.renderOrder=26;anchor.add(face);
   }
   fireViews.push({fire,g,marker,disc,anchor});
  }
  realRenderer=createRealView({THREE:T,C,groups,B},data,root);
  fuelViews=[];for(const fuel of data.fuel_units?.length?data.fuel_units:(data.solid_groups||[])){if(!fuel.position_m)continue;const edge=fuel.edge_m||.5,marker=new T.LineSegments(new T.EdgesGeometry(new T.BoxGeometry(edge,edge,edge)),new T.LineBasicMaterial({color:'#afccd5',depthTest:false,transparent:true,opacity:.9}));marker.renderOrder=27;root.add(marker);fuelViews.push({fuel,marker,edge,room:data.rooms.find(r=>r.key===fuel.cad_key)});}
  $('cfbtDemoCompare').textContent='이전 3실 예시 점화 비교';
  $('cfbtRoom').replaceChildren();for(const room of data.rooms)$('cfbtRoom').add(new Option(`${roomLabel(room)}${room.cluster_size>1?' · 묶음 '+room.cluster_size+'실':''}`,room.key));
  selected=data.rooms.find(r=>r.key===data.fire_key)||data.rooms[0];$('cfbtRoom').value=selected.key;
  $('cfbtTime').max=data.time_s.at(-1);$('cfbtTime').step='0.1';$('cfbtTime').disabled=false;$('cfbtPlay').disabled=false;$('cfbtPlay').textContent='재생';
  selectedFire=data.fires.find(f=>f.cad_key===selected.key)||data.fires[0]||null;
  $('cfbtFirePoint').replaceChildren();
  $('cfbtEvents').replaceChildren();for(const fire of [...data.fires].sort((a,b)=>a.time_s-b.time_s)){const button=document.createElement('button');button.type='button';button.textContent=`${stamp(fire.time_s)} ${fire.cad_floor} ${fire.cad_room} ${fire.kind==='initial'?'초기 화점':data.smoke_scope?.mode==='prescribed_smoke'?'추가 착화·시각 지정':'추가 착화'}`;$('cfbtFirePoint').add(new Option(button.textContent,fire.id));button.onclick=()=>chooseFire(fire,{time:fire.time_s});$('cfbtEvents').append(button);}
  for(const event of data.window_events||[]){const opening=data.openings.find(v=>v.id===event.opening_id),interval=event.observed_interval_s;if(!opening||!interval)continue;const button=document.createElement('button');button.type='button';button.textContent=`창 ${opening.cad_opening||opening.id} 개방 관측 ${stamp(interval[0])}~${stamp(interval[1])}`;button.onclick=()=>{selected=data.rooms.find(r=>r.solver_id===opening.a)||selected;$('cfbtRoom').value=selected.key;viewer.setFloor(selected.cad_floor);now=event.first_observed_change_s;playing=false;update();};$('cfbtEvents').append(button);}
  const options=data.settings.options||{};$('cfbtScope').value=data.vertical_smoke?'vertical':data.scope==='single_floor'?'floor':'building';$('cfbtVerticalReplay').disabled=!data.vertical_smoke;$('cfbtDuration').value=data.time_s.at(-1);
  $('cfbtGasT').value=data.settings.gas.gas_ignition_C;$('cfbtHotT').value=data.settings.gas.hot_C;$('cfbtO2').value=data.settings.gas.oxygen_min_vol_percent;
  $('cfbtRate').value=data.settings.gas.rate_ref_s_inv;
  // Saved result metadata below retains its actual method; the next run defaults to batch mode.
  $('cfbtIterationMode').value=data.spread_model==='room_flashover_rule_v1'?'native_room_rule':'fixed_point';
  $('cfbtRoomPreset').value=data.room_fire_rule?.preset||'standard';
  $('cfbtRoomFlux').value=data.room_fire_rule?.threshold_multiplier??'';
  $('cfbtRoomRamp').value=data.room_fire_rule?.ramp_s??'';
  conditionStamp='';
  const iteration=data.iteration;
  $('cfbtIteration').textContent=iteration?`${iteration.mode==='fixed_point'?'일괄 반복':'기존 사건별 계산'} · ${iteration.passes}회 · ${{converged:'사건 일정 안정',not_converged:'회차 상한 · 일정 미안정',no_new_ignition:'추가 후보 없음'}[iteration.terminated]||iteration.terminated}${iteration.mode==='fixed_point'?(iteration.condition_consistent?' · 조건 재확인 완료':' · 조건 불일치/자기 발열 경계 미확인 가능 · 상세 한계 확인'):''}`:'저장된 이전 결과 · 반복 진단 없음';
  $('cfbtIteration').classList.toggle('warning',iteration?.mode==='fixed_point'&&(!iteration.condition_consistent||iteration.terminated!=='converged'));
  if(data.spread_model==='room_flashover_rule_v1'){
   $('cfbtIteration').textContent=`실 전환 규칙: 시나리오 1회 + 순정 기준 1회 · ${data.room_fire_rule.preset} · ${['fuel_r3','fuel_r4'].includes(data.room_fire_rule.trigger_mode)?'기존 연료 기준 '+data.room_fire_rule.threshold_multiplier+'배':'복사열 '+data.room_fire_rule.setpoint+' kW/㎡'} · 상승 ${data.room_fire_rule.ramp_s}초 · FO 조건 판정과 전환 가정 구분`;
   $('cfbtIgnite').disabled=true;
  }
  $('cfbtFGIFuel').value=(data.settings.criteria.fgi_fuel_mass_fraction??.005)*100;$('cfbtFGIO2').value=data.settings.criteria.fgi_oxygen_vol_percent??10;
  $('cfbtFOEnabled').checked=!!data.settings.flashover?.enabled;$('cfbtFOT').value=data.settings.criteria.fo_temperature_C??600;
  $('cfbtPilot').checked=data.settings.gas.pilot_assumed;$('cfbtLimit').value=data.settings.spread.max_added_ignitions;$('cfbtSolidT').value=options.solid_ignition_C||369;$('cfbtFireBase').value=options.fuel_source_base_m??'';
  $('cfbtFullFloor').checked=!!data.settings.spread.full_floor_search;$('cfbtLimit').disabled=$('cfbtFullFloor').checked;
  const wp=data.settings.window_breakage||{};$('cfbtWindowEnabled').checked=!!wp.enabled;$('cfbtWindowCriterion').value=wp.criterion||'TEMPERATURE';$('cfbtWindowThreshold').value=wp.threshold??450;$('cfbtWindowPost').value=(wp.post_fraction??1)*100;
  $('cfbtFireFloor').value=selected.cad_floor;fireRooms();$('cfbtFireRoom').value=selected.cad_room;
  const statusNames={room_rule_completed:'실 단위 전환 규칙 완료 · 실제 FO 판정과 구분',converged:'사건 일정 안정 · 조건 재확인 상태 별도',not_converged:'반복 회차 상한 · 미수렴',prescribed_smoke:'전층 연기 계산 완료 · 고체 착화/FO 시각 지정(재예측 안 함)',no_new_ignition:'추가 후보 없음',incomplete_exposure:'전이 미평가 구역 있음',max_added_ignitions:'추가 착화 상한 도달',max_runs:'재계산 상한 도달',time_budget:'계산 예산 상한',causality_failed:'추가 이벤트 확정 중단',solver_failed:'추가 재계산 실패'};
  $('cfbtStatus').textContent=`${data.vertical_smoke?'화재층 + 전층 코어·출입 공간':data.scope==='single_floor'?selected.cad_floor+' 전체실':'연결 건물'} · ${data.rooms.length}실 / ${Object.keys(data.solvers).length}계산구획 · 균등 연료 표본 ${data.fuel_units?.length||0}개 · 고체 판정 ${data.solid_targets_count??'지정'}개 · 연료 공급 활성화 ${data.ignitions.length}건(실제 연소 실 수와 다름) · ${statusNames[data.status]||data.status}${data.pending_candidates.length?' · 미확정 '+data.pending_candidates.length+'건':''}`;
  $('cfbtMeta').textContent=`등면적 구획 근사 · ${data.excluded.length}개 제외 · 층평균 연기 · 기호는 화원 위치 표시 · 입력 ${data.final_input_sha256.slice(0,12)}`;
  $('cfbtLimits').replaceChildren();for(const text of [...(data.limitations||['이전 저장 결과: 현재 경량 설정 적용 전']),...(data.input_warnings||[]),...(data.topology_corrections?.length?[`DXF 근거 개구부 ${data.topology_corrections.filter(c=>c.action!=='classify_outdoor').length}곳 보정(황색 테두리). 문 높이는 대표값이며 원본 도면은 보존.`]:[]),...(data.vertical_smoke?['층간 계산은 화재층 전체와 다른 층의 코어·직접 출입 공간만 포함한다. 원격층 일반실·고체 착화와 외벽 창을 통한 상층 착화는 미평가다. 계단/샤프트 유효 면적은 가정값이다.']:[]),(data.spread_model==='room_flashover_rule_v1'?'균등 연료 큐브는 연료 분포 표시용이다. 이 모드에서는 표본별 착화를 계산하지 않고 실당 센서 하나와 대표 화원 하나를 사용한다.':'균등 연료 큐브는 실 전체 예산을 나눈 표본이다. 표본별 열노출·최초 착화 위치를 판정하지만 CFAST는 실당 대표 화원을 유지한다. 큐브별 독립 발열이나 화염 전면을 계산하지 않는다. FO 후에는 실 연료 통합과 분산 복사 근사를 적용한다.'),'반자 위 공간·반자 붕괴·재료별 열반응은 별도 해석하지 않으며 경계 열물성은 대표 대용값이다.',(data.spread_model==='room_flashover_rule_v1'?'확장 가스 추가연소는 꺼져 있다. 순정 연소·유동과 위험 조건표만 유지한다.':'가스 화염 표현은 꺼져 있다. 가스 추가연소 계산과 온도·산소·연기 변화는 유지한다. 실제 점화점·화염 전면·전파 속도·폭압은 계산하지 않는다.'),...(data.unevaluated_groups?.length?[`전이 미평가 연료군 ${data.unevaluated_groups.length}개`]:[])]){const p=document.createElement('p');p.textContent=text;$('cfbtLimits').append(p);}
  for(const flag of data.iteration?.final_flags||[]){const p=document.createElement('p');p.textContent=`반복 확인 ${flag.key}: ${flag.kind==='later_or_missing'?'앞선 착화를 유지했으나 이번 회차에서 자기 발열 이전 조건을 재확인하지 못함':flag.kind}`;$('cfbtLimits').append(p);}
  if(data.demonstration){const p=document.createElement('p');p.textContent=data.scenario_note||`연료 가산 시연: 에너지 ${data.demonstration.fuel_energy_multiplier}배 · 실측 조건 아님`;$('cfbtLimits').prepend(p);}
  if(data.fire_scope_summary){const s=data.fire_scope_summary;$('cfbtStatus').textContent+=` · 기간 중 실제 화원발열 >${s.observation_threshold_kW??1}kW 관측 ${s.observed_solid_rooms.length}/${s.room_count}실 · 화원 등록 ${s.registered_rooms.length}실${s.target_rooms?` · 목표 ${s.target_rooms}실 ${s.target_met?'도달':'미달'}`:''}`;}
  if(data.sensor_uncertainty?.length)$('cfbtStatus').textContent+=` · 판정 불확실: 대체 센서 ${data.sensor_uncertainty.length}개 (해당 실 상세보기)`;
  $('cfbtError').textContent=data.error||'';viewer.setFloor(selected.cad_floor);now=0;update();
  frameFloor(selected.cad_floor);
 }
 function frameFloor(floor){
  const floorRooms=data.rooms.filter(r=>floor==='all'||r.cad_floor===floor),points=floorRooms.flatMap(r=>r.cad_polys.flatMap(p=>p.o));
  if(points.length){const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]),zs=floorRooms.flatMap(r=>[r.z_m,r.z_m+data.solvers[r.solver_id].height_m]),target=new T.Vector3((Math.min(...xs)+Math.max(...xs))/2,(Math.min(...ys)+Math.max(...ys))/2,floor==='all'?(Math.min(...zs)+Math.max(...zs))/2:selected.z_m+2);
   const direction=C.position.clone().sub(O.target).normalize(),distance=Math.max(55,Math.max(Math.max(...xs)-Math.min(...xs),Math.max(...ys)-Math.min(...ys),Math.max(...zs)-Math.min(...zs))*1.5);O.target.copy(target);C.position.copy(target).addScaledVector(direction,distance);O.update();}
 }
 function focusFire(){
  if(!selectedFire||!selected)return;
  fireFocused=true;
  viewer.setFloor(selectedFire.cad_floor);
  const height=data.solvers[selected.solver_id].height_m,base=selectedFire.visuals.base_height_m;
  const flame=Math.min(height-base,Math.max(.8,...selectedFire.visuals.flame_height_m));
  const target=new T.Vector3(selectedFire.position_m[0],selectedFire.position_m[1],selected.z_m+base+flame*.5);
  const direction=C.position.clone().sub(O.target),normal=selectedFire.placement?.normal;
  if(normal)direction.set(-normal[0]-.35*normal[1],-normal[1]+.35*normal[0],0);
  direction.z=0;if(direction.lengthSq()<1e-6)direction.set(1,-1,0);direction.normalize();direction.z=.65;direction.normalize();
  const fov=C.fov*Math.PI/180,span=Math.max(3,flame+1.5),distance=Math.max(10,(selected.z_m+height+2-target.z)/direction.z,span/(2*Math.tan(fov/2)*Math.min(1,C.aspect))*1.3);
  O.target.copy(target);C.position.copy(target).addScaledVector(direction,distance);O.update();
  $('cfbtSmokeOpacity').value='.4';
 }
 function chooseFire(fire,{time=now,replay=false}={}){
  if(!fire)return;selectedFire=fire;selected=data.rooms.find(r=>r.key===fire.cad_key);$('cfbtRoom').value=selected.key;$('cfbtFirePoint').value=fire.id;
  realView=true;now=Math.max(0,Math.min(data.time_s.at(-1),time));playing=replay;if(replay)$('cfbtSpeed').value='5';last=performance.now();focusFire();update();
 }
 function drawChart(){const canvas=$('cfbtChart'),ctx=canvas.getContext('2d'),w=canvas.clientWidth,h=canvas.clientHeight,dpr=devicePixelRatio||1;canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);ctx.scale(dpr,dpr);ctx.clearRect(0,0,w,h);if(!data||!selected)return;
  const state=data.solvers[selected.solver_id],temps=state.Tu,other=comparison?($('cfbtCompareView').value==='baseline'?comparison.ignited:comparison.baseline).solvers[selected.solver_id]:null,peak=Math.max(100,...temps,...(other?.Tu||[])),odPeak=Math.max(.1,...state.ODu),end=data.time_s.at(-1),left=36,width=Math.max(1,w-90),xAt=t=>left+width*t/end;
  ctx.lineWidth=1.5;function line(values,baseline,top,colour){ctx.strokeStyle=colour;ctx.beginPath();values.forEach((v,i)=>{const x=xAt(data.time_s[i]),y=h-12-(h-29)*(v-baseline)/(top-baseline);i?ctx.lineTo(x,y):ctx.moveTo(x,y);});ctx.stroke();}
  if(comparison){const other=($('cfbtCompareView').value==='baseline'?comparison.ignited:comparison.baseline).solvers[selected.solver_id];if(other){ctx.setLineDash([4,3]);line(other.Tu,20,Math.max(peak,...other.Tu),'#ce8bff');ctx.setLineDash([]);}}
  line(temps,20,peak,'#89b8d2');line(state.ODu,0,odPeak,'#d9aa79');
  ctx.font='10px system-ui';ctx.fillStyle='#89b8d2';ctx.fillText('온도 '+Math.round(peak)+'℃',3,11);ctx.fillText('20',4,h-10);ctx.fillStyle='#d9aa79';ctx.fillText('OD '+odPeak.toFixed(1),Math.max(90,w-54),11);
  if(selectedFire?.cad_key===selected.key){ctx.strokeStyle='#ff8665';ctx.setLineDash([3,3]);ctx.beginPath();ctx.moveTo(xAt(selectedFire.time_s),16);ctx.lineTo(xAt(selectedFire.time_s),h-8);ctx.stroke();ctx.setLineDash([]);ctx.fillStyle='#ffb49b';ctx.fillText('착화 '+stamp(selectedFire.time_s),Math.min(w-110,xAt(selectedFire.time_s)+3),12);}
  ctx.strokeStyle='#f4c453';ctx.beginPath();ctx.moveTo(xAt(now),16);ctx.lineTo(xAt(now),h-8);ctx.stroke();}
 function update(){if(!data)return;const floor=viewer.getFloor();lastFloor=floor;const showSmoke=$('cfbtSmoke').checked;
  for(const child of root.children)if(child.userData.terraceFloor)child.visible=!fireFocused&&(floor==='all'||floor===child.userData.terraceFloor);
  for(const view of roomViews){const {room,solver,rg,low,upper}=view;rg.visible=floor==='all'||floor===room.cad_floor;if(!rg.visible)continue;
   const height=solver.height_m,h=solver.single_zone?0:Math.max(0,Math.min(height,field(solver,'h'))),tu=field(solver,'Tu'),tl=field(solver,'Tl'),odu=Math.max(0,field(solver,'ODu')),odl=solver.single_zone?0:Math.max(0,field(solver,'ODl'));
   low.position.z=room.z_m;low.scale.z=Math.max(.001,h);upper.position.z=room.z_m+h;upper.scale.z=Math.max(.001,height-h);
   const phenomenon=$('cfbtPhenomenon').value,risk=riskFor(solver,now,data.time_s,phenomenon);
   const uc=mode==='risk'?new T.Color(risk.color||'#687c88'):mode==='oxygen'?new T.Color('#b33c3c').lerp(new T.Color('#58bfba'),Math.min(1,field(solver,'Ou')/.21)):mode==='smoke'?new T.Color('#69737c'):color(tu);
   const lc=mode==='oxygen'?new T.Color('#b33c3c').lerp(new T.Color('#58bfba'),Math.min(1,field(solver,'Ol')/.21)):mode==='smoke'?new T.Color('#69737c'):color(tl);
   upper.material.color.copy(uc);low.material.color.copy(lc);upper.material.opacity=showSmoke?Math.min(.72,(1-Math.pow(10,-odu*3))*.65):0;
   low.material.opacity=showSmoke?Math.min(.35,(1-Math.pow(10,-odl*3))*.35):0;upper.visible=!realView&&height-h>.001;low.visible=!realView&&h>.001;
   view.floor.material.color.copy(uc);view.floor.material.opacity=mode==='smoke'?Math.min(.65,.05+(1-Math.pow(10,-odu*3))*.6):.5;
   if(mode==='risk'&&phenomenon!=='all'){
    const record=solver.conditions?.[phenomenon],i=sampleIndex(),metric=({fo:'over_C',upper_gas:'Q_bulk_kW',backdraft:'fuel_energy_MJ',fgi:'fuel_energy_MJ',rapid:'rise_C_s'})[phenomenon];
    const value=record?.intensity?.[metric]?.[i],range=data.condition_ranges?.[phenomenon]||{},min=range.min,max=range.max;
    if(value!==null&&value!==undefined&&risk.met===true)view.floor.material.color.set('#24394b').lerp(new T.Color(risk.color),max>min?(value-min)/(max-min):1);
    if(risk.met===null)view.floor.material.color.set('#7a8790');
   }
   const map=mode==='risk'&&phenomenon!=='all'&&risk.met===null?hatchTexture:null;if(view.floor.material.map!==map){view.floor.material.map=map;view.floor.material.needsUpdate=true;}
   if(realView&&mode!=='oxygen')view.floor.material.opacity=mode==='risk'&&risk.color ? .22 : .06;
   view.outline.material.color.set(mode==='risk'&&risk.color?risk.color:'#ffe39a');
   view.outline.material.opacity=mode==='risk'&&risk.color ? .95 : room.key===selected?.key ? .85 : 0;
  }
  for(const {opening,group,arrows} of flowViews){group.visible=$('cfbtArrows').checked&&(floor==='all'||floor===opening.cad_floor||data.rooms.some(r=>r.cad_floor===floor&&r.solver_id===opening.a)||opening.type==='FLOOR'&&data.rooms.some(r=>r.cad_floor===floor&&r.solver_id===opening.b));if(!group.visible)continue;
   const frame=opening.cad_geometry;for(let di=0;di<2;di++){const values=sample(di?opening.ba:opening.ab),[mass,oxygen,fuel,soot,z,temp,velocity]=values;const arrow=arrows[di];arrow.visible=mass>.0001;if(!arrow.visible)continue;
    const n=new T.Vector3(...frame.normal_a_to_b).multiplyScalar(di?-1:1);arrow.setDirection(n);const length=Math.min(3.5,.7+Math.log1p(mass)*.6);arrow.setLength(length,Math.min(.45,length*.3),.22);const p=new T.Vector3(...frame.center_m);p.z=opening.type==='FLOOR'?frame.center_m[2]:z;p.addScaledVector(new T.Vector3(...frame.tangent),di?.2:-.2);p.addScaledVector(n,-length/2);arrow.position.copy(p);arrow.setColor(new T.Color(soot>1e-8?'#d5aa6c':'#69c9f1'));}
  }
  for(const {opening,heatGroup,heat} of flowViews){heatGroup.visible=$('cfbtVentHeat').checked&&(floor==='all'||data.rooms.some(r=>r.cad_floor===floor&&(r.solver_id===opening.a||r.solver_id===opening.b)));if(!heatGroup.visible)continue;
   heat.forEach(({arrow,label},di)=>{const q=sample(di?opening.gas_ba_kW:opening.gas_ab_kW);arrow.visible=label.sprite.visible=q>0;if(!arrow.visible)return;const frame=opening.cad_geometry,n=new T.Vector3(...frame.normal_a_to_b).multiplyScalar(di?-1:1),p=new T.Vector3(...frame.center_m);p.z+=opening.type==='FLOOR'?.4:Math.max(.5,opening.top_m-.2);p.addScaledVector(new T.Vector3(...frame.tangent),di?.6:-.6);arrow.position.copy(p).addScaledVector(n,-.9);arrow.setDirection(n);arrow.setLength(1.8,.45,.24);label.sprite.position.copy(p).add(new T.Vector3(0,0,.55));label.set(`${(di?opening.b:opening.a).replace(/^CAD_[^_]+_/,'').replace('OUTSIDE','외기')} → ${(di?opening.a:opening.b).replace(/^CAD_[^_]+_/,'').replace('OUTSIDE','외기')} ${q.toFixed(1)} kW`);});
  }
  for(const {fire,g,marker,disc,anchor} of fireViews){const onFloor=floor==='all'||floor===fire.cad_floor;anchor.visible=onFloor&&fire.id===selectedFire?.id;g.visible=!realView&&onFloor&&now>=fire.time_s;if(g.visible){const q=sample(fire.Q_kW);marker.visible=q>.001;disc.material.opacity=q>.001?.9:.3;marker.scale.setScalar(Math.min(2,.7+Math.log1p(Math.max(0,q))/8));}}
  for(const [mesh] of hiddenGlass)mesh.visible=false;
  for(const {opening,repair} of repairViews)repair.visible=(floor==='all'||floor===opening.cad_floor)&&($('layer_opening')?.checked??true);
  for(const {opening,wg,panes,outline} of windowViews){const fraction=opening.fraction[sampleIndex()],changed=fraction>opening.window_state.initial_fraction+1e-8;wg.visible=(floor==='all'||floor===opening.cad_floor)&&($('layer_opening')?.checked??true);outline.material.color.set(changed?'#46ede2':'#7ec8de');outline.material.opacity=changed?1:.35;const width=opening.width_m*(1-fraction)/2;for(const {pane,sign} of panes){pane.visible=width>.001&&($('gl')?.checked??true);pane.scale.x=Math.max(.001,width);pane.position.x=sign*(opening.width_m/2-width/2);}}
  const roomWindows=data.openings.filter(v=>v.window_state&&v.a===selected?.solver_id);
  $('cfbtWindowStatus').textContent=roomWindows.length?'선택 실 창 · '+roomWindows.map(v=>{const state=v.window_state,interval=state.observed_interval_s;return `${v.cad_opening||v.id} ${Math.round(v.fraction[sampleIndex()]*100)}% 개방`+(interval&&now>=state.first_observed_change_s?` · 변화 관측 ${stamp(interval[0])}~${stamp(interval[1])}`:' · 파괴 변화 미관측');}).join(' / '):data.settings.window_breakage?.enabled?'선택 실: 평가할 외기 창 없음':'창 파괴 평가 꺼짐 · 저장된 초기 개방 조건';
  for(const {fuel,marker,edge,room} of fuelViews){const event=data.fires.find(f=>f.id===(fuel.group||fuel.id)&&now>=f.time_s),pooled=data.fo_transitions.some(e=>e.room===room?.solver_id&&now>=e.t_ign_s),local=event&&sample(event.Q_kW)>1&&Math.hypot(event.position_m[0]-fuel.position_m[0],event.position_m[1]-fuel.position_m[1])<edge;marker.visible=$('cfbtFuelMarkers').checked&&(floor==='all'||floor===room?.cad_floor);const p=fuel.position_m;marker.position.set(p[0],p[1],p[2]+edge/2);marker.material.color.set(pooled?'#ffdb58':local?'#ff8b45':'#afccd5');}
  realRenderer?.update({enabled:realView,time:now,sample,floor,smokeEnabled:showSmoke,smokeOpacity:+$('cfbtSmokeOpacity').value,flameDisplay:$('cfbtFlameDisplay').value,riskMode:mode==='risk',phenomenon:$('cfbtPhenomenon').value});
  ceilingJets?.update({show:realView&&showSmoke&&$('cfbtJets').checked,floor,sample});
  smokeTransport?.update({show:showSmoke&&$('cfbtSmokeFlow').checked,floor,sample,smokeOpacity:+$('cfbtSmokeOpacity').value});
  $('cfbtReal').setAttribute('aria-pressed',String(realView));$('cfbtBasic').setAttribute('aria-pressed',String(!realView));
  $('cfMeaning').hidden=!realView;$('cfMeaning').textContent='실감 보기 · 회색 연기: 계산 OD·층 높이 · 위험색: 연기 외곽/층 경계 · 큐브: 균등 연료 표본(회색·주황 화점·황색 FO 통합) · 작은 화염은 실제 발열 위치 기호(실제 크기 아님) · 가스 화염 표현 끔 · 가스 추가연소에 따른 온도·산소·연기 계산 유지'+(+$('cfbtSmokeOpacity').value<1?' · 내부 관찰용 투명 표시 (계산 농도 유지)':'');
  const scopeFloors=floor==='all'?[...new Set(data.rooms.map(r=>r.cad_floor))]:[floor],scopeRooms=data.rooms.filter(r=>scopeFloors.includes(r.cad_floor)),totalRooms=B.floors.filter(f=>scopeFloors.includes(f.name)).reduce((n,f)=>n+f.rooms.filter(r=>!(r.tags||[]).includes('outdoor')).length,0),smoky=scopeRooms.filter(r=>{const s=data.solvers[r.solver_id];return smokePresent(s,{h:field(s,'h'),upper:field(s,'ODu'),lower:field(s,'ODl')});}),unknown=smokeRows.filter(r=>scopeFloors.includes(r.room.cad_floor)&&!r.internal_openings).length;
  const activeRisk=scopeRooms.filter(r=>riskFor(data.solvers[r.solver_id],now,data.time_s).color).length,periodCount=scopeRooms.filter(r=>periodRisk.has(r.key)).length;
  $('cfbtSmokeScope').textContent=`${data.spread_model==='room_flashover_rule_v1'?'순정 연소 · 확장 OFF':data.gas_model==='mixture_v1'?'혼합물 추가연소':'기존 미연 연료'} · 조건 충족 현재 ${activeRisk}실 / 기간전체 ${periodCount}실 · 층 전체 연기 · ${scopeFloors.join('·')} 계산 ${scopeRooms.length}/${totalRooms}실 · 현재 연기 ${smoky.length}실 · 위험 조건 무관 표시 · 색 테두리만 조건 연동${unknown?' · 연결 미확인 '+unknown+'실':''}${totalRooms>scopeRooms.length?` · ${totalRooms-scopeRooms.length}실 미계산`:''}${data.smoke_scope?.mode==='prescribed_smoke'?' · 화원/FO 시각 지정 · 새 고체 전이 미평가':''} · 문 통과 흐름은 계산 유량 기반 표시 효과, 실제 연기 전면 예측 아님 · 천장제트 ${ceilingJets?.hasData?ceilingJets.count()+'표본 (표시속도상한8m/s)':'표본자료 없음'} · 복수조건 대표색: BD→FGI→상층→FO→급상승`;
  const realStats=realRenderer?.stats();$('cfbtRealStats').hidden=!realView;$('cfbtRealStats').textContent=realStats?`입체 연기 ${realStats.volumeCount}개 · 문 통과 연기 ${smokeTransport?.stats().activeDirections||0}방향 · 현재 고체 화염 ${realStats.flames.length}개 (>1kW) · 가스 화염 표현 OFF`:'';
  $('cfbtClock').textContent=stamp(now)+' / '+stamp(data.time_s.at(-1));$('cfbtTime').value=now;$('cfbtPlay').textContent=playing?'일시정지':'재생';
  const state=data.solvers[selected.solver_id],solid=data.fires.filter(f=>f.cad_key===selected.key).reduce((q,f)=>q+sample(f.Q_kW),0),flow=data.openings.filter(v=>v.a===selected.solver_id||v.b===selected.solver_id).reduce((m,v)=>m+sample(v.a===selected.solver_id?v.ba:v.ab)[0],0);
  const fuelAssigned=(data.solid_groups||[]).some(g=>g.cad_key===selected.key);
  const thermalText=state.single_zone?`단일층 ${field(state,'Tu').toFixed(0)}℃`:`상 ${field(state,'Tu').toFixed(0)}℃ / 하 ${field(state,'Tl').toFixed(0)}℃ · 경계 ${field(state,'h').toFixed(2)}m`;
  $('cfbtDetail').textContent=`${roomLabel(selected)} · 반자고 ${state.height_m.toFixed(2)}m (${selected.height_confidence==='tag_interpretation'?'도면 표기':({'declared':'실 설정','declared_floor_default':'층 설정','structural_proxy':'코어 구조 높이','unconfirmed':'미확인·층고 대용'}[selected.height_confidence]||'저장값')}) · ${thermalText} · O₂ ${(field(state,'Ou')*100).toFixed(1)}% · 유입 ${flow.toFixed(2)}kg/s · 고체 ${solid.toFixed(0)} / 상층 가스 ${field(state,'Qbulk_kW').toFixed(0)}kW${fuelAssigned?'':' · 고체 연료 미지정'}${selected.cluster_size>1?' · '+selected.cluster_size+'실 공유값':''}`;
  const foState=data.fo_transitions.some(e=>e.room===selected.solver_id&&now>=e.t_ign_s);
  $('cfbtActualState').textContent=`실제 상층 추가발열 ${field(state,'Qbulk_kW').toFixed(1)}kW · 잔여 가연량 ${(state.combustible_kg?field(state,'combustible_kg'):field(state,'Fu')).toFixed(2)}kg · FO 공급전환 ${foState?'적용 중':'미적용'} · 테두리는 이 발열 표시와 별개인 조건 충족 표시`;
  $('cfbtDetail').textContent+=' · '+(riskFor(state,now,data.time_s).labels.join(' / ')||'현재 위험 조건 표시 없음');
  sceneCaption.textContent=`선택: ${roomLabel(selected)} · ${stamp(now)}\n계산 반자고 ${state.height_m.toFixed(2)}m · 상층 ${field(state,'Tu').toFixed(0)}℃ · O₂ ${(field(state,'Ou')*100).toFixed(1)}% · 연기 OD ${field(state,'ODu').toFixed(2)} 1/m\n${field(state,'Qbulk_kW')>.001?'상층 가스 추가연소 계산 중 · 가스 화염 표현 끔':'가스 화염 표현 끔'}`;
  $('cfbtFirePoint').value=selectedFire?.id||'';
  for(const id of ['cfbtFireFocus','cfbtBefore','cfbtAfter','cfbtReplay'])$(id).disabled=!selectedFire;
  if(selectedFire){const fire=selectedFire,r=data.rooms.find(r=>r.key===fire.cad_key),s=data.solvers[r.solver_id],before=Math.max(0,fire.time_s-30),q=now<fire.time_s?0:sample(fire.Q_kW);
   const placement=fire.placement?.opening_id?` · ${fire.placement.source_cad_key.replace('CAD_','').replaceAll('_',' ')} 연결 개구부 ${fire.placement.opening_id.replace('CAD_','')} 안쪽 ${fire.placement.distance_from_opening_m.toFixed(1)}m · 화원 기부 ${fire.visuals.base_height_m.toFixed(2)}m${fire.placement.surface_xyz?' / 판정면 '+(fire.placement.surface_xyz[2]-selected.z_m).toFixed(2)+'m':''} · 노란선: 개구부↔착화 후보`:'';
   $('cfbtEventDetail').textContent=`${fire.cad_floor} ${fire.cad_room} · ${stamp(fire.time_s)} ${fire.kind==='initial'?'초기 화점':data.smoke_scope?.mode==='prescribed_smoke'?'추가 착화·시각 지정':'추가 착화'}${placement} · ${now<fire.time_s?'착화 전':q>0?'연소 중':combustionLabel(fire)} · 화원 ${q.toFixed(1)}kW · 계산 화염 길이 ${(now<fire.time_s?0:sample(fire.visuals.flame_height_m)).toFixed(2)}m · 상층 ${sample(s.Tu).toFixed(1)}℃ · 연기 OD ${sample(s.ODu).toFixed(3)} 1/m · 경계 ${sample(s.h).toFixed(2)}m${fire.kind==='additional'?` · 착화 30초 전 대비 온도 ${(sample(s.Tu)-sample(s.Tu,before)).toFixed(1)}℃ / OD ${(sample(s.ODu)-sample(s.ODu,before)).toFixed(3)} (전체 화재 진행 변화)`:''}`;
  }else $('cfbtEventDetail').textContent=comparison?.assumption.room===selected.solver_id?`선택 실의 가스 점화 가정 ${stamp(comparison.assumption.time_s)} · 상층 전체의 추가 연소·온도 변화로 표시 · 가스 화염 표현 끔 · 실제 점화 위치/화염 전면은 미해석`:'선택 실에 확정된 고체 연소점이 없습니다.';
  $('cfbtLegend').innerHTML=mode==='risk'?'<span style="color:#b16cff">■ FGI 선별/가정 점화</span> · <span style="color:#ee4055">■ 백드래프트 조건</span> · <span style="color:#ff9c39">■ 상층 가스 반응 조건(롤오버 관련)</span> · <span style="color:#ffdb58">■ FO 기준/전환</span> · <span style="color:#46ede2">➜ 개구부 연소(kW)</span> · 연기 외곽/층 경계·바닥 색은 가능 조건 · 회색 연기는 실제색 재현이 아닌 농도 표시 · 확률 아님':mode==='oxygen'?'산소 0% <span style="color:#58bfba">→21%</span> · 회색: 미계산 · 화살표: 연기/공기 유량':mode==='smoke'?'연기 농도: CFAST 광학밀도 · 화살표: 연기/공기 유량 · 회색 바닥: 미계산':'<span class="gradient"></span> 20→600℃ · 회색: 미계산 · 화살표: 연기/공기 유량';
  if(mode==='risk'&&$('cfbtPhenomenon').value!=='all'){const r=data.condition_ranges?.[$('cfbtPhenomenon').value],fmt=x=>x==null?'미평가':x.toFixed(2);$('cfbtLegend').textContent=`색 테두리: 선택 조건 충족 · 바닥: ${r?.key||'정도'} ${fmt(r?.min)}~${fmt(r?.max)} (계산 범위의 연속색) · 회색 빗금: 미평가 · 청록 화살표: 개구부 발열(kW) · 연료군 상자: 위치/상태 기호 · 발생 확률/확정 아님`;}
  for(const id of ['cfbtGasReplay','cfbtGasBefore','cfbtGasAfter'])$(id).disabled=!comparison;
  const gasQ=field(state,'Qbulk_kW');$('cfbtGasDetail').textContent=comparison?`${roomLabel(selected)} · ${comparison.assumption.room===selected.solver_id?`가스 점화 가정 ${stamp(comparison.assumption.time_s)} · `:''}${gasQ>.001?'상층 가스 연소 중':'현재 상층 가스 연소 없음'} · ${gasQ.toFixed(1)}kW · OD ${field(state,'ODu').toFixed(3)} 1/m · ${$('cfbtCompareView').value==='baseline'?'기준 계산':'점화 가정 계산'} · 온도·산소·연기는 같은 시점의 계산값`:'';
  showConditions();updateComparison();drawChart();saveView();
 }
 function combustionLabel(fire){
  const i=sampleIndex(),state=fire.visuals?.combustion_state?.[i];
  if(fire.transition_assumption&&now>=fire.time_s&&now<fire.prescribed_supply_start_s)return '출발실 조건 충족 · 설정된 전이 지연 대기';
  return ({inactive:'착화 조건 미충족',burning:'연소 중',supply_without_burning:'착화 조건 충족, 산소·혼합 제한으로 화원 연소 미발생',activated_no_supply:'착화 조건 충족, 현재 연료 공급 없음'})[state]||'착화 조건 충족, 현재 실제 화원 발열 없음';
 }
 function showConditions(){const i=sampleIndex(),stampKey=`${selected.key}/${$('cfbtPhenomenon').value}/${i}`;if(stampKey===conditionStamp)return;conditionStamp=stampKey;const host=$('cfbtConditions'),records=data.solvers[selected.solver_id].conditions||{};host.replaceChildren();
  const chosen=$('cfbtPhenomenon').value,names={fo:'FO 조건',upper_gas:'상층 가스 반응 조건 · 롤오버 표현',backdraft:'백드래프트 조건 · 개방 시 주의',fgi:'FGI 선별 조건',rapid:'급격한 온도 상승 조건',room_transition_display:'바닥 15 kW/㎡ 실 전환 지표 · 표시 전용, 착화에 사용하지 않음'};
  const fmt=x=>x===null||x===undefined?'미평가':typeof x==='boolean'?(x?'예':'아니오'):typeof x==='number'?x.toFixed(3):String(x);
  for(const [key,record] of Object.entries(records)){if(key==='context'||chosen!=='all'&&key!==chosen)continue;
   const title=document.createElement('p');title.textContent=`${names[key]} · 기존 조건식 ${fmt(record.all_met[i])} · 첫 충족 ${record.first_met_s===null?'없음':stamp(record.first_met_s)} · 지속 ${record.duration_s.toFixed(1)}초 (출력 해상도 ${record.resolution_s.toFixed(2)}초)`;host.append(title);
   if(['fo','fgi','backdraft','upper_gas'].includes(key)){
    const score=document.createElement('p'),s=record.scores,labels={temperature:'온도',fuel:'가연물',oxygen:'산소'};
    score.textContent=s?`조건 점수 · 세 요인 충족 ${fmt(s.all_met?.[i])} · 정도 ${fmt(s.degree?.[i])} · 병목 ${labels[s.weakest?.[i]]||'미평가'} · 우세 ${labels[s.strongest?.[i]]||'미평가'} · ${Object.entries(labels).map(([k,v])=>`${v} ${s.unbounded_factors?.[k]?.[i]?'∞':fmt(s.factors?.[k]?.[i])}`).join(' / ')} · 1.0이 설정 기준, 발생 확률 아님`:'이전 저장 결과 · 세 요인 점수 미생성(안전 또는 0점이라는 뜻이 아닙니다)';host.append(score);
   }
   if(key==='upper_gas'){const explanation=document.createElement('p');explanation.textContent='상층 발열은 프로젝트 bulk 추가연소 항입니다. native 플룸 내 상층 연소와 구별하며 롤오버 발생 확정을 뜻하지 않습니다. 온도·점화원·강제 점화는 대체 경로(OR)입니다.';host.append(explanation);}
   const table=document.createElement('table'),header=table.insertRow();for(const text of ['조건 항','현재값','기준','충족','차이']){const cell=document.createElement('th');cell.textContent=text;header.append(cell);}
   for(const term of record.terms){const row=table.insertRow(),threshold=Array.isArray(term.threshold)?term.threshold[i]:term.threshold;for(const text of [term.label,fmt(term.value[i])+' '+term.unit,term.op+' '+fmt(threshold),fmt(term.met[i]),fmt(term.margin[i])]){const cell=row.insertCell();cell.textContent=text;}row.title=term.source;}
   host.append(table);const amounts=document.createElement('p');amounts.textContent='모델 계산량: '+Object.entries(record.actual_quantities||{}).map(([k,v])=>`${k} ${fmt(v[i])}`).join(' · ');host.append(amounts);
  }
  for(const [gid,record] of Object.entries(data.conditions?._groups||{})){if(record.room!==selected.solver_id)continue;const p=document.createElement('p');
   if(record.transition_assumption)p.textContent=`연료군 ${gid}: 출발실 ${record.parent_room} 판 온도 조건 ${record.ignition_s===null?'미충족':stamp(record.ignition_s)} · 가정 지연 ${record.delay_s}초 · 공급 시작 ${record.prescribed_supply_start_s===null?'없음':stamp(record.prescribed_supply_start_s)} · 실제 연소 여부는 화원 발열로 구분 · FO 발생 예측이 아닙니다.`;
   else p.textContent=`연료군 ${gid}: ${{inactive:'미착화',active:'착화됨',fo_pool:'FO 연료 통합'}[record.state[i]]} · 착화 ${record.ignition_s===null?'없음':stamp(record.ignition_s)} · 지배 열원 ${record.cause||'초기/미지정'} · 위치 상자는 기호이며 실제 가연물 크기·배치가 아닙니다.`;host.append(p);}
  if(!Object.keys(records).length)host.textContent='이전 저장 결과 · 조건표 미생성';
  for(const sensor of data.sensor_uncertainty||[]){
   if(sensor.room!==selected.solver_id&&sensor.parent_room!==selected.solver_id&&sensor.cad_key!==selected.key)continue;
   const warning=document.createElement('p');warning.textContent=`판정 불확실 · ${sensor.sensor_id}: ${sensor.reason}`;warning.style.color='#ffdb58';host.append(warning);
  }
  for(const fire of data.fires.filter(f=>f.solver_id===selected.solver_id)){
   const p=document.createElement('p'),q=sample(fire.Q_kW);p.textContent=`화원 ${fire.id}: ${now<fire.time_s?'착화 전':q>0?'연소 중':combustionLabel(fire)} · 실제 HRR ${q.toFixed(3)} kW · 개구부 연소는 아래 별도 표시`;host.append(p);
  }

  if(['fuel_r3','fuel_r4'].includes(data.room_fire_rule?.trigger_mode))for(const record of Object.values(data.conditions?._groups||{})){
   if(record.room!==selected.solver_id||record.terms?.[0]?.key!=='native_sensor')continue;
   const term=record.terms[0],p=document.createElement('p');p.textContent=`대표 연료 착화 판정: ${fmt(term.value[i])} ${term.unit} ${term.op} ${fmt(term.threshold)} · 기존 위치·물성 재사용, 순정 판 열응답 · 문 너머 보충 열은 표시 전용`;host.append(p);
  }
  const list=data.openings.filter(v=>v.a===selected.solver_id||v.b===selected.solver_id).flatMap(v=>[[v.id,v.a,v.b,sample(v.gas_ab_kW)],[v.id,v.b,v.a,sample(v.gas_ba_kW)]]).filter(v=>v[3]>0);
  $('cfbtVentDetails').textContent='개구부 연소 (상층 가스와 별도): '+(list.map(([id,a,b,q])=>`${id} ${a} → ${b} ${q.toFixed(2)} kW`).join(' / ')||'현재 발열 없음');
 }
 function saveView(force=false){if(!remembering||!data||(!force&&performance.now()-lastSaved<1000))return;lastSaved=performance.now();try{localStorage.setItem('pyrocast-cfbt-scene',JSON.stringify({building:info.building_sha256,case:currentCase,room:selected?.key,fire:selectedFire?.id,time:now,focused:fireFocused,smokeOpacity:$('cfbtSmokeOpacity').value}));}catch{}}
 window.addEventListener('pagehide',()=>saveView(true));
 $('cfbtTime').oninput=()=>{now=+$('cfbtTime').value;playing=false;update();};$('cfbtPlay').onclick=()=>{if(now>=data.time_s.at(-1))now=0;playing=!playing;last=performance.now();update();};
 function setRealView(value){realView=value;try{localStorage.setItem('pyrocast-cfbt-view',value?'real':'basic');}catch{}update();}
 $('cfbtBasic').onclick=()=>setRealView(false);$('cfbtReal').onclick=()=>setRealView(true);
 $('cfbtSmokeReplay').onclick=()=>{if(!data)return;const floor=data.rooms.some(r=>r.cad_floor===viewer.getFloor())?viewer.getFloor():selected.cad_floor;viewer.setFloor(floor);fireFocused=false;realView=true;mode='risk';$('cfbtMode').value='risk';$('cfbtPhenomenon').value='all';$('cfbtSmoke').checked=true;$('cfbtSmokeFlow').checked=true;$('cfbtSmokeOpacity').value='1';now=0;playing=true;$('cfbtSpeed').value='20';last=performance.now();frameFloor(floor);update();panel.scrollTop=0;};
 $('cfbtVerticalReplay').onclick=()=>{if(!data?.vertical_smoke)return;$('cfbtSmokeReplay').click();viewer.setFloor('all');frameFloor('all');update();};
 $('cfbtSmokeFlow').onchange=update;$('cfbtJets').onchange=update;
 $('cfbtMode').onchange=()=>{mode=$('cfbtMode').value;update();};$('cfbtArrows').onchange=update;$('cfbtSmoke').onchange=update;
 $('cfbtPhenomenon').onchange=()=>{mode='risk';$('cfbtMode').value='risk';update();};$('cfbtVentHeat').onchange=update;$('cfbtFuelMarkers').onchange=update;
 $('cfbtSmokeOpacity').onchange=update;
 $('cfbtFlameDisplay').onchange=update;
 $('cfbtRoom').onchange=()=>{fireFocused=false;selected=data.rooms.find(r=>r.key===$('cfbtRoom').value);selectedFire=data.fires.find(f=>f.cad_key===selected.key)||null;viewer.setFloor(selected.cad_floor);update();};
 $('cfbtFirePoint').onchange=()=>chooseFire(data.fires.find(f=>f.id===$('cfbtFirePoint').value));
 $('cfbtFireFocus').onclick=()=>{focusFire();update();};
 $('cfbtBefore').onclick=()=>chooseFire(selectedFire,{time:selectedFire.time_s-30});
 $('cfbtAfter').onclick=()=>chooseFire(selectedFire,{time:selectedFire.time_s+60});
 $('cfbtReplay').onclick=()=>chooseFire(selectedFire,{time:selectedFire.time_s-30,replay:true});
 $('cfbtFocus').onclick=()=>{if(!selected)return;fireFocused=false;viewer.setFloor(selected.cad_floor);const target=new T.Vector3(...selected.cad_center_m,selected.z_m+2),delta=C.position.clone().sub(O.target).normalize();O.target.copy(target);C.position.copy(target).addScaledVector(delta,26);O.update();update();};
 function settings(){const options={fire_floor:$('cfbtFireFloor').value,fire_room:$('cfbtFireRoom').value,duration_s:+$('cfbtDuration').value,
  gas_model:$('cfbtGasModel').value,iteration_mode:$('cfbtIterationMode').value,
  full_floor_search:$('cfbtFullFloor').checked,solid_ignition_C:+$('cfbtSolidT').value,pilot_assumed:$('cfbtPilot').checked,
  window_breakage:{...(data?.settings.window_breakage||{}),enabled:$('cfbtWindowEnabled').checked,criterion:$('cfbtWindowCriterion').value,threshold:+$('cfbtWindowThreshold').value,post_fraction:+$('cfbtWindowPost').value/100},
  flashover:{enabled:$('cfbtFOEnabled').checked,temperature_C:+$('cfbtFOT').value},
  risk:{fgi_fuel_mass_percent:+$('cfbtFGIFuel').value,fgi_oxygen_vol_percent:+$('cfbtFGIO2').value},
  gas:{gas_ignition_C:+$('cfbtGasT').value,vent_ignition_C:+$('cfbtGasT').value,hot_C:+$('cfbtHotT').value,oxygen_min_vol_percent:+$('cfbtO2').value,rate_ref_s_inv:+$('cfbtRate').value}};
  if($('cfbtFireBase').value!=='')options.fuel_source_base_m=+$('cfbtFireBase').value;
  if(options.iteration_mode==='native_room_rule'){
   options.iteration_mode='fixed_point';
   options.room_fire_rule={enabled:true,preset:$('cfbtRoomPreset').value,trigger_mode:'fuel_r3'};
   if($('cfbtRoomFlux').value!=='')options.room_fire_rule.threshold_multiplier=+$('cfbtRoomFlux').value;
   if($('cfbtRoomRamp').value!=='')options.room_fire_rule.ramp_s=+$('cfbtRoomRamp').value;
  }
  if(['floor','vertical'].includes($('cfbtScope').value))options.scope_floor=options.fire_floor;
  if($('cfbtScope').value==='vertical')options.vertical_smoke=true;
  if(!$('cfbtFullFloor').checked)options.max_added_ignitions=+$('cfbtLimit').value;
  if($('cfbtDoors').value==='retain'&&data)options.opening_overrides=Object.fromEntries(data.openings.filter(v=>v.type!=='FLOOR').map(v=>[v.id,v.schedule[0][1]]));
  if($('cfbtDoors').value==='viewer'){options.opening_overrides={};const setOpening=(floor,id,fraction)=>{const match=data?.openings.find(v=>v.cad_floor===floor&&v.cad_opening===id);if(match)options.opening_overrides[match.id]=fraction;};for(const leaf of leaves)setOpening(leaf.floor,leaf.id,leaf.pct/100);for(const mesh of glassM)if(mesh.userData.win)setOpening(mesh.userData.win.floor,mesh.userData.win.id,mesh.userData.win.pct/100);}
  return options;
 }
 import('./frozen_rule_controls.js').then(module=>module.attachFrozenRules(panel,settings)).catch(error=>{console.warn('r8 설정 패널을 불러오지 못했습니다',error);});
 import('./lite_doors.js').then(module=>module.attachLiteDoors(panel,viewer)).catch(error=>{console.warn('간략 문 분류 패널',error);});
 import('./screening.js').then(module=>module.attachScreening(panel,viewer)).catch(error=>{console.warn('화점 후보 순위 패널',error);});
 $('cfbtFullFloor').onchange=()=>{$('cfbtLimit').disabled=$('cfbtFullFloor').checked;};
 for(const id of ['gl','layer_opening'])$(id)?.addEventListener('change',()=>update());
 async function status(){try{const state=await (await fetch('/cfbt/status')).json();busy=state.busy;$('cfbtRun').disabled=busy;$('cfbtIgnite').disabled=busy||!data||data.spread_model==='room_flashover_rule_v1';
  if(state.external_watch&&busy){activeRequest=state.request_id;if(!poll)poll=setInterval(status,2500);}
  $('cfbtBusy').textContent=busy?`계산 중 · 실행 ${state.attempt||1} · ${state.native_time_s==null?'구획 입력 준비':Math.floor(state.native_time_s)+'초까지 진행'} · 경과 ${Math.floor(state.elapsed_s)}초 · 화면은 마지막 완료 결과`:'';
  if(!busy){clearInterval(poll);poll=null;if(state.error)$('cfbtError').textContent='새 계산 실패: '+state.error;if(activeRequest&&activeRequest===state.request_id&&!state.error){activeRequest=null;if(state.kind==='ignition')await loadComparison('/cfbt/comparison.json');else if(state.available)await load();}}
 }catch(error){$('cfbtError').textContent='계산 상태 확인 실패: '+error.message;}}
 $('cfbtRun').onclick=async()=>{try{$('cfbtError').textContent='';const options=settings();const response=await fetch('/cfbt/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(options)});const answer=await response.json();if(!response.ok)throw Error(answer.error);activeRequest=answer.request_id;busy=true;$('cfbtRun').disabled=true;await status();if(!poll)poll=setInterval(status,2500);}catch(error){$('cfbtError').textContent=error.message;}};
 let loadVersion=0;
 async function load(url='/cfbt/playback.json'){const version=++loadVersion,response=await fetch(url);if(version!==loadVersion)return;if(!response.ok){$('cfbtDetail').textContent='완료된 계산이 없습니다. 조건을 정한 뒤 계산을 실행하세요.';return;}const payload=await response.json();if(version!==loadVersion)return;comparison=null;$('cfbtCompareView').disabled=true;currentCase=url==='/cfbt/playback.json'?'latest':decodeURIComponent(url.split('/').at(-1));install(payload);$('cfbtCases').value=currentCase;saveView(true);}
 function updateComparison(){
  if(!comparison){$('cfbtComparison').textContent='점화원 30초 유지 가정 · 기존 연료·산소만 사용 · FGI 위험 표시는 사용자 농도 기준이며 확률 아님';return;}
  const a=comparison.baseline.solvers[selected.solver_id],b=comparison.ignited.solvers[selected.solver_id];if(!a||!b)return;
  const cells=[['상층 온도',sample(a.Tu),sample(b.Tu),'℃'],['산소',sample(a.Ou)*100,sample(b.Ou)*100,'%'],['연기 OD',sample(a.ODu),sample(b.ODu),'1/m']];
  const text=cells.map(([label,x,y,unit])=>`${label} ${x.toFixed(2)}→${y.toFixed(2)} ${unit} (차이 ${(y-x).toFixed(2)} ${label==='산소'?'%p':unit})`).join(' · ');
  const base=comparison.solid_ignitions.baseline,changed=comparison.solid_ignitions.ignited;
  const shifts=[...new Set([...Object.keys(base),...Object.keys(changed)])].map(k=>`${k.replace('Fuel_CAD_','').replaceAll('_',' ')} ${base[k]==null?'미착화':stamp(base[k])}→${changed[k]==null?'미착화':stamp(changed[k])}`);
  $('cfbtComparison').textContent=`기준→점화 가정 · ${text}\n인접 고체 착화: ${data.smoke_scope?.mode==='prescribed_smoke'?'시각 지정 · 이번 비교에서 재예측하지 않음':shifts.join(' / ')||'양쪽 모두 없음'} · 추가 반응 ${comparison.reaction_observed?'관측':'차이 없음'} · 점선: 다른 계산의 온도 · ${data.smoke_scope?.mode==='prescribed_smoke'?'전층 연기 비교·고체 사건 지정':comparison.ignited.spread_search_complete?'전이 탐색 완료':'전이 탐색 상한/미완료'}\n가정: 점화원 ${comparison.assumption.duration_s}초, 반응률 ${comparison.assumption.rate_s_inv}/s, 최소 O₂ ${comparison.assumption.oxygen_min_vol_percent??10}% · 비교는 ${stamp(comparison.comparison_horizon_s??data.time_s.at(-1))}까지(점화 후 약5분) · 폭압/발생 확률 계산 아님`;
 }
 async function loadComparison(url){const r=await fetch(url),value=await r.json();if(!r.ok)throw Error(value.error);comparison=value;$('cfbtIgniteRate').value=comparison.assumption.rate_s_inv;currentCase=comparisonCase;$('cfbtCases').value=currentCase;$('cfbtCompareView').disabled=false;$('cfbtCompareView').value='ignited';showComparison(true);}
 function showComparison(reset=false){if(!comparison)return;const at=comparison.assumption.time_s,room=comparison.assumption.room,chosen=reset?room:selected?.solver_id,clock=now,camera={position:C.position.clone(),target:O.target.clone(),zoom:C.zoom};install($('cfbtCompareView').value==='baseline'?comparison.baseline:comparison.ignited);selected=data.rooms.find(r=>r.solver_id===chosen)||data.rooms.find(r=>r.solver_id===room)||selected;selectedFire=data.fires.find(f=>f.cad_key===selected.key)||null;$('cfbtRoom').value=selected.key;now=Math.min(data.time_s.at(-1),reset?at+10:clock);mode='risk';$('cfbtMode').value='risk';viewer.setFloor(selected.cad_floor);if(!reset){C.position.copy(camera.position);O.target.copy(camera.target);C.zoom=camera.zoom;C.updateProjectionMatrix();O.update();}update();}
 function gasScene(offset,replay=false){if(!comparison)return;$('cfbtCompareView').value='ignited';showComparison(false);selected=data.rooms.find(r=>r.solver_id===comparison.assumption.room)||selected;selectedFire=null;$('cfbtRoom').value=selected.key;now=Math.max(0,Math.min(data.time_s.at(-1),comparison.assumption.time_s+offset));realView=true;$('cfbtSpeed').value='1';$('cfbtFocus').click();playing=replay;last=performance.now();update();}
 $('cfbtGasReplay').onclick=()=>gasScene(-3,true);$('cfbtGasBefore').onclick=()=>gasScene(-1);$('cfbtGasAfter').onclick=()=>gasScene(5);
 $('cfbtCompareView').onchange=()=>showComparison(false);
 $('cfbtDemoCompare').onclick=()=>{comparisonCase='exterior_demo';loadComparison('/cfbt/comparison-demo.json').catch(e=>$('cfbtError').textContent=e.message);};
 $('cfbtIgnite').onclick=async()=>{try{if(!data||!selected)return;comparisonCase=comparison?comparisonCase:currentCase;const response=await fetch('/cfbt/ignite',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({case:comparisonCase,room:selected.solver_id,time_s:now,rate_s_inv:+$('cfbtIgniteRate').value,duration_s:comparison?.assumption.duration_s??30})});const value=await response.json();if(!response.ok)throw Error(value.error);activeRequest=value.request_id;await status();if(!poll)poll=setInterval(status,2500);}catch(e){$('cfbtError').textContent=e.message;}};
 const saved=await (await fetch('/cfbt/cases')).json();for(const item of saved)$('cfbtCases').add(new Option(item.label,item.id));
 $('cfbtCases').onchange=()=>load($('cfbtCases').value==='latest'?'/cfbt/playback.json':'/cfbt/case/'+encodeURIComponent($('cfbtCases').value)).catch(error=>$('cfbtError').textContent=error.message);
 const resume=restoredView?.building===info.building_sha256&&[...$('cfbtCases').options].some(o=>o.value===restoredView.case)?restoredView:null;
 await load(resume&&resume.case!=='latest'?'/cfbt/case/'+encodeURIComponent(resume.case):'/cfbt/playback.json');
 if(resume&&data){selected=data.rooms.find(r=>r.key===resume.room)||selected;selectedFire=data.fires.find(f=>f.id===resume.fire&&f.cad_key===selected.key)||data.fires.find(f=>f.cad_key===selected.key)||null;$('cfbtRoom').value=selected.key;now=Number.isFinite(resume.time)?Math.max(0,Math.min(data.time_s.at(-1),resume.time)):now;viewer.setFloor(selected.cad_floor);if(resume.focused&&selectedFire)focusFire();if(['1','.4','.15'].includes(resume.smokeOpacity))$('cfbtSmokeOpacity').value=resume.smokeOpacity;}
 remembering=true;update();await status();
 function tick(ms){requestAnimationFrame(tick);if(document.hidden){last=ms;return;}if(playing&&data){now=Math.min(data.time_s.at(-1),now+Math.min(.2,(ms-last)/1000)*+$('cfbtSpeed').value);if(now>=data.time_s.at(-1))playing=false;update();}else if(data&&lastFloor!==viewer.getFloor())update();realRenderer?.animate(ms);ceilingJets?.animate(ms);smokeTransport?.animate(matchMedia('(prefers-reduced-motion: reduce)').matches?0:ms);last=ms;}
 requestAnimationFrame(tick);resize();
}
