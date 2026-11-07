import {attentionRanking} from '../adapters/attention.js';
import {savedAttention} from '../data/saved_attention.js';
import {fixedInputFor} from '../state/fixed_openings.js';
const finite=Number.isFinite;
const count=v=>finite(v)?String(v):'—';
export function screeningRows(payload){
 const first=payload.score.ranked,byId=new Map(first.map(r=>[r.room,r]));
 return {first,second:attentionRanking(payload.comparison,payload.attention??savedAttention).map(r=>({...r,rank1:byId.get(r.room)?.rank1??r.rank1,name:byId.get(r.room)?.name??r.name}))};
}
export function mcEstimate(summary,samples){
 return finite(summary?.wall_s)&&summary.wall_s>0&&summary.completed>0?summary.wall_s/summary.completed*samples:null;
}
export function calculationStatus({floor,origin,job={},pending=false,dirty=false,changed=false,saved=false,verified=false}){
 if(pending)return '요청 중';
 if(job.running)return `계산 중 ${job.completed??0}/${job.total??'—'}`;
 if(job.server_busy)return '다른 계산 진행 중';
 if(!floor)return '층 선택 필요';
 if(!origin)return '화점 없음';
 if(dirty)return '가연물 변경 저장 필요';
 if(job.error&&(!job.room||job.room===origin))return '계산 실패';
 if(job.room===origin&&['failed','interrupted'].includes(job.state))return job.state==='failed'?'계산 실패':'계산 중단';
 if(changed)return '재계산 필요';
 if(job.room===origin&&job.state==='completed'&&job.total>0&&job.failed_or_incomplete>=job.total)return '계산 실패 · 완주 0/'+job.total;
 if(job.room===origin&&job.state==='completed')return job.failed_or_incomplete?'일부 미완료':verified?'계산 완료':'저장 결과 있음';
 return saved?'저장 결과 있음':'계산 전';
}
// The controller owns scene selection and I/O; picking a candidate never replaces playback.
export function createExplorePanel({store,onRun,onRunOrigin,onRefresh,onResults,onMC,onCalculate,onCalculationResult,onApplyWorst,onCandidate,onFloor,floors=[]}){
 const $=id=>document.getElementById(id),root=document.createElement('fieldset');root.id='exploreContent';$('shellPane-explore').append(root);
 root.innerHTML=`<div id="workflowFloor" class="exploreCard workflowStep"><h3>1단계 · 층 선택</h3><label>계산 층 <select id="exploreFloor" aria-label="계산 층"><option value="">층 하나를 선택하세요</option></select></label></div><div class="exploreCard workflowStep"><h3>3단계 · 화점 확인 <span tabindex="0" title="연료량이 많고, 환기가 부족하며, 화재가 확산될 통로가 많은 실을 우선합니다.&#10;&#10;후보 점수 = 연료량 + 환기 부족 + 확산 연결 + 복도 인접 + 격리 부족&#10;각 항목 0~1점, 합계 0~5점.&#10;후보 선별용 상대 점수이며 위험도 예측값은 아닙니다.">ⓘ</span></h3>
 <form id="exploreRunForm" hidden><label>상위 N <input id="exploreN" type="number" min="1" step="1" value="8" required></label><button id="exploreRun" type="submit" disabled>② 실행</button><button id="exploreRefresh" type="button">새로고침</button></form><div id="exploreStatus" role="status">목록 읽는 중</div><div class="exploreScroll"><table><thead><tr><th>#</th><th>후보 실</th><th>점수</th></tr></thead><tbody id="exploreCandidates"></tbody></table></div></div>
 <h3 hidden>② 시뮬레이션 순위 <span tabindex="0" title="표시 순위: 연소 실 수 → 주의 이상 실 수 → 최초 FO가 빠른 순. 주의 이상은 3현상 중 최대 지수 ≥70인 원래 방 수입니다. 두 극단 상태 중 나쁜 쪽을 사용합니다. 행을 선택하면 다음 탐색의 화점만 바뀝니다.">ⓘ</span></h3>
 <div class="exploreCard" hidden><div id="exploreRankBasis"></div><div class="exploreScroll"><table><thead><tr><th>#</th><th>화점</th><th>①순위</th><th>연소</th><th title="3현상 최대 지수 ≥70인 실 수">주의 ≥70</th><th>최초 FO</th></tr></thead><tbody id="exploreRanking"></tbody></table></div></div>
 <div class="exploreCard workflowStep"><h3>4단계 · MC 급기 탐색</h3><label hidden>화점 <select id="exploreOrigin" disabled></select></label><label>계산 시간 <select id="exploreDuration"><option value="1800">30분</option><option value="3600" selected>60분</option></select></label><label>표본 수 <input id="exploreSamples" type="number" min="2" max="1000" step="1" value="10" required></label><div id="exploreEstimate" title="저장된 MC 전체 경과시간 ÷ 완료 표본 수 × 요청 표본 수. 다른 화점과 개폐 조건의 소요시간은 달라질 수 있습니다.">예상 시간 —</div><div class="exploreButtons"><button id="exploreOriginRun" hidden disabled>선택 실 2상태 실행</button><button id="exploreMC" disabled title="MC 서버 연결 확인 중">최악 급기 탐색</button></div><div id="exploreMCStatus" role="status">MC 서버 연결 확인 중</div></div>
 <div class="exploreCard workflowStep"><h3>5단계 · 최악 결과 적용</h3><button id="exploreResults" disabled>MC 결과 보기</button><button id="exploreApplyWorst" disabled>최악 개폐 상태 적용·재생</button></div>
 <details id="exploreRules" hidden><summary>규칙 설정</summary><div id="exploreRuleContext"></div><div id="exploreRuleMount"></div></details>`;
 const style=document.createElement('style');style.dataset.pyrocastExplore='true';style.textContent=`
 #exploreContent{border:0;margin:0;min-width:0;padding:0 16px;font-size:13px;color:var(--text)}#exploreContent[disabled]{opacity:.5}#exploreContent h3,#workflowFloor h3{font-size:13px;font-weight:700;color:var(--text);margin:14px 0 8px}#workflowFloor h3{margin-top:0}#shellPane-building .workflowStep>h3{font-size:13px;font-weight:700;color:var(--text);margin:0 0 10px}#buildingContent{padding-top:0;padding-bottom:0}#exploreContent h3 span{cursor:help}.exploreCard{border:1px solid var(--border);border-radius:7px;padding:10px;margin-bottom:12px;background:var(--bg-card)}#exploreContent label{display:block;margin:6px 0}#exploreContent input,#exploreContent select,#exploreContent button{background:var(--bg-control);color:var(--text);border:1px solid var(--border-strong);border-radius:4px;padding:5px;box-sizing:border-box}#exploreContent input{width:70px}#exploreOrigin{width:100%;margin-top:5px}#exploreContent button{cursor:pointer}#exploreContent :disabled{opacity:.5;cursor:default}#exploreRunForm,.exploreButtons{display:flex;gap:6px;align-items:center;flex-wrap:wrap}#exploreContent :focus-visible{outline:2px solid var(--accent)}.exploreScroll{overflow:auto;max-height:270px}#exploreContent table{border-collapse:collapse;width:100%;font-size:11px}#exploreContent th,#exploreContent td{text-align:right;padding:7px 3px;border-bottom:1px solid var(--border);white-space:nowrap}#exploreContent th:nth-child(2),#exploreContent td:nth-child(2){text-align:left}#exploreContent td:nth-child(2){white-space:normal;min-width:68px}#exploreContent tr[data-room]{cursor:pointer}#exploreContent tr[aria-selected=true]{background:var(--bg-selected);box-shadow:inset 2px 0 var(--accent)}#exploreStatus,#exploreRankBasis,#exploreEstimate,#exploreMCStatus,#exploreRuleContext{font-size:11px;color:var(--text-muted);margin:8px 0;overflow-wrap:anywhere}#exploreContent details{margin-top:12px}#exploreContent summary{cursor:pointer;color:var(--text-muted)}#exploreRules input{max-width:100%}#exploreRules table{display:block;overflow:auto}#exploreRules #r8SettingsGrid{grid-template-columns:1fr!important}#exploreRules #cfbtFrozenRules>summary{display:none}
 `;document.head.append(style);
 // One explicit execution control at the end of the combined workflow.
 const calculate=document.createElement('section');calculate.id='exploreCalculate';calculate.className='exploreCard';
 calculate.innerHTML='<div class="exploreEngineButtons" role="group" aria-label="계산 방식"><button type="button" id="exploreEngineLite" aria-pressed="false">간략 계산</button><button type="button" id="exploreEngineCfast" aria-pressed="false">순정 CFAST</button></div><button type="button" id="exploreCalculateRun" disabled>계산하기</button><div id="exploreCalculateStatus" role="status"></div><div id="exploreCalculationProgress" hidden><span class="calculationSpinner" aria-hidden="true"></span><span id="exploreCalculationElapsed" aria-live="off"></span></div><button type="button" id="exploreCalculationResult" hidden>결과 보기</button>';
 style.textContent+=`#exploreContent .exploreEngineButtons{display:flex;gap:6px}#exploreContent .exploreEngineButtons button{flex:1;padding:9px 4px}#exploreContent .exploreEngineButtons button[aria-pressed=true]{background:var(--accent);border-color:var(--accent);color:var(--accent-fg);font-weight:700}#exploreCalculateRun:not(:disabled){background:var(--bg-control);border-color:var(--accent)}#exploreCalculationProgress:not([hidden]){display:flex;align-items:center;gap:7px;margin-top:8px;color:var(--accent);font-variant-numeric:tabular-nums}.calculationSpinner{width:12px;height:12px;border:2px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:calculationSpin .9s linear infinite}@keyframes calculationSpin{to{transform:rotate(360deg)}}@media(prefers-reduced-motion:reduce){.calculationSpinner{animation:none}}`;
 root.append(calculate);$('exploreMC').textContent='MC 급기 탐색';
 $('exploreCalculateRun').style.cssText='display:block;width:100%;padding:10px;margin-top:8px;font-weight:700';
 const fireInputs=document.createElement('fieldset');
 fireInputs.style.cssText='display:grid;gap:6px;margin:8px 0;padding:8px;border:1px solid var(--border)';
 fireInputs.innerHTML='<legend>이번 계산의 화원 입력</legend><label>화점실 가연물 총량 (GJ) <input id="exploreFuelEnergy" type="number" min="0.001" max="1000000" step="any" placeholder="저장값"></label><label>화점 셀 최대 발열률 (MW) <input id="exploreFirePeak" type="number" min="0.001" max="1000" step="any" placeholder="자동"></label><label>최소 누기 면적 (m²/경로) <input id="exploreLeakArea" type="number" min="0.0001" step="any" placeholder="계단 0.02 · 승강로 0.06"></label><small>빈칸은 저장 MC 입력을 사용합니다. 값을 바꾸면 기존 개폐 조합으로 해당 엔진을 새로 계산합니다.</small>';
 calculate.insertBefore(fireInputs,$('exploreCalculateRun'));
 let fireInputRoom;
 fireInputs.addEventListener('input',sync);
 let calculation={available:false},calculationPending=false,selectedEngine=null,calculationTimer=null,calculationStarted=0;
 for(const [id,engine] of [['exploreEngineLite','lite'],['exploreEngineCfast','cfast']])$(id).onclick=()=>{selectedEngine=engine;calculation={...calculation,error:null};sync();};
 function updateElapsed(){const seconds=Math.max(0,Math.floor((Date.now()-calculationStarted)/1000));$('exploreCalculationElapsed').textContent=`경과 ${String(Math.floor(seconds/60)).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;}
 $('exploreCalculationResult').onclick=onCalculationResult;
 function savedCalculationInput(state){
  const fixed=fixedInputFor(store.get('buildingReview'),state.origin_room_id);
  if(fixed&&fixed.source_room===state.origin_room_id&&(!fixed.duration_s||fixed.duration_s===state.duration_s))return {ready:true};
  if(calculation.saved_mc_input&&summary?.job_id&&summary.worst&&
    summary.source_room===state.origin_room_id&&summary.duration_s===state.duration_s)
   return {ready:true,job:summary.job_id,sample:summary.worst.sample_id};
  return {ready:false};
 }
 $('exploreCalculateRun').onclick=()=>{
  if(!selectedEngine||$('exploreCalculateRun').disabled)return;
  const inputs=[['fuel_energy_MJ',$('exploreFuelEnergy')],['fire_peak_kW',$('exploreFirePeak')]];
  if(inputs.some(([,input])=>!input.reportValidity()))return;
  const fire=Object.fromEntries(inputs.filter(([,input])=>input.value!=='').map(([key,input])=>[key,input.valueAsNumber*1000]));
  if($('exploreLeakArea').value!==''){if(!$('exploreLeakArea').reportValidity())return;fire.leakage_area_m2=$('exploreLeakArea').valueAsNumber;}
  onCalculate?.(selectedEngine,savedCalculationInput(store.get('exploration')).job,fire);
 };
 const scope=$('workflowFloor');scope.style.margin='12px 16px';if($('aiConnectionControl'))$('aiConnectionControl').after(scope);else $('shellPane-building').prepend(scope);
 for(const f of floors)$('exploreFloor').add(new Option(f.name,f.name));
 $('exploreFloor').onchange=()=>onFloor?.($('exploreFloor').value);
 $('exploreDuration').onchange=()=>store.dispatch('exploration/set',{duration_s:Number($('exploreDuration').value)});
 $('exploreApplyWorst').onclick=onApplyWorst;
 let previewStatus='미저장 변경 · 순위 갱신 중…',payload=null,summary=null,mcOrigin=null,pending=false,mcJob={available:false},mcPending=false,lastSamples=null,submitted=null;
 const inputKey=()=>JSON.stringify([store.get('floor').floor_id,store.get('exploration').origin_room_id,store.get('exploration').samples,store.get('exploration').duration_s,store.get('fuelSettings').data?.revision??null,store.get('buildingReview').doors]);
 const pretty=id=>id?.replace(/^CAD_/,'').replaceAll('_',' ')||'미선택';
 const useName=row=>row?.origin_budget?.classification?.label??payload?.score.approved_input?.room_uses?.[row?.room]?.label??'용도 미확인';
 const cadNames=new Map(floors.flatMap(f=>(f.rooms||[]).map(r=>[`CAD_${f.name}_${r.id}`,(r.names||[]).filter(Boolean).join(' · ')||r.name||''])));
 const originName=id=>{const row=payload?.score.ranked.find(r=>r.room===id),manual=payload?.manual_origins?.find(r=>r.room===id),name=cadNames.get(id),usage=row?useName(row):manual?.label;return `${pretty(id)}${name?' · '+name:usage?' · '+usage:''}${name&&usage&&name!==usage?' ('+usage+')':''}`;};
 const cell=(tr,value)=>{const td=document.createElement('td');td.textContent=value;tr.append(td);return td;};
 function sync(){root.disabled=!store.get('floor').floor_id;root.inert=root.disabled;const state=store.get('exploration');$('exploreFloor').value=store.get('floor').floor_id||'';$('exploreDuration').value=state.duration_s;$('exploreN').value=state.top_n;if(lastSamples!==state.samples){$('exploreSamples').value=state.samples;lastSamples=state.samples;}$('exploreOrigin').value=state.origin_room_id||'';
  for(const tr of root.querySelectorAll('tr[data-room]'))tr.setAttribute('aria-selected',String(tr.dataset.room===state.origin_room_id));
  const estimate=mcEstimate(summary,state.samples);$('exploreEstimate').textContent=estimate===null?'예상 시간 미확인':`예상 약 ${Math.ceil(estimate/60)}분 · 이전 MC 기준`;
  $('exploreOriginRun').textContent=payload?.opening_mode==='fixed'?'선택 실 확정 급기 실행':'선택 실 2상태 실행';
  const matching=Boolean(summary&&mcOrigin&&state.origin_room_id===mcOrigin);$('exploreApplyWorst').disabled=!matching||!summary?.worst||mcJob.running||mcPending;
  $('exploreResults').disabled=!matching;
  $('exploreResults').title=matching?'선택 화점의 저장 MC 집계 보기':`선택 화점의 저장 MC 결과 없음${mcOrigin?' · 저장 화점 '+pretty(mcOrigin):''}`;
  const fuel=store.get('fuelSettings'),dirty=Object.values(fuel.draft).some(v=>v&&Object.keys(v).length),changed=!!submitted&&submitted.key!==inputKey();
  let fuelNotice=$('exploreFuelNotice');if(!fuelNotice){fuelNotice=document.createElement('small');fuelNotice.id='exploreFuelNotice';$('exploreCandidates').closest('.exploreScroll').before(fuelNotice);}fuelNotice.hidden=!dirty&&!fuel.saving;fuelNotice.textContent=fuel.saving?'저장·순위 갱신 중…':previewStatus;
  $('exploreMC').disabled=mcPending||!mcJob.available||mcJob.server_busy||mcJob.running||!state.origin_room_id||!store.get('floor').floor_id||dirty||fuel.saving;
  $('exploreMC').title=dirty?'가연물 변경을 먼저 저장하세요':mcJob.available?'간략 엔진으로 개구부 조합 MC 계산 · 직렬 실행 · 표본당 적분 예산 1,200초':'MC 실행 연결 없음';
  $('exploreMCStatus').textContent=mcJob.error?'MC 오류 · '+mcJob.error:mcPending?'MC 요청 중':mcJob.running?`MC ${mcJob.completed??0}/${mcJob.total??state.samples} · ${mcJob.current??mcJob.state}`:mcJob.server_busy?'다른 계산 진행 중':({completed:`MC 완료${mcJob.failed_or_incomplete?' · 실패·미완료 '+mcJob.failed_or_incomplete+'건':''}`,failed:'MC 실패',interrupted:'MC 중단'}[mcJob.state]||'MC 대기')+(matching?' · 저장 결과 있음':' · 저장 결과 없음');
  $('exploreMCStatus').title=mcJob.error||'현재 화점 기준. 저장 결과 있음은 현재 설정과의 일치 확인을 뜻하지 않습니다.';
  $('exploreMCStatus').textContent=calculationStatus({floor:store.get('floor').floor_id,origin:state.origin_room_id,job:mcJob,pending:mcPending,dirty,changed,saved:matching,verified:submitted?.id===mcJob.id&&!changed});
  if(!mcJob.available&&!mcPending)$('exploreMCStatus').textContent='실행 연결 없음';
  if($('exploreMCStatus').textContent==='저장 결과 있음')$('exploreMCStatus').textContent='';
  const kind=selectedEngine,{ready,sample}=savedCalculationInput(state);
  const calculating=calculationPending||calculation.running;
  if(fireInputRoom!==state.origin_room_id){
   fireInputRoom=state.origin_room_id;$('exploreFuelEnergy').value='';$('exploreFirePeak').value='';
  }
  const customFire=$('exploreFuelEnergy').value!==''||$('exploreFirePeak').value!=='';
  fireInputs.disabled=!!calculating||!calculation.available;
  $('exploreCalculationResult').hidden=calculating||!!calculation.error||calculation.state!=='complete'||!calculation.case_id;
  $('exploreCalculationResult').textContent=(calculation.engine==='cfast'?'순정 CFAST':'간략 계산')+' 결과 보기';
  for(const [id,engine] of [['exploreEngineLite','lite'],['exploreEngineCfast','cfast']]){$(id).disabled=calculating;$(id).setAttribute('aria-pressed',String(kind===engine));}
  calculate.setAttribute('aria-busy',String(!!calculating));
  $('exploreCalculateRun').textContent=calculationPending?'요청 중…':calculation.running?'계산 중…':'계산하기';
  $('exploreCalculationProgress').hidden=!calculating;
  if(calculating){if(!calculationTimer){calculationStarted=calculation.started_at_ms||Date.now();calculationTimer=setInterval(updateElapsed,1000);}updateElapsed();}
  else if(calculationTimer){clearInterval(calculationTimer);calculationTimer=null;}
  $('exploreCalculateRun').disabled=!kind||!calculation.available||!ready||dirty||fuel.saving||calculating||mcJob.running||mcPending||calculation.server_busy||mcJob.server_busy||(kind==='cfast'&&!calculation.cfast_available);
  $('exploreMC').disabled ||= calculating||calculation.server_busy;
  $('exploreCalculateRun').title=kind==='cfast'?'선택한 급기 조합으로 순정 CFAST 1회':customFire?'수정한 화원 입력으로 간략 엔진 1회':'동일 조건의 완료된 간략 MC 결과 사용 · 재계산 없음';
  $('exploreCalculateStatus').style.cssText='font-size:11px;margin-top:8px;color:var(--text-muted)';
  const openingLabel=sample?`저장 MC 최악 조합 ${sample}`:'확정 급기';
  $('exploreCalculateStatus').textContent=calculation.error?'계산 실패 · '+calculation.error:calculationPending?'계산 요청 중':calculating?`${calculation.engine==='cfast'?'순정 CFAST':'간략 계산'} · 계산 중`:!calculation.available?'실행 연결 없음':!kind?'계산 방식을 선택하세요':(calculation.server_busy||mcJob.running||mcPending||mcJob.server_busy)?'다른 계산 진행 중':dirty?'가연물 변경 저장 필요':kind==='cfast'&&!calculation.cfast_available?'순정 CFAST 실행 파일 없음':!ready?(calculation.saved_mc_input?'이 화점과 같은 계산 시간의 완료 MC가 필요합니다':'최악 개폐 상태 적용 후 계산'):!customFire&&calculation.state==='complete'&&calculation.room===state.origin_room_id&&calculation.engine===kind?'계산 완료':openingLabel+(kind==='cfast'||customFire?' · 1회 계산':' · 간략 결과 불러오기');
  $('exploreCalculateStatus').className=calculation.error?'status-error':calculating?'status-busy':$('exploreCalculateStatus').textContent==='계산 완료'?'status-ok':'';
  $('exploreMCStatus').className=/실패|시간초과|차단|미완료|오류/.test($('exploreMCStatus').textContent)?'status-error':(mcJob.running||mcPending)?'status-busy':/완료/.test($('exploreMCStatus').textContent)?'status-ok':'';
  $('exploreEstimate').className=estimate===null?'':'status-busy';
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
 const off=store.subscribe('exploration',sync),offFloor=store.subscribe('floor',sync),offFuel=store.subscribe('fuelSettings',sync),offDoors=store.subscribe('buildingReview',sync);
 function update(value){payload=value;const {first,second}=screeningRows(value);$('exploreN').max=first.length;$('exploreOrigin').replaceChildren();for(const row of value.manual_origins??first)$('exploreOrigin').add(new Option(originName(row.room),row.room));$('exploreOrigin').disabled=!first.length;
  $('exploreCandidates').replaceChildren();for(const row of first.slice(0,5)){const tr=document.createElement('tr');tr.dataset.room=row.room;tr.tabIndex=0;tr.setAttribute('aria-label',originName(row.room)+' 화점 선택');
   const choose=()=>{store.dispatch('exploration/set',{origin_room_id:row.room,origin_mode:'manual'});onCandidate?.(row);};tr.onclick=choose;tr.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();choose();}};cell(tr,count(row.rank1));cell(tr,originName(row.room)).title=row.reason||'';cell(tr,finite(row.score)?row.score.toFixed(3):'—');$('exploreCandidates').append(tr);}
  $('exploreRanking').replaceChildren();for(const row of second){const tr=document.createElement('tr');tr.dataset.room=row.room;tr.tabIndex=0;tr.setAttribute('aria-label',originName(row.room)+' 화점 선택');tr.title=row.complete?({fixed:'확정 급기',closed:'모두 닫힘',open_except_confirmed:'확정 방화문 제외 모두 열림'}[row.worst_state]||''):'미완료 · 부분 결과';cell(tr,count(row.rank2));cell(tr,pretty(row.room));cell(tr,count(row.rank1));cell(tr,count(row.burning_room_count));cell(tr,count(row.attention_room_count));cell(tr,finite(row.first_FO_s)?`${Math.floor(row.first_FO_s/60)}:${String(Math.floor(row.first_FO_s%60)).padStart(2,'0')}`:'—');
   const choose=()=>{if((value.manual_origins??first).some(r=>r.room===row.room))store.dispatch('exploration/set',{origin_room_id:row.room,origin_mode:'ranked'});};tr.onclick=choose;tr.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();choose();}};$('exploreRanking').append(tr);
  }
  if(!second.length){const tr=document.createElement('tr'),td=cell(tr,'저장된 ② 결과 없음');td.colSpan=6;$('exploreRanking').append(tr);}
  const progress=value.progress;$('exploreStatus').textContent=progress?.running?`② 계산 중 ${progress.completed??0}/${progress.total??'—'} · ${progress.current_room??''}`:progress?.error?'② 실패 · '+progress.error:`적격 ${first.length}실`;
  $('exploreStatus').className=progress?.error?'status-error':progress?.running?'status-busy':'';
  const c=value.comparison;$('exploreRankBasis').textContent=c?`저장 결과 · ${c.manual_rooms?'수동 지정':'상위'} ${c.top_n} × ${c.opening_mode==='fixed'?'확정 급기 1회':'2상태'} · ${c.complete_scenarios??'—'}/${c.attempted_scenarios??'—'} 완료`:'② 실행 대기';if(second.some(r=>!r.index_complete))$('exploreRankBasis').textContent+=' · 새 결과 지수 미집계';$('exploreRankBasis').title='저장 결과 원값의 지수 ≥70 집계. 새 결과 저장 시 지수 집계가 자동 생성됩니다. 미집계는 0 또는 기존 연기 수로 대체하지 않습니다.';
  if(value.saved_score?.opening_states&&JSON.stringify(value.saved_score.opening_states)!==JSON.stringify(value.score.opening_states))$('exploreRankBasis').textContent+=' · 현재 문 설정과 다름';
  if(value.fuel_rerun_required)$('exploreRankBasis').textContent+=' · 재실행 필요 (연료 변경)';
  const chosen=store.get('exploration'),keepChosen=chosen.origin_mode==='manual'&&first.some(r=>r.room===chosen.origin_room_id);const proposed=first[0]?.room??null;if(!keepChosen&&(chosen.origin_room_id!==proposed||chosen.origin_mode!=='ranked'))store.dispatch('exploration/set',{origin_room_id:proposed,origin_mode:'ranked'});
  if(value.available===false){$('exploreStatus').textContent=first.length?`적격 ${first.length}실`:value.unavailable_reason||'화점 후보 없음';$('exploreRun').title=$('exploreOriginRun').title=value.unavailable_reason||'실행 연결 전';}
  sync();
 }
 return {update,calculationState(value,pendingRequest=false){calculation=value;calculationPending=pendingRequest;if(value.running||pendingRequest)selectedEngine=value.engine;sync();},previewState(message){previewStatus=message;sync();},calculationKey:inputKey,mcSubmitted(value,key){submitted={id:value.id,key};sync();},mcState(value,pendingRequest=false){mcJob=value;mcPending=pendingRequest;sync();},catalog(c,origin){summary=c.mc_summary??null;mcOrigin=origin;sync();},busy(value){pending=value;sync();},status(message){$('exploreStatus').textContent=message;},dispose(){if(calculationTimer)clearInterval(calculationTimer);off();offFloor();offFuel();offDoors();scope.remove();root.remove();style.remove();}};
}
