// User input only. The saved playback remains unchanged until an explicit run.
export function createFuelSettingsPanel({store,onSaved,onFloor,available=true}){
 const root=document.createElement('section');root.id='fuelSettings';root.hidden=true;document.getElementById('buildingContent').prepend(root);
 root.innerHTML='<h3>가연물 양</h3><label>층 <select id="fuelFloor" aria-label="가연물 설정 층"></select></label><label class="fuelQuantity">층 전체 <input id="fuelFloorAmount" type="range" aria-label="층 전체 가연물 양"><output id="fuelFloorValue"></output></label><div id="fuelRoomAmounts"></div><button id="fuelSave" disabled>변경 저장</button><button id="fuelReset" disabled>취소</button><p id="fuelSettingsStatus" role="status"></p><small title="기준량은 기존 승인값 또는 fire_load_table.json 용도별 값입니다. 10~300%는 입력 조절 범위입니다. 기호 크기는 양의 표시이며 실물 크기가 아닙니다.">기준량 대비 배율 · 3D는 양 표시용</small>';
 const $=id=>root.querySelector('#'+id),abort=new AbortController();let disposed=false,current=null,draft={},floor=store.get('floor')?.floor_id||'',saving=false;
 const style=document.createElement('style');style.textContent='#fuelSettings{line-height:1.5}#fuelSettings label{display:block;margin:8px 0}#fuelSettings select{max-width:100%}.fuelQuantity input{width:100%;accent-color:#42c4e8}.fuelQuantity output{display:block;color:#b8cbd8;font-size:11px}.fuelRoomAmount{border-top:1px solid #496273;padding-top:7px}.fuelRoomName{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}#fuelSettings button{margin:8px 5px 0 0}#fuelSettings small{color:#b8cbd8}';document.head.append(style);
 function updateState(message){store.dispatch('fuelSettings/set',{data:current,draft:{...draft},saving,message:message??store.get('fuelSettings').message});}
 const amount=r=>draft[r.id]??r.multiplier;
 const description=r=>`${Math.round(amount(r)*100)}% · ${Math.round(r.base_load*amount(r))} MJ/m² · 총 ${Math.round(r.base_load*amount(r)*r.area).toLocaleString()} MJ`;
 function changed(id,value){const r=current.rooms.find(r=>r.id===id);if(value===r.multiplier)delete draft[id];else draft[id]=value;store.dispatch('realView/set',{fuelMarkers:true});updateState('미저장 변경 · 기존 결과 유지');sync();}
 function configure(input){input.min=current.range.min*100;input.max=current.range.max*100;input.step=current.range.step*100;}
 function sync(){
  for(const row of root.querySelectorAll('.fuelRoomAmount')){const r=current.rooms.find(r=>r.id===row.dataset.room);row.querySelector('input').value=amount(r)*100;row.querySelector('output').textContent=description(r);row.querySelector('input').disabled=saving;}
  const rows=current.rooms.filter(r=>r.floor===floor&&r.editable),values=new Set(rows.map(amount));$('fuelFloorAmount').disabled=saving||!rows.length;$('fuelFloorAmount').value=(values.size===1?[...values][0]:1)*100;$('fuelFloorValue').textContent=values.size===1?`${Math.round([...values][0]*100)}%`:'실별 설정';
  $('fuelSave').disabled=saving||!Object.keys(draft).length;$('fuelReset').disabled=saving||!Object.keys(draft).length;$('fuelFloor').disabled=saving;$('fuelSettingsStatus').textContent=store.get('fuelSettings').message;
 }
 function render(){
  $('fuelFloor').replaceChildren();for(const f of [...new Set(current.rooms.filter(r=>r.editable).map(r=>r.floor))])$('fuelFloor').add(new Option(f,f));if(![...$('fuelFloor').options].some(o=>o.value===floor))floor=$('fuelFloor').options[0]?.value||'';$('fuelFloor').value=floor;configure($('fuelFloorAmount'));
  $('fuelRoomAmounts').replaceChildren();for(const r of current.rooms.filter(r=>r.floor===floor&&r.editable)){
   const label=document.createElement('label');label.className='fuelQuantity fuelRoomAmount';label.dataset.room=r.id;const title=document.createElement('span');title.className='fuelRoomName';title.title=r.name;title.textContent=`${r.id.replace(/^CAD_/,'').replaceAll('_',' ')} · ${r.name} (${r.usage})`;label.append(title);
   const input=document.createElement('input');input.type='range';input.setAttribute('aria-label',r.id+' 가연물 양');configure(input);const output=document.createElement('output');label.append(input,output);input.oninput=()=>changed(r.id,Number(input.value)/100);$('fuelRoomAmounts').append(label);
  }sync();
 }
 $('fuelFloor').onchange=()=>{floor=$('fuelFloor').value;onFloor?.(floor);render();};$('fuelFloorAmount').oninput=()=>{for(const r of current.rooms.filter(r=>r.floor===floor&&r.editable)){const value=Number($('fuelFloorAmount').value)/100;if(value===r.multiplier)delete draft[r.id];else draft[r.id]=value;}store.dispatch('realView/set',{fuelMarkers:true});updateState('미저장 변경 · 기존 결과 유지');sync();};
 $('fuelReset').onclick=()=>{draft={};updateState('변경 취소');sync();};
 $('fuelSave').onclick=async()=>{saving=true;updateState('저장 중…');sync();try{
  const response=await fetch('/cfbt/lite/fuel-settings',{method:'POST',signal:abort.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({building_sha256:current.building_sha256,revision:current.revision,rooms:Object.entries(draft).map(([id,multiplier])=>({id,multiplier}))})});const value=await response.json();if(!response.ok)throw Error(value.error||'저장 실패');if(disposed)return;current=value;draft={};updateState('저장 완료 · 재계산 필요');await onSaved();
 }catch(e){if(!disposed)updateState(e.message);}finally{if(!disposed){saving=false;updateState();render();}}};
 async function refresh(){if(!available||window.__PYROCAST_OFFLINE__)return;try{const response=await fetch('/cfbt/lite/fuel-settings',{signal:abort.signal});if(!response.ok)return;const value=await response.json();if(disposed||!value.editable)return;current=value;draft={};floor=store.get('floor')?.floor_id||floor;root.hidden=false;updateState(Object.keys(value.quantity_settings?.rooms||{}).length?'저장된 가연물 설정 · 기존 결과는 별도':'');render();document.getElementById('buildingFuelSection').hidden=true;document.getElementById('buildingSettingsEmpty').hidden=true;}catch(e){if(!disposed)updateState('가연물 설정 읽기 실패');}}
 const off=store.subscribe('floor',value=>{if(current&&value.floor_id&&current.rooms.some(r=>r.editable&&r.floor===value.floor_id)){floor=value.floor_id;render();}});
 refresh();return {refresh,dispose(){off();disposed=true;abort.abort();root.remove();style.remove();}};
}
