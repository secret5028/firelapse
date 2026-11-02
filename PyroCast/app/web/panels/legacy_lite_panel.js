export function createLitePanel(){
 const style=document.createElement('link');style.rel='stylesheet';if(!window.__PYROCAST_OFFLINE__){style.href='/cfbt/overlay.css';document.head.append(style);}
 const panel=document.createElement('section');panel.id='cfbtPanel';panel.setAttribute('aria-label','간략 엔진 v8');
 panel.innerHTML=`<div class="row"><strong>PyroCast · 간략 엔진 v8</strong><output id="liteClock"></output><span id="liteVisible"></span><span class="grow"></span><button id="liteBuilding">건물 전체 맞춤</button><label><input id="liteCores" type="checkbox" checked>수직 공간 투시</label><button id="liteReal" aria-pressed="true">실감 보기</button><button id="liteFireFocus">연소점 확대</button><button id="litePlay">재생</button><button id="liteFold">접기</button><button id="liteReview">전체 메뉴 검토</button></div>
 <div class="row"><label><input id="liteExterior" type="checkbox" checked><span style="color:#62dcb0">외부 창 강조</span></label><small>보는 쪽 외부 창만 · 뒤편 투시 없음 · 큰 창·난간 제외 · 표시 전용</small></div>
 <div class="row"><label><input id="liteDoors" type="checkbox" checked><span style="color:#e6bd68">실내 문 위치</span></label><small>도면 문틀 · 연기 속 위치 표시 · 개폐 상태와 별도</small></div>
 <div id="liteCoreLegend" hidden><span style="color:#ffc342">■ 계단실·계단</span> · <span style="color:#55baff">■ 승강로</span> — 도면 수직 공간을 벽·슬래브 너머로 표시 (연기 전파 계산 아님)</div>
 <div id="liteBody"><div class="row"><select id="liteSpeed" aria-label="재생 배속"><option>1</option><option>5</option><option>10</option><option selected>20</option><option>30</option><option>60</option></select>배 <label><input id="liteSmoke" type="checkbox" checked>전체 연기층</label><label><input id="liteFuel" type="checkbox" checked>균등 연료 기호</label><span class="grow"></span><select id="liteCase" aria-label="간략 계산 사례"></select><button id="liteRefresh">MC 결과 새로고침</button></div>
 <div class="row"><label><input id="litePlumes" type="checkbox" checked>상승 플룸·천장 고온 가스</label><label><input id="liteHeatSmoke" type="checkbox" checked>연기 온도색</label></div><div>연기 밝은 무늬: 회색(낮은 온도) → 노랑(200℃) → 빨강(600℃ 이상). 층 평균 온도의 표시용 색상이며 실제 연기색·착화 기준이 아닙니다.</div>
 <input id="liteTime" type="range" aria-label="간략 시뮬레이션 시간" min="0" step="10" style="width:100%">
 <div id="liteRiskStatus" role="status"></div><div>위험 테두리: 방 안의 일부 셀이라도 해당하면 원래 방 외곽 전체에 표시 · 여러 유형은 높이를 조금 띄워 함께 표시</div><div id="liteLegend"><span style="color:#ef4444">■ FO</span> · <span style="color:#a855f7">■ FGI</span> · <span style="color:#f97316">━ 롤오버</span> · <span style="color:#facc15">■ 백드래프트</span> · 회색: 주의 · 점선: 전이 온도 기준 ±30℃</div>
 <div>조건 충족 단계이며 발생 예측 아님. 문 분출 연소와 상층 연소는 별도입니다.</div>
 <div>화염 단계(표시용): <span style="color:#ff7a14">초기</span> → <span style="color:#ffa824">성장기</span> → <span style="color:#fff08c">최성기</span> → <span style="color:#ff3b09">쇠퇴기</span>. 각 화원 실제 발열량의 최고값 대비 크기·최고 시점 기준이며 실제 불꽃 온도·FO 판정이 아닙니다. 불꽃 범위는 발열량과 실·셀 면적에 따라 화원 주변에서 확대·축소됩니다. 최대 범위는 면적 65% 상당 원을 실 경계로 자른 표시용 가정이며, 불꽃 수는 계산 화원 수가 아닙니다.</div>
 <div class="row"><label>실·셀 <select id="liteRoom" aria-label="간략 실 선택"></select></label><button id="liteFocus">선택 실 확대</button><button id="liteWhole">층 전체</button><label>연기 불투명도 <select id="liteOpacity" aria-label="간략 연기 불투명도"><option value="1" selected>100% · 기본</option><option value=".4">40% · 내부 관찰</option><option value=".15">15%</option></select></label></div>
 <div id="liteDetail" aria-live="polite"></div><div id="liteScores"></div><div id="liteStatus"></div><div id="liteMC"></div>
 <details id="liteMCSummary" hidden><summary>MC 10표본 결과 · 발생확률 아님</summary><div id="liteMCTable"></div></details>
 <details><summary>가정과 한계</summary><div id="liteLimits"></div><div>연기 무늬·온도색·불투명도는 표시용입니다. 플룸·천장 가스는 간략 엔진 발열량과 층 상태에 CFAST 계열 상관식을 적용한 보조 표시이며 순정 CFAST 출력이나 CFD 속도장이 아닙니다. 광학밀도·폭압은 미평가입니다. 반응 조건을 만족해도 실제 현상 발생을 뜻하지 않습니다.</div></details>
 <span id="cfMeaning" hidden></span></div>`;
 document.body.append(panel);const $=id=>document.getElementById(id);
 const selectionLabel=document.createElement('div');selectionLabel.className='cfbtSceneCaption';selectionLabel.style.borderColor='#42e8ff';selectionLabel.style.color='#9af3ff';$('v').append(selectionLabel);

 return {panel,$,selectionLabel,style};
}
export function updateLitePanel({data,index,selected,clicked,playing,floor,$,selectionLabel,riskStatus}){
 const time=data.time_s[index],stamp=t=>Math.floor(t/60).toString().padStart(2,'0')+':'+Math.floor(t%60).toString().padStart(2,'0'),name=r=>`${r.cad_floor} ${r.cad_room} · ${r.display_name||(r.cad_names||[]).slice(0,2).join(' / ')}`;
  selectionLabel.hidden=!(floor==='all'||selected.cad_floor===floor);
  const visibleRooms=data.rooms.filter(r=>floor==='all'||r.cad_floor===floor),visibleKeys=new Set(visibleRooms.map(r=>r.key));
  const smokeCount=$('liteSmoke').checked?visibleRooms.filter(r=>{const s=data.solvers[r.solver_id];return s.ODu[index]>0&&s.height_m-s.h[index]>.01;}).length:0;
  const fireCount=data.fires.filter(f=>visibleKeys.has(f.cad_key)&&f.Q_kW[index]>0).length;
  $('liteVisible').textContent=$('liteReal').getAttribute('aria-pressed')==='true'?`연기 ${smokeCount}구역 · 화염 ${fireCount}곳`:'실감 표시 꺼짐';
  $('liteClock').textContent=`${stamp(time)} / ${stamp(data.time_s.at(-1))}`;$('liteTime').value=time;$('litePlay').textContent=playing?'일시정지':'재생';
  const s=data.solvers[selected.key],d=s.display_v8,event=data.events.find(e=>e.room===selected.key),burn=s.Qsolid_kW[index]>0;
  $('liteDetail').textContent=clicked?`${name(selected)} · ${d.phenomenon[index]} · ${burn?'연소 중':event&&time>=event.supply_start_s?'조건 충족, 산소 부족 미연소':'고체 연소 없음'} · 상층 ${s.Tu[index].toFixed(1)}℃ / 하층 ${s.Tl[index].toFixed(1)}℃ · 상/하층 O₂ ${(s.Ou[index]*100).toFixed(1)}/${(s.Ol[index]*100).toFixed(1)}% · 경계 ${s.h[index].toFixed(2)}m · 고체 ${s.Qsolid_kW[index].toFixed(1)}kW / 문 분출 ${s.Qvent_kW[index].toFixed(1)}kW / 상층 ${s.Qbulk_kW[index].toFixed(1)}kW`:'실을 클릭하거나 선택하면 계산값·현상 지수·판정 근거를 표시합니다.';
  $('liteScores').replaceChildren();if(clicked){for(const [key,title] of [['FO','FO'],['FGI','FGI'],['backdraft','백드래프트'],['rollover','롤오버']]){const q=s.conditions[key].scores,degree=q.degree[index],p=document.createElement('div');p.textContent=`${title} 지수 ${degree==null?'미평가':(degree*100).toFixed(0)} (100=조건 기준, 확률 아님) · 병목 ${q.weakest[index]||'미평가'} · 우세 ${q.strongest[index]||'미평가'}`;$('liteScores').append(p);}}
  $('liteStatus').textContent=`${data.label} · 3F 층 계산 · 문 분출 ON · 연기는 계산 상층 범위·온도의 표시 효과(광학밀도 미계산)`;
 $('liteWhole').textContent=floor==='all'?'건물 전체 맞춤':'층 전체';
 $('liteCoreLegend').hidden=!(floor==='all'&&$('liteCores').checked);
 $('liteRiskStatus').textContent=riskStatus;
}
export async function createMenuReview(panel,viewer){
 const cleanups=[];let disposed=false;
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
  try{const module=await import(path);const component=await module[method](disabled,method==='attachFrozenRules'?()=>{throw Error('메뉴 검토 화면에서는 계산하지 않습니다.');}:viewer);if(component?.dispose)cleanups.push(()=>component.dispose());for(const d of disabled.querySelectorAll('details'))d.open=true;}
  catch(e){const p=document.createElement('p');p.textContent='메뉴 로드 실패: '+e.message;host.append(p);}
 }
 const note=document.createElement('p');note.textContent='입력란이 회색인 것은 검토용이기 때문입니다. 유지·삭제할 항목을 지정하면 실제 메뉴에 반영합니다. 기존 작전 표시는 계산된 화재·연기와 별개의 수동 기호입니다.';sections.append(note);
 drawer.dispose=()=>{if(disposed)return;disposed=true;for(const off of cleanups.reverse())off();drawer.remove();};return drawer;
}
