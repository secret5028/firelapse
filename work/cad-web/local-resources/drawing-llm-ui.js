(function(){
 if(!window.LOCAL_JOB||document.getElementById('llmReviewPanel'))return;
 const panel=document.createElement('section');panel.id='llmReviewPanel';panel.style.cssText='border:1px solid #748b9d;border-radius:7px;margin:12px 0;padding:12px';
 panel.innerHTML='<strong>AI 도면 보완</strong><p data-status role="status">API 설정 확인 중</p><label>참조 도면 쪽 번호 (최대 2개)<input data-refs placeholder="예: 1, 2" style="width:100%"></label><button data-run>현재 도면 자동 보완</button><button data-undo>이번 AI 보완 되돌리기</button><p>코드가 짧은 선 끊김을 탐지 → 원본·보정본·주변 문맥을 AI가 검토 → 코드가 검증합니다. API 사용 시 해당 이미지가 설정된 OpenAI API로 전송됩니다. 최대 3회 검토하며 판독 불가는 알립니다.</p>';
 const target=document.getElementById('gapPanel')||document.getElementById('workspacePanel');if(!target)return;target.after(panel);
 const status=panel.querySelector('[data-status]'),run=panel.querySelector('[data-run]');let busy=false,last=null;
 fetch('/api/llm/status').then(r=>r.json()).then(v=>{status.textContent=v.enabled&&v.configured?'API 연결 설정됨 · '+v.model:'API 설정 대기 · 후보 탐지와 요청 준비만 가능합니다.';}).catch(()=>status.textContent='AI 보완 서버를 사용할 수 없습니다.');
 run.onclick=async()=>{if(busy)return;busy=true;run.disabled=true;const idx=typeof index==='number'?index:0,p=state.pages[idx],baseline=JSON.stringify(p.shapes||[]),sourceHash=state.sourceHash;status.textContent='끊긴 선 후보 탐지 및 AI 검토 중…';
  try{const refs=panel.querySelector('[data-refs]').value.split(',').map(x=>x.trim()).filter(Boolean).map(x=>Number(x)-1);if(refs.length>2||refs.some(i=>!Number.isInteger(i)||i<0||i>=D.pages.length))throw Error('참조 도면 번호를 확인하세요.');
   const response=await fetch('/api/jobs/'+window.LOCAL_JOB+'/llm-review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({page:idx,sourceHash,references:refs})}),v=await response.json();if(!response.ok)throw Error(v.error||'검토 요청 실패');
   if(state.sourceHash!==sourceHash||JSON.stringify(p.shapes||[])!==baseline)throw Error('검토 중 도면이 변경되어 보정안을 적용하지 않았습니다.');
   p.llmReview=v;last={page:p,ids:[]};p.repairs||=[];for(const repair of v.accepted||[]){const id=v.requestId+':'+repair.id;if(p.repairs.some(r=>r.llmId===id))continue;p.repairs.push({...repair,llmId:id,at:new Date().toISOString()});last.ids.push(id);}
   if(typeof saveReview==='function')saveReview();else if(typeof persist==='function')persist();if(typeof draw==='function')draw();
   status.textContent=v.message+' 후보 '+(v.candidateCount||0)+'개 · 이번 보정 '+last.ids.length+'개 · 미확정 '+(v.unresolved?.length||0)+'개'+(v.deferred?' · 후속 검토 대기 '+v.deferred+'개':'');
  }catch(e){status.textContent=e.message;}finally{busy=false;run.disabled=false;}
 };
 panel.querySelector('[data-undo]').onclick=()=>{if(!last?.ids.length)return;last.page.repairs=last.page.repairs.filter(r=>!last.ids.includes(r.llmId));last.ids=[];if(typeof saveReview==='function')saveReview();else if(typeof persist==='function')persist();if(typeof draw==='function')draw();status.textContent='이번 AI 보정만 되돌렸습니다. 원본과 기존 보정은 유지됩니다.';};
})();
