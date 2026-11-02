const phenomena=[['FO','FO','#ef4444'],['FGI','FGI','#a855f7'],['backdraft','백드래프트','#facc15'],['rollover','롤오버','#f97316']];
export function createDisplayPanel({store,selectionLabel,onOrigin,isOriginAllowed}){
 const $=id=>document.getElementById(id),pane=$('shellPane-display'),cleanups=[],moves=[];
 const move=(node,parent)=>{const marker=document.createComment('display restore');node.before(marker);moves.push(()=>marker.replaceWith(node));parent.append(node);};
 const listen=(node,event,fn)=>{node.addEventListener(event,fn);cleanups.push(()=>node.removeEventListener(event,fn));};
 pane.innerHTML='<h3>보기</h3><div id="displayViewSettings"></div><h3>레이어</h3><div id="displayLayers"></div><h3>위험 유형</h3><div id="displayRisks"></div><h3>임계값</h3><div class="displaySettings"><label>테두리 <input id="displayRibbon" type="number" min="0" step="5" value="100"></label><label>주의 <input id="displayCaution" type="number" min="0" step="5" value="70"></label><span id="displayError" role="alert"></span></div><h3>연기</h3><div id="displaySmokeSettings" class="displaySettings"></div>';
 const bindings=[];
 function toggle(host,id,label,color,read,write,existing=false,tip=''){
  const row=document.createElement('div');row.className='displayToggle';const text=document.createElement('label');text.htmlFor=id;text.innerHTML=`<i style="background:${color}"></i>`;text.append(label);row.append(text);
  if(tip){const info=document.createElement('span');info.className='displayInfo';info.tabIndex=0;info.textContent='ⓘ';info.title=tip;info.dataset.tip=tip;row.append(info);}
  let input;if(existing){input=$(id);const oldLabel=input.closest('label');move(input,row);oldLabel.remove();}else{input=document.createElement('input');input.type='checkbox';input.id=id;row.append(input);listen(input,'change',()=>write(input.checked));}
  input.setAttribute('role','switch');host.append(row);bindings.push(()=>input.checked=read());return input;
 }
 toggle($('displayViewSettings'),'displayReal','실감 보기','#62dcb0',()=>store.get('realView').enabled,enabled=>store.dispatch('realView/set',{enabled}));
 for(const [id,label,color,layer] of [['liteSmoke','연기','#9ca3af','smoke'],['displayFlame','화염','#ffa824','flame'],['litePlumes','상승 플룸·천장 가스','#b38ae6','plume'],['displayRisk','위험 테두리','#ef4444','risk']])toggle($('displayLayers'),id,label,color,()=>store.get('layers')[layer],visible=>store.dispatch('layers/toggle',{id:layer,visible}),id.startsWith('lite'),'저장된 결과의 표시만 전환합니다.');
 for(const [id,label,color,key] of [['liteDoors','실내 문 위치','#e6bd68','interior'],['liteExterior','외부 창','#62dcb0','exterior']])toggle($('displayLayers'),id,label,color,()=>store.get('openings')[key],null,true,'문틀·창 위치 표시이며 시뮬레이션 개폐 조건은 바뀌지 않습니다.');
 toggle($('displayLayers'),'liteCores','계단·승강기 투시','#ffc342',()=>store.get('layers').core,null,true,'전체 건물 보기에서만 표시합니다.');
 toggle($('displayLayers'),'liteFuel','연료 기호','#c8b794',()=>store.get('realView').fuelMarkers,null,true);
 toggle($('displayLayers'),'displayOperations','작전 기호 (차량·인원)','#d33',()=>store.get('layers').operations,visible=>store.dispatch('layers/toggle',{id:'operations',visible}),false,'수동 작전·크기 기준 기호입니다. 계산 결과와 별개입니다.');
 for(const [key,label,color] of [...phenomena,['smoke','주의 구간','#9ca3af']])toggle($('displayRisks'),'displayType-'+key,label,color,()=>store.get('risk').show[key],visible=>store.dispatch('risk/set',{type:key,visible}));
 toggle($('displayRisks'),'displayHistory','이력 표시','#dce8ef',()=>store.get('risk').history,enabled=>store.dispatch('risk/history',{enabled}),false,'현재 시각까지 저장된 지수의 최대값입니다. 이력만 해당하는 테두리는 점선입니다.');
 const opacityLabel=$('liteOpacity').closest('label');move(opacityLabel,$('displaySmokeSettings'));
 const oldTemperature=$('liteHeatSmoke').closest('label');oldTemperature.remove();
 const pattern=document.createElement('label');pattern.innerHTML='온도 무늬 <select id="displayTemperature"><option value="current" selected>현재</option><option value="weak">약하게</option><option value="off">끔</option></select><span class="displayInfo" tabindex="0" title="계산된 온도 그대로 무늬를 표시하거나 끕니다. 온도 입력은 변경하지 않습니다.">ⓘ</span>';$('displaySmokeSettings').append(pattern);
 const color=document.createElement('label');color.innerHTML='연기 색 <select id="displaySmokeColor"><option value="current" selected>현재</option><option value="neutral">중성</option></select>';$('displaySmokeSettings').append(color);
 const flame=document.createElement('label');flame.innerHTML='불꽃 <select id="displayFlameStyle"><option value="growth" selected>성장 비율(현재)</option><option value="hrr">발열량 기준</option></select>';$('displaySmokeSettings').append(flame);
 listen($('displayFlameStyle'),'change',()=>store.dispatch('realView/set',{flameDisplay:$('displayFlameStyle').value}));
 listen($('displaySmokeColor'),'change',()=>store.dispatch('realView/set',{smokeColor:$('displaySmokeColor').value}));
 listen($('displayTemperature'),'change',()=>store.dispatch('realView/set',{temperaturePattern:$('displayTemperature').value}));
 for(const id of ['displayRibbon','displayCaution'])listen($(id),'change',()=>{try{store.dispatch('risk/threshold',{ribbon:$('displayRibbon').valueAsNumber,caution:$('displayCaution').valueAsNumber});$('displayError').textContent='';}catch(e){$('displayError').textContent='0 이상이며 주의 ≤ 테두리로 입력하세요.';sync();}});
 const legend=document.createElement('div');legend.id='displayLegend';$('v').append(legend);const meaning=$('cfMeaning');move(meaning,legend);meaning.hidden=false;
 meaning.innerHTML=phenomena.map(([k,n,c])=>`<span class="legendChip"><i style="background:${c}"></i>${n}</span>`).join('')+'<span class="legendChip"><i style="background:#9ca3af"></i><span id="legendCaution"></span></span><span class="legendChip" id="legendHistory">┄ 이력(점선)</span><span class="legendChip">┄ 경계 ±30℃</span><span class="legendChip"><i style="background:#42e8ff"></i>선택</span>';
 $('liteLegend').remove();
 const view=document.createElement('div');view.id='displayView';view.setAttribute('role','group');view.setAttribute('aria-label','보기');view.append('보기 ');$('pyroShellHeader').append(view);move($('top'),view);move($('iso'),view);
 const toolbar=$('resetView').parentElement;move($('liteFocus'),toolbar);move($('liteFireFocus'),toolbar);$('resetView').textContent='⟲';$('resetView').title='시점 복원';$('liteFocus').textContent='실 확대';$('liteFireFocus').textContent='연소점';
 selectionLabel.replaceChildren();selectionLabel.classList.add('compactHUD');selectionLabel.innerHTML='<div class="hudTitle"><b id="hudRoom"></b><span id="hudPill"></span></div><button id="hudOrigin" type="button" disabled>이 실을 화점으로</button><div class="hudValues"><span>상층 <b id="hudT"></b></span><span>O₂ <b id="hudO"></b></span><span>연기층 <b id="hudH"></b></span></div>';
 listen($('hudOrigin'),'click',()=>onOrigin(store.get('selection').room_id));
 const style=document.createElement('style');style.dataset.pyrocastDisplay='true';style.textContent=`
 #shellPane-display{padding:12px 16px;box-sizing:border-box}#shellPane-display h3{font-size:12px;color:#b8cbd8;margin:14px 0 8px;font-weight:500}
 .displayToggle{display:flex;align-items:center;gap:8px;border-bottom:1px solid #304c5e;padding:8px 0}.displayToggle label{flex:1;display:flex;align-items:center;gap:9px}.displayToggle i,.legendChip i{display:inline-block;width:9px;height:9px;border-radius:2px}.displayToggle input{appearance:none;width:34px;height:20px;border-radius:999px;background:#496273;position:relative;cursor:pointer;margin:0;flex:none}.displayToggle input::after{content:'';position:absolute;top:2px;left:2px;width:16px;height:16px;border-radius:50%;background:#fff;transition:left .15s}.displayToggle input:checked{background:#2baed4}.displayToggle input:checked::after{left:16px}.displayToggle input:focus-visible{outline:2px solid #42c4e8;outline-offset:3px}
 .displayInfo{font-size:12px;color:#b6cedb;cursor:help}.displaySettings{padding:10px;border:1px solid #496273;border-radius:7px;display:grid;gap:9px}.displaySettings label{display:flex;justify-content:space-between;gap:10px;align-items:center}.displaySettings input{width:68px}.displaySettings input,.displaySettings select{background:#1d4158;color:#eef5fa;border:1px solid #6a8d9f;border-radius:4px;padding:5px}#displayError{color:#ffc1b0;font-size:11px}#displayError:empty{display:none}
 #displayLegend{position:absolute;z-index:6;bottom:10px;left:12px;max-width:calc(100% - 24px);pointer-events:none}#displayLegend #cfMeaning{display:flex;flex-wrap:wrap;gap:5px}.legendChip{background:#142b3be8;border:1px solid #577487;border-radius:14px;padding:3px 7px;display:inline-flex;gap:5px;align-items:center;color:#eaf3f8;font-size:11px}
 .legendChip[hidden]{display:none}
 #displayLegend #cfPlumeLegend{margin:4px 0 0;padding:3px 6px!important;background:#142b3be8;border-radius:4px;font-size:10px;color:#d6e8f3}#displayLegend #cfPlumeLegend small,#displayLegend #cfPlumeLegend br,#displayLegend #cfPlumeNumbers{display:none}
 body.pyroShell .viewHint{bottom:70px;right:12px;left:auto;font-size:10px}#displayView{display:flex;align-items:center;gap:5px;white-space:nowrap}.compactHUD{white-space:normal!important;max-width:calc(100% - 24px)}.hudTitle{display:flex;align-items:center;gap:8px}#hudOrigin{pointer-events:auto;margin-top:5px;background:#1d4158;color:#eaf3f8;border:1px solid #577487;border-radius:4px;padding:3px 6px;cursor:pointer}.hudValues{display:flex;gap:12px;margin-top:3px;font-size:12px}.hudValues b{font-variant-numeric:tabular-nums}#hudPill{padding:2px 8px;border-radius:12px;background:#1d4158;color:#eaf3f8;font-size:11px;white-space:nowrap}
 @media(max-width:860px){#displayView{font-size:11px}#displayView button{padding:4px}.hudValues{gap:8px}#displayLegend{bottom:6px;left:8px}.legendChip{font-size:10px;padding:2px 5px}}
 `;document.head.append(style);
 function sync(){bindings.forEach(f=>f());$('legendHistory').hidden=!store.get('risk').history;const t=store.get('risk').threshold;$('displayRibbon').value=t.ribbon;$('displayCaution').value=t.caution;$('legendCaution').textContent=`주의 ${t.caution}~${t.ribbon-1}`;$('displayTemperature').value=store.get('realView').temperaturePattern;$('displaySmokeColor').value=store.get('realView').smokeColor;$('displayFlameStyle').value=store.get('realView').flameDisplay;$('liteOpacity').value=store.get('realView').smokeOpacity;}
 for(const slice of ['layers','openings','realView','risk'])cleanups.push(store.subscribe(slice,sync));sync();
 function hud({building,result,series,index,selection}){
  const rooms=building.floors.flatMap(f=>f.rooms),room=rooms.find(r=>r.room_id===selection.room_id),cell=selection.cell_id??(room?.cells.length===1?room.cells[0].cell_id:null),s=cell?series.cells[cell]:null;
  const allowed=!!isOriginAllowed(room?.room_id);$('hudOrigin').disabled=!allowed;$('hudOrigin').title=allowed?'선택한 원래 방을 탐색 화점으로 지정합니다':'화점 지정 가능한 실을 선택하세요';
  $('hudRoom').textContent=$('liteRoom').selectedOptions[0]?.textContent||'실 선택';
  const scores=phenomena.map(([key,name,color])=>({key,name,color,value:cell?result.index_by_cell[cell]?.[key]?.[index]:null})).filter(s=>Number.isFinite(s.value)).sort((a,b)=>b.value-a.value),top=scores[0];
  $('hudPill').textContent=top?`${top.name} ${Math.round(top.value)}`:'미평가';$('hudPill').style.color=top?.color||'';
  const format=(n,suffix,digits)=>Number.isFinite(n)?n.toFixed(digits)+suffix:'—';$('hudT').textContent=format(s?.T_upper_C[index],' ℃',0);$('hudO').textContent=format(s?.O2_upper_volfrac[index]==null?null:s.O2_upper_volfrac[index]*100,' %',1);$('hudH').textContent=format(s?.interface_m[index],' m',2);
  selectionLabel.title=cell?'상층 산소 · 바닥에서 연기층 경계까지의 높이':room?.cells.length>1?'방 평균 없음 · 셀을 선택하세요.':'';
 }
 return {hud,dispose(){for(const off of cleanups.reverse())off();for(const undo of moves.reverse())undo();style.remove();legend.remove();view.remove();pane.replaceChildren();}};
}
