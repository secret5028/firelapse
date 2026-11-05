import {fuelSettingsWithDraft,resolveFuel} from '../state/fuel_settings.js';
// Editing changes future inputs only; no simulation is started here.
export function createFuelSettingsPanel({store,onSaved,available=true}){
 const root=document.createElement('section');root.id='fuelSettings';root.className='exploreCard workflowStep';root.hidden=true;document.getElementById('buildingContent').prepend(root);
 root.innerHTML='<h3 id="fuelFloorTitle"></h3><label>종류 <select id="fuelFloorType" aria-label="층 전체 가연물 종류"></select></label><label class="fuelQuantity">양 <input id="fuelFloorAmount" type="range" aria-label="층 전체 가연물 양"><output id="fuelFloorValue"></output></label><section id="fuelSelectedRoom" hidden><h3 id="fuelRoomName"></h3><small id="fuelRoomScope"></small><label>종류 <select id="fuelRoomType" aria-label="선택 실 가연물 종류"></select></label><label class="fuelQuantity">양 <input id="fuelRoomAmount" type="range" aria-label="선택 실 가연물 양"><output id="fuelRoomValue"></output></label><button id="fuelInherit">층 설정 따르기</button></section><button id="fuelSave" disabled>변경 저장</button><button id="fuelReset" disabled>취소</button><p id="fuelDefaultsStatus"></p><button id="fuelAI" hidden>AI 초기 배치</button><p id="fuelSettingsStatus" role="status"></p>';
 const $=id=>root.querySelector('#'+id),abort=new AbortController();let disposed=false,current=null,draft={},floor=store.get('floor')?.floor_id||null,selected=null,saving=false,autoAttempted=false;
 const style=document.createElement('style');style.textContent='#fuelSettings{line-height:1.5}#fuelSettings label{display:block;margin:8px 0}#fuelSettings select{max-width:100%;width:100%}.fuelQuantity input{width:100%;accent-color:#42c4e8}.fuelQuantity output,#fuelSettings small{display:block;color:#b8cbd8;font-size:11px}#fuelSelectedRoom{border-top:1px solid #496273;margin-top:15px;padding-top:8px}#fuelSettings button{margin:8px 5px 0 0}#fuelDefaultsStatus{color:#b8cbd8;font-size:11px}';document.head.append(style);
 const dirty=()=>Object.values(draft).some(x=>Object.keys(x).length);
 const room=()=>current?.rooms.find(r=>r.id===selected&&r.editable);
 function update(message){store.dispatch('fuelSettings/set',{data:current,draft:structuredClone(draft),saving,message:message??store.get('fuelSettings').message});}
 function options(el,value){el.replaceChildren(new Option('AI 기본 배치', ''));for(const [id,c] of Object.entries(current.classes))el.add(new Option(c.label,id));el.value=value||'';}
 function configure(el){el.min=current.range.min*100;el.max=current.range.max*100;el.step=current.range.step*100;}
 function render(){if(!current)return;const saved=fuelSettingsWithDraft(current,draft),f=saved.floors[floor]||{multiplier:1},rows=current.rooms.filter(r=>r.editable&&r.floor===floor);
  $('fuelFloorTitle').textContent=floor?`2단계 · 가연물 설정 (${floor})`:'2단계 · 가연물 설정';options($('fuelFloorType'),f.usage_class);configure($('fuelFloorAmount'));$('fuelFloorAmount').value=f.multiplier*100;$('fuelFloorValue').textContent=`${Math.round(f.multiplier*100)}% · 개별 설정 실 제외`;
  for(const id of ['fuelFloorType','fuelFloorAmount'])$(id).disabled=saving||!rows.length;
  const r=room();$('fuelSelectedRoom').hidden=!r;if(r){const value=resolveFuel(current,draft,r);$('fuelRoomName').textContent=`${r.id.replace(/^CAD_/,'').replaceAll('_',' ')} · ${r.name}`;
   $('fuelRoomScope').textContent=value.scope==='room'?'개별 설정 · 층 변경 시 유지':'층 설정 따름';$('fuelRoomScope').title=r.basis;
   options($('fuelRoomType'),value.pending?null:value.usage_class);configure($('fuelRoomAmount'));$('fuelRoomAmount').value=value.multiplier*100;$('fuelRoomValue').textContent=value.pending?'AI 초기 배치 대기':`${Math.round(value.multiplier*100)}% · ${Math.round(value.load)} MJ/m² · ${Math.round(value.hrrpua)} kW/m²`;
   $('fuelRoomType').disabled=saving;$('fuelRoomAmount').disabled=saving||value.pending;$('fuelInherit').disabled=saving||value.scope!=='room';
  }
  $('fuelSave').disabled=saving||!dirty();$('fuelReset').disabled=saving||!dirty();$('fuelDefaultsStatus').textContent=current.ai_pending?.length&&!current.ai_available?'AI 연결 대기 · 현재는 용도별 기준량을 임시 표시':current.default_status||'';
  $('fuelAI').hidden=!current.ai_pending?.length;$('fuelAI').disabled=saving||dirty()||!current.ai_available;$('fuelAI').title=current.ai_available?'미설정 실만 AI 배치':'config/ai.json 및 키 환경변수 설정 필요';$('fuelSettingsStatus').textContent=store.get('fuelSettings').message;
 }
 function changed(){store.dispatch('realView/set',{fuelMarkers:true});update('미저장 변경 · 기존 결과 유지');render();}
 function editFloor(){draft.floors={...draft.floors,[floor]:{usage_class:$('fuelFloorType').value||null,multiplier:Number($('fuelFloorAmount').value)/100}};changed();}
 function editRoom(){const r=room();if(!r)return;draft.rooms={...draft.rooms,[r.id]:{usage_class:$('fuelRoomType').value||null,multiplier:Number($('fuelRoomAmount').value)/100}};changed();}
 $('fuelFloorType').onchange=editFloor;$('fuelFloorAmount').oninput=editFloor;$('fuelRoomType').onchange=editRoom;$('fuelRoomAmount').oninput=editRoom;
 $('fuelInherit').onclick=()=>{draft.rooms={...draft.rooms,[selected]:null};changed();};$('fuelReset').onclick=()=>{draft={};update('변경 취소');render();};
 async function post(body,message){saving=true;update(message);render();try{
  const response=await fetch('/cfbt/lite/fuel-settings',{method:'POST',signal:abort.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({building_sha256:current.building_sha256,revision:current.revision,...body})});const value=await response.json();if(!response.ok)throw Error(value.error||'저장 실패');if(disposed)return;current=value;draft={};update('저장 완료 · 재계산 필요');if(body.initialize_defaults)store.dispatch('realView/set',{fuelMarkers:true});await onSaved?.();
 }catch(e){if(!disposed)update(e.message);}finally{if(!disposed){saving=false;update();render();}}}
 $('fuelSave').onclick=()=>post({floors:Object.entries(draft.floors||{}).map(([id,r])=>({id,...r})),rooms:Object.entries(draft.rooms||{}).map(([id,r])=>r?{id,...r}:{id,inherit:true})},'저장 중…');
 $('fuelAI').onclick=()=>post({initialize_defaults:true},'AI 초기 배치 중…');
 async function refresh(){if(!available||window.__PYROCAST_OFFLINE__)return;try{const response=await fetch('/cfbt/lite/fuel-settings',{signal:abort.signal});if(!response.ok)return;const value=await response.json();if(disposed||!value.editable)return;current=value;draft={};floor=store.get('floor')?.floor_id;root.hidden=false;update('');render();for(const id of ['buildingFuelSection','buildingSettingsEmpty']){const el=document.getElementById(id);if(el)el.hidden=true;}
  if(!autoAttempted&&value.ai_available&&value.ai_pending?.length){autoAttempted=true;await post({initialize_defaults:true},'AI 초기 배치 중…');}
 }catch(e){if(!disposed)update('가연물 설정 읽기 실패');}}
 const offFloor=store.subscribe('floor',value=>{floor=value.floor_id;if(room()?.floor!==floor)selected=null;render();});
 const offSelection=store.subscribe('selection',value=>{if(!['click','touch'].includes(value.source)||!current)return;selected=value.room_id;if(!room()){selected=null;render();return;}render();});
 refresh();return {refresh,dispose(){offFloor();offSelection();disposed=true;abort.abort();root.remove();style.remove();}};
}
