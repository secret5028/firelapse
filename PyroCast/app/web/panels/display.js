import {createDisplayPolicy} from './display_policy.js';
import {roomFgiRollover} from '../adapters/fgi_rollover.js';
import {fixedOpeningsFor} from '../state/fixed_openings.js';
const backdraftTip='고온연기 축적·산소부족';
const phenomena=[['FO','FO','#ef4444'],['FGI','FGI','#a855f7'],['backdraft','BD','#facc15']];
export function createDisplayPanel({store,selectionLabel,onOrigin,isOriginAllowed}){
 const $=id=>document.getElementById(id),pane=$('shellPane-display'),cleanups=[],moves=[];
 const move=(node,parent)=>{const marker=document.createComment('display restore');node.before(marker);moves.push(()=>marker.replaceWith(node));parent.append(node);};
 const listen=(node,event,fn)=>{node.addEventListener(event,fn);cleanups.push(()=>node.removeEventListener(event,fn));};
 pane.innerHTML='<h3>보기</h3><div id="displayViewSettings"></div><h3>레이어</h3><div id="displayLayers"></div><h3>위험 유형</h3><div id="displayRisks"></div><h3>임계값</h3><div class="displaySettings"><label>테두리 <input id="displayRibbon" type="number" min="0" step="5" value="100"></label><label>주의 <input id="displayCaution" type="number" min="0" step="5" value="70"></label><span id="displayError" role="alert"></span></div><h3>연기</h3><div id="displaySmokeSettings" class="displaySettings"></div>';
 const bindings=[],policy=createDisplayPolicy(store);let plumeLegend=null,plumeNumbers=null;
 // The unchanged legacy renderer writes cfPlumeNumbers even while disabled.
 // Keep that hidden write target mounted; only attach the visible legend on demand.
 const plumeSink=document.createElement('div');plumeSink.hidden=true;pane.append(plumeSink);
 function syncPlumeLegend(){const found=$('cfPlumeLegend');if(found&&found!==plumeLegend){plumeNumbers?.remove();plumeLegend=found;plumeNumbers=found.querySelector('#cfPlumeNumbers');}if(!plumeLegend)return;const on=store.get('layers').plume&&store.get('realView').enabled;if(on){if(plumeNumbers)plumeLegend.append(plumeNumbers);if(!plumeLegend.isConnected)$('cfMeaning').after(plumeLegend);plumeLegend.hidden=false;}else{if(plumeNumbers)plumeSink.append(plumeNumbers);plumeLegend.remove();}}

 function toggle(host,id,label,color,read,write,existing=false,tip=''){
  const row=document.createElement('div');row.className='displayToggle';const text=document.createElement('label');text.htmlFor=id;text.innerHTML=`<i style="background:${color}"></i>`;text.append(label);row.append(text);
  if(tip){const info=document.createElement('span');info.className='displayInfo';info.tabIndex=0;info.textContent='ⓘ';info.title=tip;info.dataset.tip=tip;row.append(info);}
  let input;if(existing){input=$(id);const oldLabel=input.closest('label');move(input,row);oldLabel.remove();}else{input=document.createElement('input');input.type='checkbox';input.id=id;row.append(input);listen(input,'change',()=>write(input.checked));}
  input.setAttribute('role','switch');host.append(row);bindings.push(()=>input.checked=read());return input;
 }
 toggle($('displayViewSettings'),'displayReal','실감 보기','#62dcb0',()=>store.get('realView').enabled,enabled=>store.dispatch('realView/set',{enabled}));
 const buildingSlider=document.createElement('label');buildingSlider.className='gainControl';buildingSlider.title='0% 불투명 · 70% 기존 투시 · 100% 숨김. 문·창 강조와 코어 투시는 유지합니다.';
 buildingSlider.innerHTML='건물 투명도 <input id="displayBuildingTransparency" aria-label="건물 투명도" type="range" min="0" max="100" step="1" value="70"><output for="displayBuildingTransparency">70%</output>';
 $('displayViewSettings').append(buildingSlider);
 listen($('displayBuildingTransparency'),'input',()=>store.dispatch('realView/set',{buildingTransparency:$('displayBuildingTransparency').valueAsNumber/100}));
 for(const [id,label,color,layer] of [['displayBuilding','건물','#aab7c0','building'],['displaySelection','선택 실','#ffffff','selection'],['liteSmoke','연기','#9ca3af','smoke'],['displayFlame','화염','#ffa824','flame'],['litePlumes','상승 플룸·천장 가스','#b38ae6','plume'],['displayRisk','위험 테두리','#ef4444','risk']])toggle($('displayLayers'),id,label,color,()=>store.get('layers')[layer],visible=>store.dispatch('layers/toggle',{id:layer,visible}),id.startsWith('lite'),'저장된 결과의 표시만 전환합니다.');
 for(const [id,label,color,key] of [['liteDoors','실내 문 위치','#e6bd68','interior'],['liteExterior','외부 창','#62dcb0','exterior']])toggle($('displayLayers'),id,label,color,()=>store.get('openings')[key],null,true,'문틀·창 위치 표시이며 시뮬레이션 개폐 조건은 바뀌지 않습니다.');
 toggle($('displayLayers'),'displayRoomNames','도면 방 이름','#e8f2f8',()=>store.get('layers').roomNames,visible=>store.dispatch('layers/toggle',{id:'roomNames',visible}),false,'원본 CAD에 기록된 실 이름을 표시합니다. 이름이 없는 실은 임의로 만들지 않습니다.');
 toggle($('displayLayers'),'liteCores','계단·승강기 투시','#2563eb',()=>store.get('layers').core,null,true,'전체 보기에서는 전층, 층 선택 시 해당 층의 계단·승강기를 표시합니다.');
 toggle($('displayLayers'),'displayFixedOpenings','급기 상태 보기','#62dcb0',()=>store.get('openings').fixed,fixed=>store.dispatch('openings/set',{fixed}),false,'확정 입력이 있으면 다음 계산의 상태를, 없으면 저장된 재생 사례의 입력 상태를 표시합니다. 두 상태는 다를 수 있습니다. 사각형은 열림, ×는 닫힘(누설 포함). 외부 창은 기존 강조 필터와 카메라 방향을 따릅니다.');
 for(const [key,id,label] of [['cellOutline','displayCellOutline','셀 점선'],['floorTint','displayFloorTint','바닥 틴트'],['smokeInterface','displaySmokeInterface','연기 경계면'],['boundaryDots','displayBoundaryDots','경계 ±30 ℃ 점선']])toggle($('displayLayers'),id,label,'#9ca3af',()=>store.get('displayDetails')[key],visible=>store.dispatch('displayDetails/set',{[key]:visible}));
 toggle($('displayLayers'),'liteFuel','연료 기호','#c8b794',()=>store.get('realView').fuelMarkers,null,true);
 toggle($('displayLayers'),'displayRoute','진입 경로','#38bdf8',()=>store.get('layers').route,visible=>store.dispatch('layers/toggle',{id:'route',visible}));
 toggle($('displayLayers'),'displayVehicle','경로 차량','#d33',()=>store.get('route').vehicle_visible,vehicle_visible=>store.dispatch('route/set',{vehicle_visible}));
 for(const [key,label,color] of [...phenomena,['smoke','주의 구간','#9ca3af']])toggle($('displayRisks'),'displayType-'+key,label,color,()=>store.get('risk').show[key],visible=>store.dispatch('risk/set',{type:key,visible}),false,key==='backdraft'?backdraftTip:'');
 toggle($('displayRisks'),'displayHistory','이력 보기','#dce8ef',()=>store.get('risk').history,enabled=>store.dispatch('risk/history',{enabled}),false,'전 구간 최대값입니다. 점선은 언젠가 도달, 실선은 지금 도달한 현상입니다.');
 const opacity=$('liteOpacity');opacity.innerHTML='<option value="1">100%</option><option value="0.7">70% · 기본</option><option value="0.4">40%</option><option value="0.15">15%</option>';
 const opacityLabel=$('liteOpacity').closest('label');move(opacityLabel,$('displaySmokeSettings'));
 const oldTemperature=$('liteHeatSmoke').closest('label');oldTemperature.remove();
 const pattern=document.createElement('label');pattern.innerHTML='온도 무늬 <select id="displayTemperature"><option value="current">현재</option><option value="weak" selected>약하게</option><option value="off">끔</option></select><span class="displayInfo" tabindex="0" title="계산된 온도 그대로 무늬를 표시하거나 끕니다. 온도 입력은 변경하지 않습니다.">ⓘ</span>';$('displaySmokeSettings').append(pattern);
 listen($('displayTemperature'),'change',()=>store.dispatch('realView/set',{temperaturePattern:$('displayTemperature').value}));
 for(const [key,id,label,option,text] of [['smokeMode','displaySmokeMode','연기 표현','soot','그을음·온도'],['flameStyle','displayFlameStyle','화염 표현','four_stage','4단계']]){
  const row=document.createElement('label');row.innerHTML=`${label} <select id="${id}"><option value="current">현재</option><option value="${option}">${text}</option></select>`;$('displaySmokeSettings').append(row);
  listen($(id),'change',()=>store.dispatch('realView/set',{[key]:$(id).value}));
 }
 const gains=[];
 for(const [key,label,min,max] of [['smokeGain','연기 농도',30,150],['flameGain','화염 밝기',50,200]]){
  for(const [host,prefix] of [[$('displaySmokeSettings'),'display']]){
   const row=document.createElement('label');row.className='gainControl';row.htmlFor=prefix+key;row.append(label);
   const input=document.createElement('input');input.type='range';input.id=prefix+key;input.min=min;input.max=max;input.step=1;input.value=100;input.setAttribute('aria-label',label);row.append(input);
   const output=document.createElement('output');output.htmlFor=input.id;row.append(output);host.append(row);gains.push({key,input,output});
   listen(input,'input',()=>store.dispatch('realView/set',{[key]:input.valueAsNumber/100}));
  }
 }
 for(const id of ['displayRibbon','displayCaution'])listen($(id),'change',()=>{try{store.dispatch('risk/threshold',{ribbon:$('displayRibbon').valueAsNumber,caution:$('displayCaution').valueAsNumber});$('displayError').textContent='';}catch(e){$('displayError').textContent='0 이상이며 주의 ≤ 테두리로 입력하세요.';sync();}});
 const legend=document.createElement('div');legend.id='displayLegend';$('v').append(legend);const meaning=$('cfMeaning');move(meaning,legend);meaning.hidden=false;
 const chips=[...phenomena.map(([k,n,c])=>[k,n,c]),['smoke','주의 70~99','#9ca3af'],['history','┄ 이력','#dce8ef'],['boundary','┄ 경계 ±30℃','#9ca3af'],['building','건물','#aab7c0'],['smokeLayer','연기','#9ca3af'],['flame','화염','#ffa824'],['selection','선택','#ffffff'],['route','경로','#38bdf8'],['windows','외부 창','#62dcb0'],['doors','실내 문','#e6bd68'],['core','코어','#2563eb'],['fuel','연료','#c8b794'],['cells','셀 점선','#9ca3af'],['tint','바닥','#9ca3af'],['interface','연기 경계','#e7f2fa']];
 meaning.innerHTML=chips.map(([key,name,color])=>`<span class="legendChip" id="legend-${key}"><i style="background:${color}"></i><span>${name}</span></span>`).join('');
 $('legend-backdraft').title=backdraftTip;
 const fixedLegend=document.createElement('span');fixedLegend.className='legendChip';fixedLegend.id='legend-fixedOpenings';fixedLegend.hidden=true;
 fixedLegend.title='확정된 다음 실행 입력 · 현재 재생 결과의 개폐 상태가 아닙니다. 닫힘에는 누설 면적이 남을 수 있습니다.';meaning.prepend(fixedLegend);
 for(const [i,name,color] of [[0,'① 초기','#c41f05'],[1,'② 성장','#ffae23'],[2,'③ 최성','#fffad9'],[3,'④ 산소 부족','#8c0800']]){
  const chip=document.createElement('span');chip.className='legendChip';chip.id='legend-stage'+i;chip.hidden=true;chip.innerHTML=`<i style="background:${color}"></i><span>${name}</span>`;meaning.append(chip);
 }
 const rolloverBadge=document.createElement('b');rolloverBadge.id='fgiRolloverBadge';rolloverBadge.hidden=true;rolloverBadge.style.color='#f97316';rolloverBadge.title='FGI 부속 상태 · 보라 리본의 주황 점. 독립 지수 아님.';$('legend-FGI').append(rolloverBadge);
 $('liteLegend').remove();
 const vehicleMarker=document.createElement('span');vehicleMarker.className='displayVehicleMarker';vehicleMarker.textContent='차량';vehicleMarker.title='경로 차량 위치 · 표시 기호';vehicleMarker.hidden=true;$('v').append(vehicleMarker);
 const view=document.createElement('div');view.id='displayView';view.setAttribute('role','group');view.setAttribute('aria-label','보기');view.append('보기 ');$('pyroShellHeader').append(view);move($('top'),view);move($('iso'),view);
 const toolbar=$('resetView').parentElement;move($('liteFocus'),toolbar);move($('liteFireFocus'),toolbar);$('resetView').textContent='⟲';$('resetView').title='시점 복원';$('liteFocus').textContent='실 확대';$('liteFireFocus').textContent='연소점';move($('resetView'),view);
 selectionLabel.replaceChildren();selectionLabel.classList.add('compactHUD');selectionLabel.innerHTML='<div class="hudTitle"><b id="hudRoom"></b><button id="hudHistory" type="button" aria-pressed="false">이력 보기</button></div><div class="hudPhenomenon"><span id="hudPill"></span></div><div class="hudValues">상층 <b id="hudT"></b></div><button id="hudOrigin" type="button" disabled>이 실을 화점으로</button>';
 listen($('hudOrigin'),'click',()=>onOrigin(store.get('selection').room_id));
 listen($('hudHistory'),'click',()=>store.dispatch('risk/history',{enabled:!store.get('risk').history}));
 const style=document.createElement('style');style.dataset.pyrocastDisplay='true';style.textContent=`
 #shellPane-display{padding:12px 16px;box-sizing:border-box}#shellPane-display h3{font-size:12px;color:#b8cbd8;margin:14px 0 8px;font-weight:500}
 .displayToggle{display:flex;align-items:center;gap:8px;border-bottom:1px solid #304c5e;padding:8px 0}.displayToggle label{flex:1;display:flex;align-items:center;gap:9px}.displayToggle i,.legendChip i{display:inline-block;flex-shrink:0;width:9px;height:9px;border-radius:2px}.displayToggle input{appearance:none;width:34px;height:20px;border-radius:999px;background:#496273;position:relative;cursor:pointer;margin:0;flex:none}.displayToggle input::after{content:'';position:absolute;top:2px;left:2px;width:16px;height:16px;border-radius:50%;background:#fff;transition:left .15s}.displayToggle input:checked{background:#2baed4}.displayToggle input:checked::after{left:16px}.displayToggle input:focus-visible{outline:2px solid #42c4e8;outline-offset:3px}
 .displayInfo{font-size:12px;color:#b6cedb;cursor:help}.displaySettings{padding:10px;border:1px solid #496273;border-radius:7px;display:grid;gap:9px}.displaySettings label{display:flex;justify-content:space-between;gap:10px;align-items:center}.displaySettings input{width:68px}.displaySettings input,.displaySettings select{background:#1d4158;color:#eef5fa;border:1px solid #6a8d9f;border-radius:4px;padding:5px}#displayError{color:#ffc1b0;font-size:11px}#displayError:empty{display:none}
 .displayVehicleMarker{position:absolute;z-index:6;transform:translate(-50%,-50%);background:#17384d;border:2px solid #38bdf8;border-radius:5px;padding:3px 6px;color:#fff;font-size:11px;pointer-events:none}.displayVehicleMarker[hidden]{display:none}
 #hudHistory{pointer-events:auto;background:#17384d;border:1px solid #577487;border-radius:12px;color:#eaf3f8;padding:3px 7px;cursor:pointer}#hudHistory[aria-pressed=true]{border-color:#42e8ff;color:#42e8ff}.hudPhenomenon{margin:5px 0}.viewHint[hidden]{display:none!important}
 #displayLegend{position:absolute;z-index:6;bottom:10px;left:12px;max-width:calc(100% - 24px);pointer-events:none}#displayLegend #cfMeaning{display:none}.legendChip{background:#142b3be8;border:1px solid #577487;border-radius:14px;padding:3px 7px;display:inline-flex;gap:5px;align-items:center;color:#eaf3f8;font-size:11px;flex-shrink:0;white-space:nowrap}
 .legendChip[hidden]{display:none}
 .gainControl{display:flex;align-items:center;gap:7px;white-space:nowrap}.gainControl+.gainControl{margin-top:5px}.gainControl input[type=range]{width:105px;min-width:40px;flex:1;padding:0;accent-color:#42c4e8}.gainControl output{width:36px;text-align:right;font-variant-numeric:tabular-nums}
 #displayLegend #cfPlumeLegend{margin:4px 0 0;padding:3px 6px!important;background:#142b3be8;border-radius:4px;font-size:10px;color:#d6e8f3}#displayLegend #cfPlumeLegend small,#displayLegend #cfPlumeNumbers{display:none}
 body.pyroShell #cameraButtons{display:none!important}
 body.pyroShell .viewHint{bottom:70px;right:12px;left:auto;font-size:10px}#displayView{display:flex;align-items:center;gap:5px;white-space:nowrap}.compactHUD{display:none!important;white-space:normal!important;max-width:calc(100% - 24px)}.hudTitle{display:flex;align-items:center;gap:8px}#hudOrigin{pointer-events:auto;margin-top:5px;background:#1d4158;color:#eaf3f8;border:1px solid #577487;border-radius:4px;padding:3px 6px;cursor:pointer}.hudValues{display:flex;gap:12px;margin-top:3px;font-size:12px}.hudValues b{font-variant-numeric:tabular-nums}#hudPill{padding:2px 8px;border-radius:12px;background:#1d4158;color:#eaf3f8;font-size:11px;white-space:nowrap}
 @media(max-width:860px){#displayView{font-size:11px}#displayView button{padding:4px}.hudValues{gap:8px}#displayLegend{bottom:6px;left:8px}.legendChip{font-size:10px;padding:2px 5px}}
 `;document.head.append(style);
 function sync(){bindings.forEach(f=>f());const r=store.get('risk'),l=store.get('layers'),d=store.get('displayDetails'),rv=store.get('realView'),o=store.get('openings'),t=r.threshold;
  const transparency=Math.round(rv.buildingTransparency*100);$('displayBuildingTransparency').value=transparency;buildingSlider.querySelector('output').textContent=transparency+'%';
   const fixed=fixedOpeningsFor(store.get('building'),store.get('buildingReview'));
   $('displayFixedOpenings').disabled=!fixed;
   const stateLabel=fixed?.basis==='saved_case_input'?'재생 사례 급기':'확정 급기 · 다음 실행';
   $('displayFixedOpenings').title=fixed?`${stateLabel} · 열림 ${Object.values(fixed.states).filter(s=>s.open).length} / 닫힘 ${Object.values(fixed.states).filter(s=>!s.open).length} · 문 황금색·창 초록색 · 사각=열림, 회색 ×=닫힘`:'저장된 개폐 상태 없음';
   fixedLegend.hidden=!(l.openings&&o.fixed&&fixed);
   fixedLegend.replaceChildren();if(fixed){fixedLegend.append(`${stateLabel} · ${fixed.sample_id||fixed.case_id||'사용자 지정'} `);for(const [text,color] of [['□ 문','#e6bd68'],['□ 창','#62dcb0'],['× 닫힘','#c0cbd3']]){const span=document.createElement('span');span.textContent=text;span.style.color=color;fixedLegend.append(span);}}
  const visible={...Object.fromEntries(phenomena.map(([k])=>[k,l.risk&&r.show[k]])),smoke:l.risk&&r.show.smoke,history:l.risk&&r.history,boundary:l.risk&&d.boundaryDots,building:l.building,smokeLayer:rv.enabled&&l.smoke,flame:rv.enabled&&l.flame,selection:l.selection,route:l.route,windows:l.openings&&o.exterior,doors:l.openings&&o.interior,core:l.core,fuel:rv.fuelMarkers,cells:l.risk&&d.cellOutline,tint:l.risk&&d.floorTint,interface:l.risk&&d.smokeInterface};
  for(const [key,on] of Object.entries(visible))$('legend-'+key).hidden=!on;
  $('legend-smokeLayer').lastElementChild.textContent=rv.smokeMode==='soot'?'검정=그을음 · 빨강=600 ℃↑':'연기';
  $('legend-smokeLayer').title=rv.smokeMode==='soot'?'색상은 표시 규칙입니다. 450~800 ℃에서 암적→빨강 발광. 실제 빛의 방출 계산 아님.':'';
  for(let i=0;i<4;i++)$('legend-stage'+i).hidden=!(visible.flame&&rv.flameStyle==='four_stage');
  $('displaySmokeMode').value=rv.smokeMode;$('displayFlameStyle').value=rv.flameStyle;
  $('legend-smoke').lastElementChild.textContent=`주의 ${t.caution}~${t.ribbon-1}`;$('hudHistory').setAttribute('aria-pressed',String(r.history));
  $('displayRibbon').value=t.ribbon;$('displayCaution').value=t.caution;$('displayTemperature').value=rv.temperaturePattern;$('liteOpacity').value=rv.smokeOpacity;syncPlumeLegend();
  for(const {key,input,output} of gains){const value=Math.round(rv[key]*100);input.value=value;output.textContent=value+'%';input.setAttribute('aria-valuetext',value+'%');}
 }
 for(const slice of ['layers','openings','realView','risk','route','displayDetails','floor','building','buildingReview'])cleanups.push(store.subscribe(slice,sync));sync();
 function hud({building,result,series,index,selection}){
  const rooms=building.floors.flatMap(f=>f.rooms),room=rooms.find(r=>r.room_id===selection.room_id),cell=selection.cell_id??(room?.cells.length===1?room.cells[0].cell_id:null),s=cell?series.cells[cell]:null;
  const allowed=!!isOriginAllowed(room?.room_id);$('hudOrigin').disabled=!allowed;$('hudOrigin').title=allowed?'선택한 원래 방을 탐색 화점으로 지정합니다':'화점 지정 가능한 실을 선택하세요';
  $('hudRoom').textContent=$('liteRoom').selectedOptions[0]?.textContent||'실 선택';
  const scores=phenomena.map(([key,name,color])=>({key,name,color,value:cell?result.index_by_cell[cell]?.[key]?.[index]:null})).filter(s=>Number.isFinite(s.value)).sort((a,b)=>b.value-a.value),top=scores[0];
  $('hudPill').textContent=top?`${top.name} ${Math.round(top.value)}`:'미평가';$('hudPill').style.color=top?.color||'';
  const risk=store.get('risk'),floor=store.get('floor').floor_id,ids=building.floors.filter(f=>floor===null||f.floor_id===floor).flatMap(f=>f.rooms.flatMap(r=>r.cells));
  const rolling=roomFgiRollover(result,ids,index,risk.threshold.ribbon,risk.history)===true,now=roomFgiRollover(result,ids,index,risk.threshold.ribbon,false)===true;
  rolloverBadge.hidden=!rolling;rolloverBadge.textContent=now?' · 롤오버 조건 충족':' · 롤오버 조건 충족 이력';
  if(top?.key==='FGI'&&roomFgiRollover(result,cell?[cell]:room?.cells||[],index,risk.threshold.ribbon,false)===true)$('hudPill').textContent+=' · 롤오버 조건 충족';
  const format=(n,suffix,digits)=>Number.isFinite(n)?n.toFixed(digits)+suffix:'—';$('hudT').textContent=format(s?.T_upper_C[index],' ℃',0);
  selectionLabel.title=cell?'선택 셀 · 현재 시각':room?.cells.length>1?'방 평균 없음 · 셀을 선택하세요.':'';
 }
 return {hud,applyScene(context){policy.apply(context);syncPlumeLegend();
  // Buildings without a reference vehicle mesh still show the existing route origin.
  const {route,camera}=context,point=route.result?.vehicle,floor=store.get('floor').floor_id;
  vehicleMarker.hidden=!!route.vehicleSource||!point||!store.get('layers').route||!store.get('route').vehicle_visible||(floor!==null&&floor!=='1F');
  if(!vehicleMarker.hidden){const p=new route.THREE.Vector3(...point).project(camera);vehicleMarker.hidden=p.z< -1||p.z>1;vehicleMarker.style.left=(p.x+1)*$('v').clientWidth/2+'px';vehicleMarker.style.top=(1-p.y)*$('v').clientHeight/2+'px';}
 },dispose(){policy.dispose();vehicleMarker.remove();plumeLegend?.remove();for(const off of cleanups.reverse())off();for(const undo of moves.reverse())undo();style.remove();legend.remove();view.remove();pane.replaceChildren();}};
}
