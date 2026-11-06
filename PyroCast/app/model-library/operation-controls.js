// Existing building-scoped single run, hosted in the shared Explore tab.
export async function attachOperationControls({app,info,initial}){
 const root=document.createElement('section');root.id='modelSingleRun';root.className='exploreCard';root.style.cssText='margin:12px;padding:12px;border:1px solid var(--border)';
 root.innerHTML='<h3>단일 화점 실행</h3><label>계산 층 <select id="opFloor"></select></label><label>화점 <select id="opRoom"></select></label><label>계산 시간 <select id="opDuration"><option value="60">1분 · 연결 확인</option><option value="1800">30분</option><option value="3600" selected>60분</option></select></label><label>급기 <select id="opState"><option value="open_except_confirmed">확정 방화문 제외 열림</option><option value="closed">전부 닫힘 · 누설만</option></select></label><button id="opRun">시뮬레이션 실행</button><div id="opStatus" role="status"></div><button id="opResult" hidden>완료 결과 보기</button>';
 const style=document.createElement('style');style.textContent='#modelSingleRun label{display:block;margin:8px 0}#modelSingleRun select{width:100%}#opStatus{margin:8px 0;font-size:12px}';root.append(style);document.getElementById('shellPane-explore').prepend(root);
 const $=id=>document.getElementById(id),abort=new AbortController();let poll=null,job=null,disposed=false;
 const api=async(path,options={})=>{const r=await fetch(path,{...options,signal:abort.signal}),v=await r.json();if(!r.ok)throw Error(v.error||'요청 실패');return v;};
 const cap=await api('/models/simulation/capabilities?building='+info.building_id);
 for(const f of cap.floors){const o=new Option(f.floor+(f.enabled?'':' · 계산 불가'),f.floor);o.disabled=!f.enabled;$('opFloor').add(o);}
 const original=initial.rooms.find(r=>r.key===initial.fire_key);$('opFloor').value=original?.cad_floor||cap.floors.find(f=>f.enabled)?.floor;
 function rooms(){const f=cap.floors.find(f=>f.floor===$('opFloor').value);$('opRoom').replaceChildren(...(f?.rooms||[]).map(r=>new Option(r.label,r.id)));$('opRun').disabled=!f?.enabled;}
 rooms();if(original)$('opRoom').value=original.original_room||original.key;
 $('opFloor').onchange=()=>{rooms();$('exploreRefresh').click();};
 async function watch(){clearTimeout(poll);try{const s=await api(`/models/simulation/status?building=${info.building_id}&job=${job}`);if(disposed)return;const busy=['queued','running'].includes(s.state);$('opRun').disabled=busy;$('opResult').hidden=s.state!=='complete';$('opStatus').textContent=s.state==='complete'?`완료 · ${s.wall_s.toFixed(1)}초`:s.state==='failed'?`실패 · ${s.error}`:'계산 중 · 현재 재생 유지';if(busy)poll=setTimeout(watch,1000);else $('liteRefresh').click();}catch(e){if(!disposed){$('opStatus').textContent=e.message;$('opRun').disabled=false;}}}
 $('opRun').onclick=async()=>{try{$('opRun').disabled=true;$('opResult').hidden=true;const r=await api('/models/simulation/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({building:info.building_id,floor:$('opFloor').value,room:$('opRoom').value,duration_s:Number($('opDuration').value),opening_state:$('opState').value})});job=r.job;await watch();}catch(e){$('opStatus').textContent=e.message;$('opRun').disabled=false;}};
 $('opResult').onclick=async()=>{const data=await api('/cfbt/lite/result/'+job);await app.install(data,job);$('liteRefresh').click();$('shellTab-result').click();};
 const pending=await api('/models/simulation/jobs?building='+info.building_id);const active=pending.jobs.find(j=>['queued','running'].includes(j.state));if(active){job=active.job;await watch();}
 return {floor:()=>$('opFloor').value,dispose(){disposed=true;clearTimeout(poll);abort.abort();root.remove();}};
}
