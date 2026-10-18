// CFAST result playback on the existing CAD scene. No alternative viewer or solver.
void (async function installCfastPlayback(){
 const response=await fetch('cfast-demo.json',{cache:'no-store'});
 if(!response.ok)return; // Other uploaded models have no matching calculation yet.
 const data=await response.json();
 const raw=await (await fetch('building.json')).arrayBuffer();
 const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',raw)),x=>x.toString(16).padStart(2,'0')).join('');
 if(hash!==data.building_sha256)throw new Error('CFAST 결과와 현재 건물 모델이 다릅니다.');
 const fi=B.floors.findIndex(f=>f.name===data.floor), floor=B.floors[fi];
 if(!floor)throw new Error('계산 대상 층이 없습니다.');
 const $=id=>document.getElementById(id);
 const style=document.createElement('style');style.textContent=`
 #cfPanel{border:1px solid #39677e;border-radius:7px;padding:10px;margin-bottom:14px;background:#163447;color:#e8f4fc;font-size:12px}
 #cfPanel h2{margin:0 0 8px;color:#ffda87;font-size:15px}#cfPanel select{width:100%;margin:5px 0;background:#102a3a;color:white;border:1px solid #517083;padding:5px}
 #cfPanel button{margin:4px 0}#cfPanel details{margin-top:7px}#cfPanel p{line-height:1.55;margin:6px 0}#cfPanel summary{cursor:pointer}
 #cfReadout{font-size:13px;line-height:1.8;background:#0e2535;padding:7px;border-radius:5px;font-variant-numeric:tabular-nums}
 #cfTimeline{position:absolute;z-index:5;bottom:12px;left:12px;right:12px;background:#102b3fee;color:#eff7fc;border:1px solid #486779;border-radius:8px;padding:10px 12px;font-size:12px;box-shadow:0 4px 18px #0004}
 #cfTimeline .cfRow{display:flex;align-items:center;gap:10px;flex-wrap:wrap}#cfTimeline button{background:#e4bd65;color:#102839;border:0;border-radius:4px;padding:6px 11px;cursor:pointer}
 #cfTime{width:100%;accent-color:#e4bd65;margin:8px 0 3px}#cfClock{font-size:17px;min-width:104px;font-variant-numeric:tabular-nums}
 #cfLegendBar{height:7px;margin:7px 0 4px;background:linear-gradient(90deg,#5eaee0,#f3d44b,#f09031,#e14425,#9a1334);border-radius:3px}
 .cfTag{padding:5px 8px;border-radius:4px;background:#102a3aeF;color:white;font:12px sans-serif;border:1px solid #e0bd65;white-space:pre-line}
 body.cfPlayingResult .viewHint{bottom:124px}
 `;document.head.append(style);
 const panel=document.createElement('section');panel.id='cfPanel';
 panel.innerHTML=`<h2>온도·연기 시간 변화</h2><label><input id="cfEnabled" type="checkbox" checked> CFAST 예시 결과 표시</label>
 <p>3F · 공작실/설비보관실 R9<br><small>예시 조건 계산 · 현장 측정값 아님</small></p>
 <select id="cfMode" aria-label="온도 연기 표시 방식"><option value="both">온도 + 연기층</option><option value="temperature">온도만</option><option value="smoke">연기층만</option></select>
 <div id="cfLegend"><div id="cfLegendBar"></div><div style="display:flex;justify-content:space-between"><span>20</span><span>60</span><span>150</span><span>300</span><span>600°C+</span></div></div>
 <p id="cfMeaning">색: 상·하부 평균 온도<br>부피: 연기층 위치 · 경계: 바닥 위 높이</p>
 <select id="cfRoom" aria-label="계산 구획 선택"></select><div id="cfReadout"></div>
 <button id="cfFocus">3층 화점으로 보기</button><p id="cfScope"></p>
 <details><summary>계산 조건·표현 범위</summary><div id="cfAssumptions"></div><p>재생 중 문·창 모습은 계산 조건으로 표시합니다. 결과 표시를 끄면 원래 상태로 돌아갑니다.</p><p>회색 농도는 광학밀도에 따른 표시용 강도이며 실제 가시거리나 안전 판정이 아닙니다.</p></details>`;
 $('p').prepend(panel);
 for(const item of data.assumptions){const p=document.createElement('p');p.textContent=item;$('cfAssumptions').append(p)}
 const timeline=document.createElement('div');timeline.id='cfTimeline';timeline.innerHTML=`<div class="cfRow"><button id="cfPlay">▶ 재생</button><button id="cfReset">처음</button><strong id="cfClock"></strong><span>발화 후 / 10:00</span><select id="cfSpeed" aria-label="재생 속도"><option value="5">5배속</option><option value="20" selected>20배속</option><option value="60">60배속</option></select><span id="cfHrr"></span></div><input id="cfTime" type="range" min="0" max="600" step="1" value="300" aria-label="발화 후 경과 시간"><div>3층 예시 · 문 100% / 창 닫힘 · 5분에 1 MW · 소화설비 미작동</div>`;
 el.append(timeline);
 const root=new THREE.Group();root.name='cfast_result_overlay';groups[fi].add(root);
 const roomMap=new Map(floor.rooms.map(r=>[r.id,r]));
 const meshes=new Map();
 const material=()=>new THREE.MeshBasicMaterial({transparent:true,opacity:0,depthWrite:false,depthTest:true,side:THREE.DoubleSide});
 for(const r of data.rooms){
  const room=roomMap.get(r.id);if(!room)continue;
  const polys=room.render_polys?.length?room.render_polys:room.polys;
  const low=ext(polys,0,1,material()),upper=ext(polys,0,1,material());
  const plane=new THREE.Mesh(new THREE.ShapeGeometry(polys.map(shp)),material());
  for(const mesh of [low,upper,plane]){mesh.raycast=()=>{};root.add(mesh)}
  meshes.set(r.id,{low,upper,plane});
  const option=document.createElement('option');option.value=r.id;option.textContent=`${r.id} · ${r.name}`;$('cfRoom').append(option);
 }
 $('cfRoom').value=data.fire_room;
 const markerDiv=document.createElement('div');markerDiv.className='cfTag';
 const marker=new CSS2DObject(markerDiv);root.add(marker);
 // Temporarily show this precomputed scenario's openings; preserve editor state.
 let doorBackup=[],windowBackup=[],frozenControls=[];
 const ventIds=new Set(data.vents.map(v=>v.id));
 function openings(on){
  if(on){
   doorBackup=leaves.filter(s=>s.floor===data.floor).map(s=>[s,s.pct]);
   windowBackup=glassM.filter(m=>m.userData.win?.floor===data.floor).map(m=>[m,m.userData.win.pct,m.material.opacity,m.material.color.clone()]);
   frozenControls=['dall','done','ddir','dsave','dload','wall','wone','wsave'].map(id=>[$(id),$(id)?.disabled]);
  }
  doorBackup.forEach(([s,pct])=>s.pct=on?(ventIds.has(s.id)?100:0):pct);
  windowBackup.forEach(([m,pct,opacity,color])=>{m.userData.win.pct=on?0:pct;m.material.opacity=on?.35:opacity;m.material.color.copy(on?new THREE.Color(0x7fc8ff):color)});
  frozenControls.forEach(([control,disabled])=>{if(control)control.disabled=on||disabled});
 }
 let time=300,playing=false,last=0,lastDraw=0,enabled=true;
 const colors=[[20,0x5eaee0],[60,0xf3d44b],[150,0xf09031],[300,0xe14425],[600,0x9a1334]];
 function color(temp){let i=1;while(i<colors.length-1&&temp>colors[i][0])i++;const a=colors[i-1],b=colors[i];return new THREE.Color(a[1]).lerp(new THREE.Color(b[1]),THREE.MathUtils.clamp((temp-a[0])/(b[0]-a[0]),0,1))}
 function sample(r){const i=Math.min(r.series.length-2,Math.floor(time/data.step)),a=r.series[i],b=r.series[i+1],u=(time-a[0])/(b[0]-a[0]);return a.map((v,k)=>v+(b[k]-v)*u)}
 function draw(){
  const mode=$('cfMode').value;root.visible=enabled;timeline.hidden=!enabled;
  marker.visible=enabled&&groups[fi].visible;
  markerDiv.style.visibility=marker.visible?'visible':'hidden';
  document.body.classList.toggle('cfPlayingResult',enabled);
  const selected=$('cfRoom').value;
  for(const r of data.rooms){
   const m=meshes.get(r.id);if(!m)continue;
   const [,upper,lower,z0,odUpper,odLower]=sample(r),z=THREE.MathUtils.clamp(z0,0,data.height);
   m.low.scale.z=Math.max(.001,z);m.low.position.z=.025;
   m.upper.scale.z=Math.max(.001,data.height-z);m.upper.position.z=z;
   m.plane.position.z=z+.008;
   const smoky=Math.max(odUpper,0)>.0005;
   const alpha=od=>Math.min(.68,Math.max(0,1-Math.exp(-Math.max(0,od)*2.5))*.68);
   m.low.material.color.copy(mode==='smoke'?new THREE.Color(0x394450):color(lower));
   m.upper.material.color.copy(mode==='smoke'?new THREE.Color(0x394450):color(upper));
   m.low.material.opacity=mode==='temperature'?(lower>21?.14:0):alpha(odLower)*.5;
   m.upper.material.opacity=mode==='temperature'?(upper>21?.28:0):alpha(odUpper);
   m.plane.material.color.copy(mode==='smoke'?new THREE.Color(0x71818e):color(upper));
   m.plane.material.opacity=smoky?(r.id===selected?.42:.18):0;
   if(r.id===selected){
    $('cfReadout').textContent=`상부 ${upper.toFixed(1)}°C\n하부 ${lower.toFixed(1)}°C\n연기층 하단 ${z.toFixed(2)} m\n연기층 두께 ${(data.height-z).toFixed(2)} m`;
    $('cfReadout').style.whiteSpace='pre-line';
    const room=roomMap.get(r.id);marker.position.set(room.c[0],room.c[1],Math.max(z,.3));
    markerDiv.textContent=`${r.id===data.fire_room?'🔥 화점 ':''}${r.id} · ${upper.toFixed(0)}°C\n연기층 하단 ${z.toFixed(2)}m`;
   }
  }
  $('cfClock').textContent=`${String(Math.floor(time/60)).padStart(2,'0')}:${String(Math.floor(time%60)).padStart(2,'0')}`;
  $('cfTime').value=time;$('cfPlay').textContent=playing?'❚❚ 일시정지':'▶ 재생';
  $('cfHrr').textContent=`계산 HRR ${Math.round(data.hrr[Math.min(data.hrr.length-1,Math.round(time/data.step))])} kW`;
  $('cfLegend').hidden=mode==='smoke';
  $('cfScope').textContent=selFloor==='all'?'3층에만 계산 결과 표시 · 다른 층은 미계산':selFloor!==data.floor?'현재 층은 계산 범위 밖입니다. 아래 결과는 3층 구획 값입니다.':'3층 30개 실내 구획 · 층간 확산 미포함';
  $('cfMeaning').textContent=mode==='smoke'?'회색: 연기 농도에 따른 표시 · 경계: 바닥 위 연기층 높이':'색: 상·하부 평균 온도 · 부피: 층 위치 · 온도색은 위험등급이 아닙니다.';
  document.body.dataset.cfastState=JSON.stringify({floor:data.floor,time,playing,mode,enabled,selected,roomCount:meshes.size,modelHash:hash});
 }
 function focus(){const button=[...$('fbtn').children].find(x=>x.textContent===data.floor);button?.click();iso();draw()}
 $('cfFocus').onclick=focus;
 $('cfTime').oninput=e=>{time=+e.target.value;playing=false;draw()};
 $('cfPlay').onclick=()=>{if(time>=data.duration)time=0;playing=!playing;last=performance.now();draw()};
 $('cfReset').onclick=()=>{time=0;playing=false;draw()};
 $('cfMode').onchange=draw;$('cfRoom').onchange=draw;
 $('cfEnabled').onchange=e=>{enabled=e.target.checked;playing=false;openings(enabled);draw()};
 const previousApplyFloor=applyFloor;
 applyFloor=function(){previousApplyFloor();draw()};
 const oldSnapshot=window.cadViewerSnapshot;
 window.cadViewerSnapshot=()=>({...oldSnapshot(),cfast:JSON.parse(document.body.dataset.cfastState||'null')});
 function tick(now){requestAnimationFrame(tick);if(!playing||!enabled||document.hidden){last=now;return}time=Math.min(data.duration,time+Math.min((now-last)/1000,.5)*+$('cfSpeed').value);last=now;if(time>=data.duration)playing=false;if(now-lastDraw>100||!playing){draw();lastDraw=now}}
 openings(true);focus();draw();requestAnimationFrame(tick);
})().catch(error=>{console.error('CFAST playback:',error);const p=document.createElement('p');p.textContent='온도·연기 결과를 불러오지 못했습니다: '+error.message;document.getElementById('p')?.prepend(p)});
