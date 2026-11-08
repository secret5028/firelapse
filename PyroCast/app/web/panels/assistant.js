import {bindResizeHandle} from './resize_handle.js';
// D-4 view boundary. Text/numbers come from server evidence; actions need a click.
export function createAssistantPanel({store,revealSidebar,available=true,getContext,onNavigate,onProposal,onSaved}){
 const $=id=>document.getElementById(id),root=document.createElement('details');root.id='aiAssistant';root.open=false;
 root.innerHTML='<summary>AI 대화창</summary><div class="aiBody"><button type="button" id="aiBrief">결과 요약</button><div id="aiStatus" role="status"></div><div id="aiConversation" aria-live="polite"></div><form id="aiChat"><label>질문<textarea id="aiMessage" rows="3" maxlength="4000" placeholder="결과 질문 또는 용도·가연물 변경 요청" required></textarea></label><button id="aiSend">보내기</button></form><details id="aiPending" hidden><summary>적용 대기</summary><div id="aiProposals"></div></details></div>';
 const sidebar=$('pyroShellSidebar');sidebar.append(root);
 const openButton=document.createElement('button');
 openButton.id='shellAiChat';
 openButton.type='button';
 openButton.textContent='AI 대화';
 openButton.style.whiteSpace='nowrap';
 openButton.setAttribute('aria-controls',root.id);
 $('pyroShellHeader').append(openButton);
 const style=document.createElement('style');style.textContent=`#aiAssistant{flex-shrink:0;background:var(--bg-panel);color:var(--text);border:1px solid var(--border);font:13px system-ui;z-index:160;max-width:96vw}#aiPending[hidden],#aiAssistant[hidden]{display:none!important}.aiFuelProposal{border-collapse:collapse;font-size:11px}.aiFuelProposal th,.aiFuelProposal td{padding:6px;border-bottom:1px solid var(--border);text-align:left;min-width:50px}.aiFuelProposal td:last-child{min-width:120px}#aiAssistant>summary{padding:9px;cursor:pointer;font-weight:600}body.pyroShell:not(.shellExpanded) #pyroShellSidebar #aiAssistant{display:block}@media(max-width:860px){body.pyroShell:not(.shellExpanded) #pyroShellSidebar #aiAssistant{display:none}}.aiBody{box-sizing:border-box;padding:10px;height:var(--ai-height,160px);max-height:var(--ai-max-height,50vh);overflow:auto}#aiAssistant textarea{box-sizing:border-box;width:100%;color:inherit;background:var(--bg-control)}#aiAssistant button{margin:3px;color:inherit;background:var(--bg-control);border:1px solid var(--border-strong);padding:5px;cursor:pointer}#aiAssistant button:disabled{opacity:.45;cursor:default}.aiAnswer{white-space:pre-wrap;border-bottom:1px solid var(--border);padding:8px 0}#aiAssistant .aiAnswer section{margin:0 0 14px!important;line-height:1.6}#aiAssistant .aiAnswer section .aiFact{border:0;background:transparent;padding:0;margin:5px 0 0;line-height:1.6;font-weight:normal}#aiAssistant .aiAnswer section .aiFact:hover{text-decoration:underline}.aiEvidence{font-size:11px;color:var(--text-muted)}.aiFact{display:block;text-align:left}#aiAssistant{position:relative;width:100%;box-sizing:border-box;margin-top:10px}#aiResize{position:absolute;top:-5px;left:0;right:0;height:10px;cursor:row-resize;z-index:1}#aiResize:hover,#aiResize:focus-visible{background:color-mix(in srgb,var(--accent) 33.333333%,transparent)}#aiAssistant:not([open]) #aiResize{display:none}`;document.head.append(style);
 let contextRequest=new AbortController(),disposed=false,busy=false,session=null,ctxKey='',briefingTurn=null,reportRequest=null;
 const resize=document.createElement('div');resize.id='aiResize';resize.setAttribute('aria-label','AI 대화창 높이 조절');resize.title='드래그하여 대화창 높이 조절';root.append(resize);
 const resizeLimit=new ResizeObserver(()=>root.style.setProperty('--ai-max-height',Math.max(120,sidebar.clientHeight*.5)+'px'));resizeLimit.observe(sidebar);
 const unbindResize=bindResizeHandle(resize,{axis:'y',value:()=>root.querySelector('.aiBody').getBoundingClientRect().height,setValue:n=>root.style.setProperty('--ai-height',n+'px'),limits:()=>[120,Math.max(120,sidebar.clientHeight*.5)]});
 const syncExpanded=()=>openButton.setAttribute('aria-expanded',String(root.open&&!root.hidden&&!sidebar.hidden));
 const syncTabVisibility=()=>{root.hidden=$('shellTab-display')?.getAttribute('aria-selected')==='true';syncExpanded();};
 const tabObserver=new MutationObserver(syncTabVisibility);tabObserver.observe($('pyroShellTabs'),{subtree:true,attributes:true,attributeFilter:['aria-selected']});syncTabVisibility();
 const sidebarObserver=new MutationObserver(syncExpanded);sidebarObserver.observe(sidebar,{attributes:true,attributeFilter:['hidden']});
 root.addEventListener('toggle',syncExpanded);
 openButton.onclick=()=>{
  revealSidebar();
  if(root.hidden)$('shellTab-result').click();
  syncTabVisibility();
  root.open=true;
  syncExpanded();
  root.querySelector('summary').focus();
 };
 const status=s=>{$('aiStatus').textContent=s;};
 const readable=value=>String(value).replace(/CAD_[A-Za-z0-9]+_[A-Za-z0-9_]+/g,id=>id.slice(4).replaceAll('_',' '));
 const offline=!!window.__PYROCAST_OFFLINE__;
 async function api(path,body){const r=await fetch('/cfbt/lite/ai/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:contextRequest.signal});const v=await r.json();if(!r.ok)throw Error(v.error||'요청 실패');return v;}
 function buttons(){for(const id of ['aiSend','aiBrief'])$(id).disabled=busy||offline||!available;}
 const hasCase=ctx=>ctx.case&&ctx.case!=='model-preview';
 function syncPending(){const pending=$('aiPending');pending.hidden=!$('aiProposals').children.length;if(pending.hidden)pending.open=false;}
 function resetContext(){
  const {building,case:caseId}=getContext(),key=JSON.stringify([building,caseId]);
  if(key===ctxKey)return;
  contextRequest.abort();contextRequest=new AbortController();
  ctxKey=key;session=null;busy=false;briefingTurn=null;
  $('aiConversation').replaceChildren();$('aiMessage').value='';
  $('aiProposals').replaceChildren();syncPending();status('');buttons();
 }
 function answer(value,turn){
  const box=document.createElement('div');box.className='aiAnswer';const used=new Set();
  function factButton(fact){const b=document.createElement('button');b.type='button';b.className='aiFact';b.textContent=fact.text;if(fact.tooltip)b.title=fact.tooltip;b.disabled=!fact.room;b.onclick=()=>{try{onNavigate({...fact,case:value.case});}catch(e){status(e.message);}};box.append(b);}
  if(value.sections){for(const section of value.sections){const paragraph=document.createElement('section');paragraph.style.margin='0 0 14px';const heading=document.createElement('strong');heading.textContent=section.title;paragraph.append(heading);box.append(paragraph);const fact=(value.facts||[]).find(f=>f.text===section.text);if(fact){used.add(fact);factButton(fact);paragraph.append(box.lastElementChild);}else{const text=document.createElement('div');text.textContent=section.text;text.style.marginTop='5px';paragraph.append(text);}}}
  else for(const line of (value.text||'').split('\n')){const fact=(value.facts||[]).find(f=>f.text===line.trim());if(fact){used.add(fact);factButton(fact);}else{const text=document.createElement('div');text.textContent=line;box.append(text);}}
  for(const fact of value.facts||[])if(!used.has(fact))factButton(fact);
  const basis=document.createElement('div');basis.className='aiEvidence';basis.textContent=`근거: 도구 호출 ${value.calls?.length??0}회 · 사례 ${value.case??'미선택'} · 규칙 ${(value.rules||[]).join(', ')||'없음'}`;box.append(basis);
  if(value.briefing_id){const save=document.createElement('button');save.textContent='보고서로 저장';save.disabled=offline;save.onclick=async()=>{save.disabled=true;try{const r=await api('reports/save',{briefing_id:value.briefing_id});await onSaved(r);status('사례 보고서 저장 완료');}catch(e){status(e.message);save.disabled=false;}};box.append(save);}
  turn.append(box);box.scrollIntoView({block:'nearest'});
  for(const proposal of value.proposals||[]){const block=document.createElement('div'),selected=[];
   if(proposal.kind==='fuel'&&proposal.rows){
    const wrap=document.createElement('div');wrap.style.overflowX='auto';const table=document.createElement('table');table.className='aiFuelProposal';
    const head=document.createElement('thead'),header=document.createElement('tr');for(const title of ['선택','실','현재 용도','제안 용도','MJ/m²','근거']){const th=document.createElement('th');th.textContent=title;header.append(th);}head.append(header);table.append(head);const body=document.createElement('tbody');
    for(const row of proposal.rows){const tr=document.createElement('tr'),td=document.createElement('td'),c=document.createElement('input');c.type='checkbox';c.dataset.room=row.room_id;c.setAttribute('aria-label',readable(row.room_id)+' 적용 선택');td.append(c);tr.append(td);selected.push(c);
     for(const value of [readable(row.room_id),row.current_usage,row.proposed_usage,row.load,row.reason]){const cell=document.createElement('td');cell.textContent=value??'—';tr.append(cell);}body.append(tr);
    }table.append(body);wrap.append(table);block.append(wrap);
   }else{const pre=document.createElement('pre');pre.textContent=readable(JSON.stringify(proposal,null,2));block.append(pre);}
   const apply=document.createElement('button');apply.textContent=proposal.kind==='mc'||proposal.kind==='screening'?'사용자 실행':'선택 적용';const updateApply=()=>{apply.disabled=offline||(proposal.kind==='fuel'&&!selected.some(c=>c.checked));};for(const c of selected)c.onchange=updateApply;updateApply();apply.onclick=async()=>{if(apply.disabled)return;apply.disabled=true;try{await onProposal(proposal,selected.filter(c=>c.checked).map(c=>c.dataset.room),value.building);status('요청 반영 · 현재 사례는 유지됩니다');block.remove();syncPending();}catch(e){status(e.message);updateApply();}};block.append(apply);$('aiProposals').append(block);syncPending();$('aiPending').open=true;
  }
 }
 async function request(brief=false){resetContext();if(busy||offline)return;const ctx=getContext(),signal=contextRequest.signal;
  if(brief&&!hasCase(ctx)){status('왼쪽 저장 결과 목록에서 사례를 먼저 선택하세요.');return;}
  const message=brief?'브리핑':$('aiMessage').value.trim();if(!message)return;
  busy=true;buttons();status('근거 조회 중…');
  const turn=document.createElement('div'),question=document.createElement('p');
  question.textContent='나: '+(brief?'결과 요약':message);
  turn.append(question);$('aiConversation').append(turn);
  try{
   const value=await api(brief?'briefing':'chat',{context:ctx,message,session});
   if(signal.aborted)return;
   session=value.session??session;
   if(brief||value.briefing_id){briefingTurn?.remove();briefingTurn=turn;}
   answer(value,turn);status(value.status||'완료');if(!brief)$('aiMessage').value='';
  }catch(e){if(!signal.aborted){turn.remove();status(e.message);}}
  finally{if(!signal.aborted){busy=false;buttons();}}
 }
 $('aiChat').onsubmit=e=>{e.preventDefault();request();};$('aiBrief').onclick=()=>request(true);
 const summaryCard=document.createElement('details');
 summaryCard.id='resultSavedSummary';
 summaryCard.className='resultCard';
 summaryCard.open=true;
 summaryCard.hidden=true;
 summaryCard.innerHTML='<summary>결과 요약</summary><div role="status"></div>';
 const summaryBody=summaryCard.lastElementChild;
 Object.assign(summaryBody.style,{maxHeight:'220px',overflow:'auto',whiteSpace:'pre-wrap',overflowWrap:'anywhere'});
 $('resultContent').append(summaryCard);
 let summaryRequest=null;
 async function loadSummary(){
  const ctx=getContext(),signal=contextRequest.signal;
  if(signal===summaryRequest)return;
  summaryRequest=signal;
  const embedded=window.__PYROCAST_OFFLINE__?.saved_summary;
  summaryCard.hidden=!hasCase(ctx)||(offline&&!embedded);
  summaryBody.textContent='';
  if(summaryCard.hidden)return;
  summaryBody.textContent='저장 결과 요약을 불러오는 중…';
  try{
   const value=offline?embedded:await api('saved-summary',{context:{building:ctx.building,case:ctx.case}});
   if(signal.aborted)return;
   summaryBody.replaceChildren();
   for(const section of value.sections){
    const block=document.createElement('section'),heading=document.createElement('h3'),text=document.createElement('div');
    heading.textContent=section.title;text.textContent=section.text;block.append(heading,text);summaryBody.append(block);
   }
   summaryBody.scrollTop=0;
  }catch(e){if(!signal.aborted)summaryBody.textContent=e.message;}
 }
 const saved=document.createElement('details');saved.id='aiSavedReports';saved.hidden=true;saved.innerHTML='<summary>AI 브리핑 보고서</summary><div></div>';$('resultCase').append(saved);
 async function reports(){const c=getContext(),signal=contextRequest.signal;if(reportRequest===signal)return;reportRequest=signal;saved.hidden=true;saved.querySelector('div').replaceChildren();if(!hasCase(c))return;try{const value=offline?(window.__PYROCAST_OFFLINE__.assistant_reports||[]):(await api('reports/list',{context:c})).reports;if(signal.aborted)return;saved.hidden=!offline||value.length===0;for(const r of value){const item=document.createElement('details'),s=document.createElement('summary'),p=document.createElement('pre');s.textContent=r.case+' · '+r.created;p.textContent=readable(r.markdown);item.append(s,p);saved.querySelector('div').append(item);}}catch(e){if(!signal.aborted)status(e.message);}}
 const off=store.subscribe('result',()=>{resetContext();if(store.get('result')){loadSummary();reports();}});resetContext();buttons();
 if(offline)status('보기 전용');
 return {refreshReports(){if(disposed)return;reportRequest=null;return reports();},dispose(){disposed=true;contextRequest.abort();off();tabObserver.disconnect();sidebarObserver.disconnect();resizeLimit.disconnect();unbindResize();openButton.remove();root.remove();style.remove();saved.remove();summaryCard.remove();}};
}
