export const routeIndexText=value=>Number.isFinite(value)&&Math.round(value)!==0?String(Math.round(value)):'—';
export function routeRiskEntries(row){
 const entries=(row.phenomena||[]).filter(p=>Number.isFinite(p.index)&&p.index>=70);
 return entries.length?entries:[row];
}
export function createRoutePanel({store,graph,onPlaceStart}){
 const container=document.createElement('details');container.id='routeSettings';container.hidden=true;container.innerHTML='<summary>경로 설정</summary><label>호스 1본(m) <input id="routeHose" type="number" min="1" step="1" value="15"></label><label>계단 계수 <input id="routeStair" type="number" min="1" step="0.1" value="1.5"></label><div><button id="routePlace" hidden>차량 지정 취소</button><button id="routeReset">차량 기본 위치</button></div><div id="routeSummary"></div><div id="routeStatus" role="status"></div><span title="실 중앙·복도 폭 중앙 우선 배치 경로. 등록 장애물은 회피, 미등록 적재물·실제 호스 처짐은 미반영. 확인된 연결만 사용하며 진입 안전을 보증하지 않습니다.">ⓘ 경로 가정</span><pre id="routeDiagnostics" hidden></pre>';
 document.getElementById('exploreContent').append(container);
 const summary=document.createElement('section');summary.id='routeRiskSummary';summary.innerHTML='<h3>경로 위험 요약 <span tabindex="0" title="실별 FO·FGI·BD를 각각 확인해 70 이상인 현상마다 한 행씩 표시합니다. 각 현상은 멤버 셀 최댓값이며, 100 이상은 현상 색, 70 이상은 회색. 이력은 시간바와 무관한 전 구간 최대. 계산하지 않은 층·실은 미평가이며 안전을 뜻하지 않습니다. 호스 번호는 해당 구간에 걸친 본 번호 범위입니다.">ⓘ</span></h3><div class="resultCard"><div id="routeRiskBasis"></div><div class="exploreScroll"><table><thead><tr><th>순서</th><th>실</th><th>누적 m</th><th>호스 번호</th><th>현상</th><th>지수</th></tr></thead><tbody id="routeRiskRows"></tbody></table></div></div>';
 const savedSummary=document.getElementById('resultSavedSummary');
 if(savedSummary)savedSummary.before(summary);else document.getElementById('resultContent').append(summary);
 const style=document.createElement('style');style.textContent='#routeRiskSummary table{table-layout:fixed;font-size:13px}#routeRiskSummary th,#routeRiskSummary td{padding:6px 2px;white-space:normal;overflow-wrap:anywhere}#routeRiskSummary th:nth-child(1){width:8%}#routeRiskSummary th:nth-child(2){width:24%}#routeRiskSummary th:nth-child(3){width:17%}#routeRiskSummary th:nth-child(4){width:17%}#routeRiskSummary th:nth-child(5){width:21%}#routeRiskSummary th:nth-child(6){width:13%}#routeRiskSummary td:nth-child(2){min-width:0}#routeRiskSummary thead{position:sticky;top:0;background:var(--bg-card)}#routeRiskBasis{font-size:11px;color:var(--text-muted);margin-bottom:6px}';summary.append(style);
 const hud=document.createElement('div');hud.id='routeHUD';hud.style.cssText='padding-top:5px;font-size:13px;color:var(--accent)';document.querySelector('.compactHUD').append(hud);
 const $=id=>container.querySelector('#'+id);const cleanup=[];const on=(id,event,fn)=>{$(id).addEventListener(event,fn);cleanup.push(()=>$(id).removeEventListener(event,fn));};
 for(const [id,key] of [['routeHose','hose_m'],['routeStair','stair_factor']])on(id,'change',()=>{try{store.dispatch('route/set',{[key]:+$(id).value});$('routeStatus').textContent='';}catch(e){$('routeStatus').textContent=e.message;$(id).value=store.get('route')[key];}});
 on('routePlace','click',()=>store.dispatch('route/set',{placing:false,message:''}));on('routeReset','click',()=>store.dispatch('route/set',{vehicle:null,vehicle_yaw:0,placing:false,message:''}));
 cleanup.push(store.subscribe('route',s=>{$('routePlace').hidden=!s.placing;$('routeStatus').textContent=s.placing?'지상 그리드의 건물 밖을 클릭하세요. Esc: 취소':s.message;}));
 const popup=document.createElement('div');popup.id='vehiclePopup';popup.hidden=true;popup.style.cssText='position:fixed;z-index:210;background:var(--bg-panel);color:var(--text);border:1px solid var(--border-strong);border-radius:6px;padding:8px;box-shadow:0 3px 12px var(--shadow)';popup.innerHTML='<strong>소방차</strong><div><button type="button" data-move>이동</button><button type="button" data-close>닫기</button></div>';document.body.append(popup);
 const hint=document.createElement('div');hint.id='vehicleMoveHint';hint.hidden=true;hint.style.cssText='position:absolute;left:12px;bottom:12px;z-index:130;padding:8px;background:color-mix(in srgb,var(--bg-panel) 90.980392%,transparent);color:var(--text);border:1px solid var(--border-strong);border-radius:5px';hint.innerHTML='<span></span> <button type="button">취소</button>';document.getElementById('v').append(hint);
 const cancel=()=>store.dispatch('route/set',{placing:false,message:''});hint.querySelector('button').onclick=cancel;
 popup.querySelector('[data-close]').onclick=()=>{popup.hidden=true;};popup.querySelector('[data-move]').onclick=()=>{popup.hidden=true;onPlaceStart?.();store.dispatch('route/set',{placing:true,vehicle_visible:true,message:''});};
 const escape=e=>{if(e.key==='Escape'){popup.hidden=true;cancel();}};document.addEventListener('keydown',escape);cleanup.push(()=>document.removeEventListener('keydown',escape));
 cleanup.push(store.subscribe('route',s=>{hint.hidden=!s.placing;hint.querySelector('span').textContent=s.message||'위치 선택 → 방향 조절 → 클릭하여 확정 · Esc 취소';}));
 return {showVehicleMenu({x,y}){popup.hidden=false;popup.style.left=Math.max(8,Math.min(x,window.innerWidth-150))+'px';popup.style.top=Math.max(8,Math.min(y,window.innerHeight-90))+'px';},update(r){hud.textContent=r.error?'경로 · '+r.error:`경로 ${r.length.toFixed(1)} m · 호스 ${r.hoses}본(+1 권장) · 계단 ${r.stairs}회`;hud.title=r.limits||r.error;$('routeSummary').textContent=(r.target?r.target.replace(/^CAD_/,'').replaceAll('_',' ')+' · ':'')+hud.textContent;
  const display=r.risk_summary,body=summary.querySelector('#routeRiskRows');body.replaceChildren();
  const t=display?.sample_s,stamp=Number.isFinite(t)?`${Math.floor(t/60).toString().padStart(2,'0')}:${Math.floor(t%60).toString().padStart(2,'0')}`:'미평가';
  summary.querySelector('#routeRiskBasis').textContent=r.error||`${stamp} · ${display?.history?'전 구간 최대':'현재 시점'}`;
  for(const row of display?.rows||[]){const entries=routeRiskEntries(row);
   const hose=row.hose_first===row.hose_last?String(row.hose_first):`${row.hose_first}–${row.hose_last}`;
   entries.forEach((item,index)=>{const tr=document.createElement('tr');tr.dataset.room=row.room||'OUTSIDE';tr.dataset.phenomenon=item.type||'';tr.dataset.color=item.color;tr.dataset.index=item.index??'';
    if(index===0)for(const value of [row.order,row.label,row.end_m.toFixed(1),hose]){const td=document.createElement('td');td.textContent=value;td.rowSpan=entries.length;td.style.verticalAlign='middle';tr.append(td);}
    for(const value of [Number.isFinite(item.index)&&item.index<70?'—':item.phenomenon,routeIndexText(item.index)]){const td=document.createElement('td');td.textContent=value;td.style.color=item.index===null?'var(--text-muted)':item.color;tr.append(td);}
    tr.title=item.index===null?'저장된 평가 없음':`${row.label} · ${item.source_cell} · ${item.type} ${item.index.toFixed(2)}${item.partial?' · 일부 지수 미평가':''}`;body.append(tr);
   });
  }
  $('routeDiagnostics').textContent=JSON.stringify({main:graph.mainEntrance?.id,main_point:graph.mainEntrance?.point,default_vehicle:graph.defaultVehicle,...r});},dispose(){cleanup.forEach(f=>f());popup.remove();hint.remove();hud.remove();container.remove();summary.remove();}};
}
