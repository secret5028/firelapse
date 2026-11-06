// Session-only conversation. API credentials never enter the browser.
export function createAIFuelPanel({onApplied,onRooms}){
 const root=document.createElement('details');root.id='aiFuel';root.innerHTML='<summary>AI 배치</summary><div id="aiFuelStatus" role="status"></div><div id="aiFuelConversation"></div><form id="aiFuelForm"><label for="aiFuelMessage">배치 설명</label><textarea id="aiFuelMessage" maxlength="4000" rows="3" placeholder="1층은 소매점이고 2층은 타이어창고" required></textarea><button id="aiFuelSend" disabled>제안 요청</button></form><div class="buildingScroll"><table><thead><tr><th>선택</th><th>실</th><th>현재 용도</th><th>제안 용도</th><th>MJ/m²</th><th>근거</th></tr></thead><tbody id="aiFuelRows"></tbody></table></div><button id="aiFuelApply" disabled>선택 적용</button>';
 document.getElementById('buildingContent').append(root);
 const style=document.createElement('style');style.textContent='#aiFuel{margin-top:18px}#aiFuel textarea{box-sizing:border-box;width:100%;background:var(--bg-card);color:var(--text)}#aiFuelStatus,#aiFuelConversation{font-size:11px;margin:8px 0;white-space:pre-wrap}#aiFuel td{min-width:60px}#aiFuel td:last-child{min-width:150px;white-space:normal}';document.head.append(style);
 const $=id=>root.querySelector('#'+id),abort=new AbortController(),history=[];
 let configured=false,busy=false,proposal=null,disposed=false;
 const offline=Boolean(window.__PYROCAST_OFFLINE__);
 const status=text=>{$('aiFuelStatus').textContent=text;};
 const buttons=()=>{$('aiFuelSend').disabled=offline||!configured||busy;$('aiFuelApply').disabled=offline||busy||!proposal||!root.querySelector('input[data-room]:checked');};
 async function api(path,body){const r=await fetch(path,{signal:abort.signal,...(body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{})});const v=await r.json();if(!r.ok)throw Error(v.error||'요청 실패');return v;}
 async function refresh(){if(offline){status('보기 전용');buttons();return;}try{const value=await api('/cfbt/lite/ai/fuel');if(disposed)return;configured=value.configured;onRooms(value.rooms);status(value.message||'제안 대기');buttons();}catch(e){if(!disposed){configured=false;status(e.message);buttons();}}}
 $('aiFuelForm').onsubmit=async e=>{e.preventDefault();if(busy||!configured||offline)return;const message=$('aiFuelMessage').value.trim();if(!message)return;busy=true;proposal=null;$('aiFuelRows').replaceChildren();buttons();status('AI 제안 요청 중…');
  try{const value=await api('/cfbt/lite/ai/fuel',{message,history:history.slice(-20)});if(disposed)return;proposal=value;history.push({role:'user',content:message},{role:'assistant',content:value.assistant});if(history.length>20)history.splice(0,history.length-20);$('aiFuelConversation').textContent=history.filter(r=>r.role==='user').map(r=>'나: '+r.content).join('\n');
   for(const row of value.rows){const tr=document.createElement('tr'),check=document.createElement('input');check.type='checkbox';check.dataset.room=row.room_id;check.setAttribute('aria-label',row.room_id+' 적용 선택');check.onchange=buttons;const td=document.createElement('td');td.append(check);tr.append(td);for(const text of [row.room_id.replace(/^CAD_/,'').replaceAll('_',' '),row.current_usage,row.proposed_usage,String(row.load),row.reason]){const cell=document.createElement('td');cell.textContent=text;tr.append(cell);}$('aiFuelRows').append(tr);}
   status(value.rows.length+'실 제안 · 적용할 행 선택');
  }catch(error){if(!disposed)status(error.message);}finally{busy=false;if(!disposed)buttons();}
 };
 $('aiFuelApply').onclick=async()=>{if(busy||!proposal||offline)return;const rooms=[...root.querySelectorAll('input[data-room]:checked')].map(el=>el.dataset.room);if(!rooms.length)return;busy=true;buttons();
  try{await api('/cfbt/lite/fuel-overrides',{proposal_id:proposal.proposal_id,rooms});if(disposed)return;proposal=null;await onApplied();await refresh();if(!disposed)status(rooms.length+'실 적용 · ① 갱신 · ② 재실행 필요');}catch(e){if(!disposed)status(e.message);}finally{busy=false;if(!disposed)buttons();}
 };
 buttons();return {refresh,dispose(){disposed=true;abort.abort();history.length=0;root.remove();style.remove();}};
}
