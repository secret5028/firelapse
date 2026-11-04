import {attentionRanking} from '../adapters/attention.js';
import {savedAttention} from '../data/saved_attention.js';
const finite=Number.isFinite;
const count=v=>finite(v)?String(v):'—';
export function screeningRows(payload){
 const first=payload.score.ranked,byId=new Map(first.map(r=>[r.room,r]));
 return {first,second:attentionRanking(payload.comparison,payload.attention??savedAttention).map(r=>({...r,rank1:byId.get(r.room)?.rank1??r.rank1,name:byId.get(r.room)?.name??r.name}))};
}
export function mcEstimate(summary,samples){
 return finite(summary?.wall_s)&&summary.wall_s>0&&summary.completed>0?summary.wall_s/summary.completed*samples:null;
}
// DOM only. The controller owns existing HTTP paths; candidate selection does
// not select a scene cell or mutate the currently displayed simulation.
export function createExplorePanel({store,onRun,onRunOrigin,onRefresh,onResults,onMC,onApplyWorst,onFloor,floors=[]}){
 const $=id=>document.getElementById(id),root=document.createElement('div');root.id='exploreContent';$('shellPane-explore').append(root);
 root.innerHTML=`<div id="workflowFloor" class="exploreCard"><label>계산 층 <select id="exploreFloor" aria-label="계산 층"><option value="">층 하나를 선택하세요</option></select></label><div id="exploreChosenOrigin"></div></div><h3>① 화점 후보 순위 <span tabindex="0" title="연료량이 많고, 환기가 부족하며, 화재가 확산될 통로가 많은 실을 우선합니다.&#10;&#10;후보 점수 = 연료량 + 환기 부족 + 확산 연결 + 복도 인접 + 격리 부족&#10;각 항목 0~1점, 합계 0~5점.&#10;후보 선별용 상대 점수이며 위험도 예측값은 아닙니다.">ⓘ</span></h3>
 <div class="exploreCard"><form id="exploreRunForm" hidden><label>상위 N <input id="exploreN" type="number" min="1" step="1" value="8" required></label><button id="exploreRun" type="submit" disabled>② 실행</button><button id="exploreRefresh" type="button">새로고침</button></form><div id="exploreStatus" role="status">목록 읽는 중</div><div class="exploreScroll"><table><thead><tr><th>#</th><th>후보 실</th><th>점수</th></tr></thead><tbody id="exploreCandidates"></tbody></table></div></div>
 <h3 hidden>② 시뮬레이션 순위 <span tabindex="0" title="표시 순위: 연소 실 수 → 주의 이상 실 수 → 최초 FO가 빠른 순. 주의 이상은 3현상 중 최대 지수 ≥70인 원래 방 수입니다. 두 극단 상태 중 나쁜 쪽을 사용합니다. 행을 선택하면 다음 탐색의 화점만 바뀝니다.">ⓘ</span></h3>
 <div class="exploreCard" hidden><div id="exploreRankBasis"></div><div class="exploreScroll"><table><thead><tr><th>#</th><th>화점</th><th>①순위</th><th>연소</th><th title="3현상 최대 지수 ≥70인 실 수">주의 ≥70</th><th>최초 FO</th></tr></thead><tbody id="exploreRanking"></tbody></table></div></div>
 <h3>② MC 급기 탐색</h3><div class="exploreCard"><label hidden>화점 <select id="exploreOrigin" disabled></select></label><label>계산 시간 <select id="exploreDuration"><option value="1800">30분</option><option value="3600" selected>60분</option></select></label><label>표본 수 <input id="exploreSamples" type="number" min="2" max="1000" step="1" value="10" required></label><div id="exploreEstimate" title="저장된 MC 전체 경과시간 ÷ 완료 표본 수 × 요청 표본 수. 다른 화점과 개폐 조건의 소요시간은 달라질 수 있습니다.">예상 시간 —</div><div class="exploreButtons"><button id="exploreOriginRun" hidden disabled>선택 실 2상태 실행</button><button id="exploreMC" disabled title="MC 서버 연결 확인 중">최악 급기 탐색</button><button id="exploreResults" hidden disabled>결과 보기</button><button id="exploreApplyWorst" disabled>③ 최악 결과 적용·재생</button></div><div id="exploreMCStatus" role="status">MC 서버 연결 확인 중</div></div>
 <details id="exploreRules"><summary>규칙 설정</summary><div id="exploreRuleContext"></div><div id="exploreRuleMount"></div></details>`;
 const style=document.createElement('style');style.dataset.pyrocastExplore='true';style.textContent=`
 #exploreContent{padding:12px 16px;font-size:12px;color:#eaf3f8}#exploreContent h3{font-size:12px;font-weight:500;color:#b8cbd8;margin:14px 0 8px}#exploreContent h3 span{cursor:help}.exploreCard{border:1px solid #496273;border-radius:7px;padding:10px;margin-bottom:12px;background:#163345}#exploreContent label{display:block;margin:6px 0}#exploreContent input,#exploreContent select,#exploreContent button{background:#1d4158;color:#eef5fa;border:1px solid #577487;border-radius:4px;padding:5px;box-sizing:border-box}#exploreContent input{width:70px}#exploreOrigin{width:100%;margin-top:5px}#exploreContent button{cursor:pointer}#exploreContent :disabled{opacity:.5;cursor:default}#exploreRunForm,.exploreButtons{display:flex;gap:6px;align-items:center;flex-wrap:wrap}#exploreContent :focus-visible{outline:2px solid #42e8ff}.exploreScroll{overflow:auto;max-height:270px}#exploreContent table{border-collapse:collapse;width:100%;font-size:11px}#exploreContent th,#exploreContent td{text-align:right;padding:7px 3px;border-bottom:1px solid #304c5e;white-space:nowrap}#exploreContent th:nth-child(2),#exploreContent td:nth-child(2){text-align:left}#exploreContent td:nth-child(2){white-space:normal;min-width:68px}#exploreContent tr[data-room]{cursor:pointer}#exploreContent tr[aria-selected=true]{background:#245166;box-shadow:inset 2px 0 #42e8ff}#exploreStatus,#exploreRankBasis,#exploreEstimate,#exploreMCStatus,#exploreRuleContext{font-size:11px;color:#b8cbd8;margin:8px 0;overflow-wrap:anywhere}#exploreContent details{margin-top:12px}#exploreContent summary{cursor:pointer;color:#b8cbd8}#exploreRules input{max-width:100%}#exploreRules table{display:block;overflow:auto}#exploreRules #r8SettingsGrid{grid-template-columns:1fr!important}#exploreRules #cfbtFrozenRules>summary{display:none}
 `;document.head.append(style);
 const scope=$('workflowFloor');scope.style.margin='12px 16px';$('shellPane-building').prepend(scope);
 for(const f of floors)$('exploreFloor').add(new Option(f.name,f.name));
 $('exploreFloor').onchange=()=>onFloor?.($('exploreFloor').value);
 $('exploreDuration').onchange=()=>store.dispatch('exploration/set',{duration_s:Number($('exploreDuration').value)});
 $('exploreApplyWorst').onclick=onApplyWorst;
 let payload=null,summary=null,mcOrigin=null,pending=false,mcJob={available:false},mcPending=false,lastSamples=null;
 const pretty=id=>id?.replace(/^CAD_/,'').replaceAll('_',' ')||'미선택';
 const useName=row=>row?.origin_budget?.classification?.label??payload?.score.approved_input?.room_uses?.[row?.room]?.label??'용도 미확인';
 const originName=id=>{const row=payload?.score.ranked.find(r=>r.room===id),manual=payload?.manual_origins?.find(r=>r.room===id);return row?`${pretty(id)} · ${useName(row)}`:manual?`${pretty(id)} · ${manual.label}`:pretty(id);};
 const cell=(tr,value)=>{const td=document.createElement('td');td.textContent=value;tr.append(td);return td;};
 function sync(){const state=store.get('exploration');$('exploreFloor').value=store.get('floor').floor_id||'';$('exploreDuration').value=state.duration_s;$('exploreN').value=state.top_n;if(lastSamples!==state.samples){$('exploreSamples').value=state.samples;lastSamples=state.samples;}$('exploreOrigin').value=state.origin_room_id||'';
  for(const tr of root.querySelectorAll('tr[data-room]'))tr.setAttribute('aria-selected',String(tr.dataset.room===state.origin_room_id));
  const estimate=mcEstimate(summary,state.samples);$('exploreEstimate').textContent=estimate===null?'예상 시간 미확인':`예상 약 ${Math.ceil(estimate/60)}분 · 이전 MC 기준`;
  $('exploreOriginRun').textContent=payload?.opening_mode==='fixed'?'선택 실 확정 급기 실행':'선택 실 2상태 실행';
  const matching=Boolean(summary&&mcOrigin&&state.origin_room_id===mcOrigin);$('exploreApplyWorst').disabled=!matching||!summary?.worst||mcJob.running||mcPending;
  $('exploreChosenOrigin').textContent=state.origin_room_id?'자동 화점 · '+originName(state.origin_room_id)+' · 후보 점수 1위':'선택 층의 화점 후보 없음';$('exploreResults').disabled=!matching;
  $('exploreResults').title=matching?'선택 화점의 저장 MC 집계 보기':`선택 화점의 저장 MC 결과 없음${mcOrigin?' · 저장 화점 '+pretty(mcOrigin):''}`;
  $('exploreMC').disabled=mcPending||!mcJob.available||mcJob.server_busy||mcJob.running||!state.origin_room_id;
  $('exploreMC').title=mcJob.available?'직렬 실행 · 표본당 적분 예산 1,200초':'MC 서버 연결 확인 중';
  $('exploreMCStatus').textContent=mcJob.error?'MC 오류 · '+mcJob.error:mcPending?'MC 요청 중':mcJob.running?`MC ${mcJob.completed??0}/${mcJob.total??state.samples} · ${mcJob.current??mcJob.state}`:mcJob.server_busy?'다른 계산 진행 중':({completed:`MC 완료${mcJob.failed_or_incomplete?' · 실패·미완료 '+mcJob.failed_or_incomplete+'건':''}`,failed:'MC 실패',interrupted:'MC 중단'}[mcJob.state]||'MC 대기')+(matching?' · 저장 결과 있음':' · 저장 결과 없음');
  $('exploreOriginRun').disabled=payload?.available===false||pending||!payload?.manual_origins?.some(r=>r.room===state.origin_room_id)||Boolean(payload?.progress?.running)||mcJob.server_busy;
  if(state.origin_room_id&&!payload?.score.ranked.some(r=>r.room===state.origin_room_id)&&!(state.origin_mode==='manual'&&payload?.manual_origins?.some(r=>r.room===state.origin_room_id))){$('exploreMC').disabled=true;$('exploreMC').title='수동 화점으로 지정한 뒤 실행하세요';}
  $('exploreRun').disabled=payload?.available===false||pending||!payload||Boolean(payload.progress?.running);$('exploreN').disabled=pending||Boolean(payload?.progress?.running);
 }
 $('exploreN').onchange=()=>{if($('exploreN').checkValidity())store.dispatch('exploration/set',{top_n:Number($('exploreN').value)});};
 $('exploreSamples').onchange=()=>{if($('exploreSamples').checkValidity())store.dispatch('exploration/set',{samples:Number($('exploreSamples').value)});};
 $('exploreOrigin').onchange=()=>store.dispatch('exploration/set',{origin_room_id:$('exploreOrigin').value,origin_mode:'manual'});
 $('exploreOriginRun').onclick=onRunOrigin;
 $('exploreRunForm').onsubmit=e=>{e.preventDefault();if(!$('exploreRunForm').reportValidity())return;store.dispatch('exploration/set',{top_n:Number($('exploreN').value)});onRun();};
 $('exploreMC').onclick=()=>{if(!$('exploreSamples').reportValidity())return;store.dispatch('exploration/set',{samples:Number($('exploreSamples').value)});onMC();};
 $('exploreRefresh').onclick=onRefresh;$('exploreResults').onclick=onResults;
 const off=store.subscribe('exploration',sync);
 function update(value){payload=value;const {first,second}=screeningRows(value);$('exploreN').max=first.length;$('exploreOrigin').replaceChildren();for(const row of value.manual_origins??first)$('exploreOrigin').add(new Option(originName(row.room),row.room));$('exploreOrigin').disabled=!first.length;
  $('exploreCandidates').replaceChildren();for(const row of first){const tr=document.createElement('tr');cell(tr,count(row.rank1));cell(tr,`${pretty(row.room)} · ${useName(row)}`).title=row.reason||'';cell(tr,finite(row.score)?row.score.toFixed(3):'—');$('exploreCandidates').append(tr);}
  $('exploreRanking').replaceChildren();for(const row of second){const tr=document.createElement('tr');tr.dataset.room=row.room;tr.tabIndex=0;tr.setAttribute('aria-label',originName(row.room)+' 화점 선택');tr.title=row.complete?({fixed:'확정 급기',closed:'모두 닫힘',open_except_confirmed:'확정 방화문 제외 모두 열림'}[row.worst_state]||''):'미완료 · 부분 결과';cell(tr,count(row.rank2));cell(tr,pretty(row.room));cell(tr,count(row.rank1));cell(tr,count(row.burning_room_count));cell(tr,count(row.attention_room_count));cell(tr,finite(row.first_FO_s)?`${Math.floor(row.first_FO_s/60)}:${String(Math.floor(row.first_FO_s%60)).padStart(2,'0')}`:'—');
   const choose=()=>{if((value.manual_origins??first).some(r=>r.room===row.room))store.dispatch('exploration/set',{origin_room_id:row.room,origin_mode:'ranked'});};tr.onclick=choose;tr.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();choose();}};$('exploreRanking').append(tr);
  }
  if(!second.length){const tr=document.createElement('tr'),td=cell(tr,'저장된 ② 결과 없음');td.colSpan=6;$('exploreRanking').append(tr);}
  const progress=value.progress;$('exploreStatus').textContent=progress?.running?`② 계산 중 ${progress.completed??0}/${progress.total??'—'} · ${progress.current_room??''}`:progress?.error?'② 실패 · '+progress.error:`적격 ${first.length}실`;
  const c=value.comparison;$('exploreRankBasis').textContent=c?`저장 결과 · ${c.manual_rooms?'수동 지정':'상위'} ${c.top_n} × ${c.opening_mode==='fixed'?'확정 급기 1회':'2상태'} · ${c.complete_scenarios??'—'}/${c.attempted_scenarios??'—'} 완료`:'② 실행 대기';if(second.some(r=>!r.index_complete))$('exploreRankBasis').textContent+=' · 새 결과 지수 미집계';$('exploreRankBasis').title='저장 결과 원값의 지수 ≥70 집계. 새 결과 저장 시 지수 집계가 자동 생성됩니다. 미집계는 0 또는 기존 연기 수로 대체하지 않습니다.';
  if(value.saved_score?.opening_states&&JSON.stringify(value.saved_score.opening_states)!==JSON.stringify(value.score.opening_states))$('exploreRankBasis').textContent+=' · 현재 문 설정과 다름';
  if(value.fuel_rerun_required)$('exploreRankBasis').textContent+=' · 재실행 필요 (연료 변경)';
  const proposed=first[0]?.room??null;if(store.get('exploration').origin_room_id!==proposed||store.get('exploration').origin_mode!=='ranked')store.dispatch('exploration/set',{origin_room_id:proposed,origin_mode:'ranked'});
  if(value.available===false){$('exploreStatus').textContent=first.length?`적격 ${first.length}실 · 1위 화점 선정`:value.unavailable_reason||'화점 후보 없음';$('exploreRun').title=$('exploreOriginRun').title=value.unavailable_reason||'실행 연결 전';}
  sync();
 }
 return {update,mcState(value,pendingRequest=false){mcJob=value;mcPending=pendingRequest;sync();},catalog(c,origin){summary=c.mc_summary??null;mcOrigin=origin;sync();},busy(value){pending=value;sync();},status(message){$('exploreStatus').textContent=message;},dispose(){off();scope.remove();root.remove();style.remove();}};
}
