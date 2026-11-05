// Display-only snapshot/export boundary. No calculation inputs are changed here.
export function attachExport({store,viewer,getCase,getRoute,render}){
 const root=document.createElement('div');root.id='resultExport';
 root.innerHTML='<button id="exportHTML">HTML 내보내기</button> <label id="exportIntervalLabel" hidden>표시 간격 <select id="exportInterval"><option value="10">10 s · 원본</option><option value="20">20 s · 축소</option></select></label><output id="exportStatus" role="status"></output>';
 const card=document.getElementById('resultCase'),assistant=document.getElementById('aiAssistant');
 if(assistant?.parentElement===card)card.insertBefore(root,assistant);else card.append(root);
 const button=root.querySelector('button'),status=root.querySelector('output');
 function snapshot(){const route=getRoute();return Object.fromEntries([
  ...['selection','floor','playback','realView','openings','layers','risk','exploration',...(viewer.capabilities?.exportPost?['fuelSettings']:[])].map(k=>[k,store.get(k)]),
  ['route',{...store.get('route'),vehicle:route?.vehicle??store.get('route').vehicle,placing:false}],
  ['route_result',route],['camera',{position:viewer.C.position.toArray(),up:viewer.C.up.toArray(),target:viewer.O.target.toArray()}]
 ]);}
 button.onclick=async()=>{const caseId=getCase();button.disabled=true;status.textContent=' 묶는 중…';try{
  const payload={state:snapshot(),interval:Number(root.querySelector('select').value)},post=viewer.capabilities?.exportPost;
  const query=new URLSearchParams({state:JSON.stringify(payload.state),interval:payload.interval});
  const response=await fetch('/cfbt/lite/export/'+encodeURIComponent(caseId)+(post?'':'?'+query),post?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}:undefined);
  if(!response.ok){const error=await response.json().catch(()=>null);throw Error(error?.error||'내보내기 실패 · HTTP '+response.status);}
  const blob=await response.blob(),large=blob.size>50*1024*1024;
  root.querySelector('label').hidden=!large&&root.querySelector('select').value==='10';
  const link=document.createElement('a'),url=URL.createObjectURL(blob);link.href=url;link.download=`FireLapse-${caseId}-${payload.interval}s.html`;link.click();setTimeout(()=>URL.revokeObjectURL(url),60000);
  if(getCase()===caseId)status.textContent=` ${(blob.size/1024/1024).toFixed(2)} MiB`+(large?' · 50 MiB 초과: 20 s 선택 후 다시 내보내기 가능':'');
 }catch(e){status.textContent=' '+e.message;}finally{button.disabled=false;}};
 const offline=window.__PYROCAST_OFFLINE__,cleanups=[];
 if(!offline)cleanups.push(store.subscribe('result',()=>{status.textContent='';}));
 if(offline){
  button.disabled=true;button.title='보기 전용';status.textContent=` ${offline.case_id} · 보기 전용 · ${offline.interval_s} s`;
  const state=offline.state||{};
  for(const k of ['realView','openings','exploration','route','fuelSettings'])if(state[k])store.dispatch(k+'/set',state[k]);
  if(state.route){document.getElementById('routeHose').value=state.route.hose_m;document.getElementById('routeStair').value=state.route.stair_factor;}
  if(state.layers)for(const [id,visible] of Object.entries(state.layers))store.dispatch('layers/toggle',{id,visible});
  if(state.risk){store.dispatch('risk/history',{enabled:state.risk.history});store.dispatch('risk/threshold',state.risk.threshold);for(const [type,visible] of Object.entries(state.risk.show))store.dispatch('risk/set',{type,visible});}
  if(state.selection)store.dispatch('selection/set',state.selection);
  if(state.floor){viewer.setFloor(state.floor.floor_id??'all');store.dispatch('floor/set',state.floor);}
  if(state.playback){store.dispatch('playback/speed',{speed:state.playback.speed});store.dispatch('playback/seek',{t_s:state.playback.t_s});}
  if(state.camera){viewer.C.position.fromArray(state.camera.position);viewer.C.up.fromArray(state.camera.up);viewer.O.target.fromArray(state.camera.target);viewer.O.update();}
  const selector='#fuelSettings input,#fuelSettings select,#fuelSettings button,#exploreDuration,#exploreSamples,#exploreEngineLite,#exploreEngineCfast,#exploreOrigin,#exploreRun,#exploreOriginRun,#exploreMC,#exploreCalculateRun,#resultMCApplyWorst,#buildingClearFixed,#buildingDoors select,#cfbtFrozenRules button,#resultReplay,#exportHTML,#run,#mc';
  const lock=()=>{for(const node of document.querySelectorAll(selector)){if(!node.disabled)node.disabled=true;if(node.title!=='보기 전용')node.title='보기 전용';}};
  const guard=e=>{if(e.target.closest?.(selector)){e.preventDefault();e.stopImmediatePropagation();}};
  document.addEventListener('click',guard,true);document.addEventListener('change',guard,true);
  const observer=new MutationObserver(lock);observer.observe(document.body,{subtree:true,childList:true,attributes:true,attributeFilter:['disabled']});lock();
  cleanups.push(()=>{observer.disconnect();document.removeEventListener('click',guard,true);document.removeEventListener('change',guard,true);});
  document.documentElement.dataset.offlineReady='true';render();
 }
 return ()=>{for(const off of cleanups)off();root.remove();};
}
