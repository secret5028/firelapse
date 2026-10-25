// Candidate ranking only. Selection never starts Monte Carlo or replaces playback.
export async function attachScreening(panel,viewer){
 const host=document.createElement('details');host.id='liteScreening';
 const title=document.createElement('summary');title.textContent='화점 후보 · ① 입력 점수 / ② 간략 시뮬레이션';host.append(title);
 const note=document.createElement('p');note.textContent='v8 승인 용도표 · 화점은 연료 기준 공급량(입력 peak 미사용). ①은 연료 log·공급/환기·연결도 등 후보 선별용 상대 점수입니다. ②는 개방·폐쇄 2상태 중 나쁜 결과로 비교: 연소 실 수 → 연기 위험 실 수 → 연기 주의 실 수 → 최초 FO가 빠른 순 → 화점 최고 상층 온도. 같은 값은 공동 순위입니다.';host.append(note);
 const controls=document.createElement('div'),n=document.createElement('input');n.type='number';n.min=1;n.value=3;n.style.width='65px';n.setAttribute('aria-label','상위 후보 수 N');
 controls.append('상위 N ',n);
 const save=document.createElement('button');save.textContent='후보 선택 저장';controls.append(save);
 const run=document.createElement('button');run.textContent='N실 × 2상태 순차 계산 · 각 1시간';controls.append(run);
 const refresh=document.createElement('button');refresh.textContent='결과 새로고침';controls.append(refresh);
 const toggle=document.createElement('input');toggle.type='checkbox';const label=document.createElement('label');label.append(toggle,' 3D 상위 N 표시 (금색→청색)');controls.append(label);host.append(controls);
 const status=document.createElement('p');status.setAttribute('role','status');host.append(status);
 const table=document.createElement('table');table.style.width='100%';table.style.minWidth='680px';
 const tableScroll=document.createElement('div');tableScroll.style.overflow='auto';tableScroll.style.maxHeight='320px';tableScroll.append(table);host.append(tableScroll);
 const choice=document.createElement('select');choice.setAttribute('aria-label','다음 MC 화점 후보');const next=document.createElement('p');next.append('다음 MC 화점 후보 ',choice,' · 선택만 저장하며 MC는 실행하지 않습니다.');host.append(next);
 const limitation=document.createElement('p');limitation.textContent='3F 승인 용도표·v7 문 재분류. 화장실40 MJ/m²·250 kW/m²는 사용자 가정이며 화점 후보에서 제외. 개구부 없는 1m² 미만 R14·R28은 후보·전이 그래프 제외. 개방 상태는 확정 방화문만 닫고 나머지는 열림, 폐쇄 상태는 문·창 닫힘입니다. 영구 통로는 항상 열림, 열린 창은 면적 50%. 두 상태가 모든 조합의 최악을 보증하지 않습니다. 기존 화재 재생은 유지됩니다.';host.append(limitation);
 (panel.querySelector('#cfbtBody')||panel).append(host);
 const {THREE:T,S}=viewer,group=new T.Group();S.add(group);let data=null;
 function clear(){for(const obj of [...group.children]){group.remove(obj);obj.geometry.dispose();obj.material.dispose();}}
 function draw(){clear();if(!data)return;const count=Number(n.value);
  for(const row of data.score.ranked.slice(0,count)){
   const color=new T.Color().setHSL(.12+.4*(row.selection_order-1)/Math.max(1,count-1),.9,.6);
   for(const poly of row.cad_polys||[]){if(!poly.o?.length)continue;
    const points=poly.o.map(p=>new T.Vector3(p[0],p[1],row.z_m+.12));
    const line=new T.LineLoop(new T.BufferGeometry().setFromPoints(points),new T.LineBasicMaterial({color,depthTest:false}));line.renderOrder=60;group.add(line);
   }
   if(row.cad_center_m){const dot=new T.Mesh(new T.SphereGeometry(.45,12,8),new T.MeshBasicMaterial({color,depthTest:false}));dot.position.set(row.cad_center_m[0],row.cad_center_m[1],row.z_m+.4);dot.renderOrder=61;group.add(dot);}
  }
 }
 function render(payload){data=payload;n.max=payload.score.eligible_count;n.value=payload.score.top_n;table.replaceChildren();
  const header=table.insertRow();for(const h of ['선택','실','① 순위 / 점수','화점 공급상한 kW','② 순위','나쁜 상태','연소 실','연기 위험 실','연기 주의 실','최초 FO','화점 최고 ℃']){const th=document.createElement('th');th.textContent=h;header.append(th);}
  const found=new Map((payload.comparison?.rows||[]).map(r=>[r.room,r]));
  for(const row of payload.score.ranked){const result=found.get(row.room),tr=table.insertRow();
   for(const value of [row.selected?'●':'',`${row.room.replace('CAD_3F_','')} · ${row.name}`,`${row.rank1} / ${row.score.toFixed(3)}`,row.origin_budget?.Q_origin_peak_kW?.toFixed(1)??'—',result?(result.complete?result.rank2:'미완료'):'미계산',result?.tied_states?.length>1?'동률':result?.worst_state==='open_except_confirmed'?'개방':result?.worst_state==='closed'?'폐쇄':'—',result?.burning_room_count??'—',result?.smoke_risk_room_count??'—',result?.smoke_caution_room_count??'—',result?.first_FO_s!=null?`${result.first_FO_s}초`:'—'])tr.insertCell().textContent=value;
   tr.title=row.reason;
  }
  choice.replaceChildren();for(const row of payload.score.ranked){const option=document.createElement('option');option.value=row.room;option.textContent=`${row.room.replace('CAD_3F_','')} · ${row.name}`;choice.append(option);}
  choice.value=payload.selection.mc_room||payload.comparison?.default_mc_room||payload.score.ranked[0]?.room;
  const p=payload.progress;status.textContent=p?.state==='running'?`순차 계산 ${p.completed}/${p.total||2*p.top_n} 완료 · 현재 ${p.current_room} / ${p.current_state||''}`:payload.comparison?`저장된 비교: N=${payload.comparison.top_n}, ${payload.comparison.complete_scenarios}/${payload.comparison.attempted_scenarios} 시나리오 완주 · 전체 ${payload.comparison.total_wall_s.toFixed(1)}초. N 변경은 저장된 결과를 재계산하지 않습니다.`:'완료된 비교가 없습니다.';
  if((payload.comparison?.rows||[]).filter(r=>r.rank2===1).length>1)status.textContent+=' 공동 1위: 유일한 최악실은 선정되지 않았습니다.';
  if(payload.saved_score&&JSON.stringify(payload.saved_score.opening_states)!==JSON.stringify(payload.score.opening_states))status.textContent+=' 현재 문 설정과 저장된 비교 조건이 다릅니다.';
  save.disabled=run.disabled=p?.state==='running';draw();
 }
 async function load(){try{const response=await fetch('/cfbt/lite/screening');if(!response.ok)throw Error('후보 API를 불러오지 못했습니다');render(await response.json());}catch(e){status.textContent=e.message;}}
 async function post(start=false){if(!n.checkValidity()){n.reportValidity();return;}status.textContent='저장 중…';try{const response=await fetch('/cfbt/lite/screening',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({top_n:Number(n.value),mc_room:choice.value,run:start})});const payload=await response.json();if(!response.ok)throw Error(payload.error);if(start){status.textContent='순차 계산 시작. 결과 새로고침으로 확인하세요.';run.disabled=true;}else render(payload);}catch(e){status.textContent=e.message;}}
 save.onclick=()=>post();run.onclick=()=>post(true);choice.onchange=()=>post();refresh.onclick=load;n.oninput=draw;
 const show=()=>{group.visible=toggle.checked&&['all','3F'].includes(viewer.getFloor());};toggle.onchange=show;show();
 const timer=setInterval(show,250);window.addEventListener('pagehide',()=>{clearInterval(timer);clear();S.remove(group);},{once:true});await load();
}


