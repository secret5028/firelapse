// Context-bound controls; thermal calculations run only through the server worker.
export function createSimulation({THREE,camera,scene,getBuilding,getGroups,getFloor,draw,onFloor}){
 const $=id=>document.getElementById(id),panel=document.createElement('section');panel.id='simulation';
 panel.innerHTML=`<h3>간략 시뮬레이션</h3><label>계산 층 <select id="simFloor"></select></label><label>화점 <select id="simRoom"></select></label><label>계산 시간 <select id="simDuration"><option value="60">1분 · 연결 확인</option><option value="1800">30분</option><option value="3600" selected>60분</option></select></label><label>개구부 확정 상태 <select id="simState"><option value="open_except_confirmed">확정 방화문 제외 열림</option><option value="closed">전부 닫힘 · 누설만</option></select></label><p id="simNote"></p><p id="simStatus" role="status"></p><button id="simResult" hidden>완료 결과 보기</button><details><summary>이 건물의 계산 결과</summary><div id="simJobs"></div></details>`;
 $('reason').after(panel);
 const playbackBar=document.createElement('div');playbackBar.id='playbackBar';playbackBar.hidden=true;
 playbackBar.innerHTML=`<button id="simPlay">재생</button> <input id="simTime" aria-label="재생 시간" type="range" min="0" value="0" step="0.1"><output id="simClock">0:00</output><label><input id="simSmoke" type="checkbox" checked>연기</label><label><input id="simFlame" type="checkbox" checked>화염</label><div id="simReadout"></div><div id="cfMeaning"></div>`;
 $('stage').append(playbackBar);
 let entry=null,token=0,cap=null,poll=null,pb=null,real=null,realGroup=null,playing=false,last=0,frame=null,job=null;
 const api=async(path,options)=>{const r=await fetch(path,options);const d=await r.json();if(!r.ok)throw Error(d.error||`HTTP ${r.status}`);return d};
 function disposeView(){cancelAnimationFrame(frame);frame=null;playing=false;pb=null;playbackBar.hidden=true;real?.detach();real=null;
  if(realGroup){const owned=new Set();realGroup.traverse(o=>{if(o.geometry)owned.add(o.geometry);for(const m of (Array.isArray(o.material)?o.material:[o.material]))if(m){owned.add(m);for(const v of Object.values(m.uniforms||{}))if(v.value?.isTexture)owned.add(v.value)}});for(const r of owned)r.dispose();realGroup.removeFromParent();realGroup=null;}draw();}
 function rooms(){const f=cap?.floors.find(f=>f.floor===$('simFloor').value);$('simRoom').replaceChildren(...(f?.rooms||[]).map(r=>new Option(r.label,r.id)));$('run').disabled=!f?.enabled;
  $('simNote').textContent=f?.enabled?'단일 층 · 자동 용도·연료표 · 직렬 계산 · 최대 1,200초':f?.error||'입력 확인 중';}
 $('simFloor').onchange=rooms;
 function stateText(s){if(s.state==='complete'){const v=s.summary;return `완료 · ${s.wall_s.toFixed(1)}초 · 연소 ${v.burning_room_count}실 · 주의 이상 ${v.attention_room_count??'미평가'}실`;}return s.state==='failed'?`실패 · ${s.error}`:s.state==='queued'?'계산 대기':'계산 중 · 다른 모델을 봐도 계산은 계속됩니다';}
 async function jobs(mine){const d=await api(`/models/simulation/jobs?building=${encodeURIComponent(entry.id)}`);if(mine!==token)return;
  $('simJobs').replaceChildren();for(const item of d.jobs){const b=document.createElement('button');b.textContent=`${item.request.floor} ${item.request.room.replace(/^CAD_[^_]+_/,'')} · ${item.request.duration_s/60}분 · ${item.state}`;b.disabled=item.state!=='complete';b.onclick=()=>loadResult(item.job);$('simJobs').append(b);}if(!d.jobs.length)$('simJobs').textContent='저장 결과 없음';
  const active=d.jobs.find(j=>['queued','running'].includes(j.state));if(active){job=active.job;watch(mine);}}
 async function watch(mine){clearTimeout(poll);try{const s=await api(`/models/simulation/status?building=${encodeURIComponent(entry.id)}&job=${job}`);if(mine!==token)return;
  $('simStatus').textContent=stateText(s);const busy=['queued','running'].includes(s.state);$('run').disabled=busy||!cap?.floors.find(f=>f.floor===$('simFloor').value)?.enabled;
  $('simResult').hidden=s.state!=='complete';$('simResult').onclick=()=>loadResult(job);
  if(busy)poll=setTimeout(()=>watch(mine),1000);else await jobs(mine);
 }catch(e){if(mine===token){$('simStatus').textContent=e.message;rooms();}}}
 async function run(){const mine=token;$('run').disabled=true;$('simStatus').textContent='입력 준비 중…';$('simResult').hidden=true;
  try{const d=await api('/models/simulation/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({building:entry.id,floor:$('simFloor').value,room:$('simRoom').value,duration_s:Number($('simDuration').value),opening_state:$('simState').value})});if(mine!==token)return;job=d.job;await watch(mine);}catch(e){if(mine===token){$('simStatus').textContent=e.message;rooms();}}}
 const sample=(a,t)=>{if(!a?.length)return 0;let i=0;while(i<pb.time_s.length-1&&pb.time_s[i+1]<=t)i++;const j=Math.min(i+1,a.length-1),dt=pb.time_s[j]-pb.time_s[i];return dt>0?a[i]+(a[j]-a[i])*(t-pb.time_s[i])/dt:a[i]};
 function update(){if(!pb||!real)return;const t=Number($('simTime').value),floor=getFloor();
  real.update({enabled:true,time:t,sample:a=>sample(a,t),floor,smokeEnabled:$('simSmoke').checked,smokeOpacity:.7,customRiskBoundaries:true,legacySmokeTexture:true,flameDisplay:'hrr',plumesEnabled:false,temperatureSmoke:true,noiseAmp:.4});
  // Existing renderer owns flame objects; hide only their display when toggled.
  if(!$('simFlame').checked)realGroup.traverse(o=>{if(o.material?.uniforms?.uFire?.value>0)o.visible=false;});
  $('simClock').textContent=`${Math.floor(t/60)}:${String(Math.floor(t%60)).padStart(2,'0')}`;
  const src=pb.rooms.find(r=>r.key===pb.fire_key);const s=src&&pb.solvers[src.solver_id];$('simReadout').textContent=s?`${src.cad_floor} ${src.cad_room} · 상층 ${sample(s.Tu,t).toFixed(0)} ℃ · O₂ ${(sample(s.Ou,t)*100).toFixed(1)} %`:'';draw();}
 async function loadResult(id){const mine=token;try{const data=await api(`/models/simulation/playback?building=${encodeURIComponent(entry.id)}&job=${id}`);if(mine!==token)return;
  const {createRealView}=await import('/cfbt/legacy_real_bridge.js');if(mine!==token)return;disposeView();pb=data;realGroup=new THREE.Group();scene.add(realGroup);
  real=createRealView({THREE,C:camera,B:getBuilding(),groups:getGroups()},data,realGroup);$('simTime').max=data.time_s.at(-1);$('simTime').value=0;playbackBar.hidden=false;$('simPlay').textContent='재생';
  const origin=data.rooms.find(r=>r.key===data.fire_key);if(origin)onFloor(origin.cad_floor);update();last=0;frame=requestAnimationFrame(animate);
 }catch(e){if(mine===token)$('simStatus').textContent=e.message;}}
 function animate(ms){if(!real)return;if(playing&&last){const t=Math.min(Number($('simTime').max),Number($('simTime').value)+(ms-last)/1000*20);$('simTime').value=t;update();if(t>=Number($('simTime').max)){playing=false;$('simPlay').textContent='재생';}}
  last=ms;real.animate(ms);realGroup.traverse(o=>{if(o.isPointLight)o.visible=$('simFlame').checked;});draw();frame=requestAnimationFrame(animate);}
 $('simPlay').onclick=()=>{playing=!playing;$('simPlay').textContent=playing?'일시정지':'재생'};$('simTime').oninput=update;$('simSmoke').onchange=update;$('simFlame').onchange=update;
 return {update,async bind(e){const mine=++token;entry=e;cap=null;job=null;clearTimeout(poll);disposeView();panel.hidden=e.execution_mode!=='library_lite';$('simStatus').textContent='';$('simResult').hidden=true;
  if(panel.hidden)return;$('run').disabled=true;$('run').onclick=run;$('simNote').textContent='층별 입력 확인 중…';$('simFloor').replaceChildren();$('simRoom').replaceChildren();
  try{const c=await api(`/models/simulation/capabilities?building=${encodeURIComponent(e.id)}`);if(mine!==token)return;cap=c;
   for(const f of c.floors){const o=new Option(f.floor+(f.enabled?'':' · 계산 불가'),f.floor);o.disabled=!f.enabled;$('simFloor').add(o);}
   $('simFloor').value=c.floors.find(f=>f.enabled)?.floor||'';rooms();await jobs(mine);
  }catch(error){if(mine===token)$('simNote').textContent=error.message;}
 }};
}
