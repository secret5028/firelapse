import {createBuildingPanel,buildingTable} from './panels/building.js';
import {attachExplanations} from './panels/explanations.js';
import {createStore} from './state/store.js';
import {createSeriesCache} from './state/series_cache.js';
import {adaptBuilding,adaptResult,adaptScreening} from './adapters/read.js';
import {readLegacyBuildingSource} from './adapters/legacy_building.js';
import {readLegacyOpeningsSource} from './adapters/legacy_openings.js';
import {readLegacyCoreSource} from './adapters/legacy_core.js';
import {BuildingLayer} from './layers/building.js';
import {OpeningsLayer} from './layers/openings.js';
import {CoreLayer} from './layers/core.js';
import {createRealViewLayers} from './layers/real_view_layers.js';
import {RiskLayer} from './layers/risk.js';
import {SelectionLayer} from './layers/selection.js';
import {createSceneHost} from './scene/host.js';
import {createLitePanel,updateLitePanel,createMenuReview} from './panels/legacy_lite_panel.js';
import {createPanelShell} from './panels/shell.js';
import {createDisplayPanel} from './panels/display.js';
import {createResultsPanel,summarizeMCPlayback,resultTypes} from './panels/results.js';
import {createExplorePanel} from './panels/explore.js';
import {attachFrozenRules} from '/cfbt/frozen_rule_controls.js';

// One boundary: existing panel/CAD loader <-> pure store and display layers.
// HTTP boundary only; no solver or cache-key imports.
export async function attachModern(viewer,initial,{clock={now:()=>performance.now()}}={}){
 const {THREE:T,B,S,C,O,R,groups,shp,legacyRoot}=viewer;
 // The unchanged lite API rejects payloads from another building before serving.
 // Subsequent case installs must still match this initial server-validated hash.
 const legacyVisible=legacyRoot.visible,wasReady=document.body.classList.contains('cfbtReady'),panelHeight=document.documentElement.style.getPropertyValue('--cfbt-height');
 const {panel,$,selectionLabel,style}=createLitePanel();legacyRoot.visible=false;
 const cache=createSeriesCache(),store=createStore({seriesCache:cache,validators:{building:v=>v.schema==='pyrocast.building/1'&&!v.errors.length,result:v=>v.schema==='pyrocast.result/1'&&!v.errors.length,screening:v=>v.schema==='pyrocast.screening/1'&&!v.errors.length}});
 const shell=createPanelShell({panel,store});
 const display=createDisplayPanel({store,selectionLabel});
 const results=createResultsPanel({panel,store});
 const buildingAsset=readLegacyBuildingSource({building:B,groups,sourceHash:initial.building_sha256});
 const openingsAsset=readLegacyOpeningsSource({building:B,groups,sourceHash:initial.building_sha256});
 const coreAsset=readLegacyCoreSource({building:B,groups,sourceHash:initial.building_sha256,shapeFor:shp});
 const buildingLayer=new BuildingLayer(T,{geometryFor:()=>buildingAsset}),openings=new OpeningsLayer(T,{geometryFor:()=>openingsAsset,camera:C}),core=new CoreLayer(T,{geometryFor:()=>coreAsset});
 let rawSource=null,data=null,selected=null,clicked=false,autoFit=false,chosen=initial.case_id||'stage4',disposed=false,ready=false,busy=false,last=0,fractional=0,lastFloor='',lastPanel='';
 const real=createRealViewLayers(T,{sourceFor:()=>rawSource,camera:C,fuelSymbols:true}),risk=new RiskLayer(T),selection=new SelectionLayer(T);
 const layers=[buildingLayer,openings,core,...real,risk,selection];
 const cleanup=[],originalRender=R.render,baseRender=R.render.bind(R);
 let screeningPayload=null,screeningPoll=null,screeningRequest=0,screeningBusy=false,frozenRules=null,mcPoll=null,mcJobState=null,catalogSerial=0;
 const exploreAbort=new AbortController();
 const buildingPanel=createBuildingPanel({store,onSave:saveDoor,onRefresh:async()=>{await refreshDoors();await refreshScreening();}});
 async function refreshDoors(){try{const response=await fetch('/cfbt/lite/doors',{signal:exploreAbort.signal});if(!response.ok)throw Error('HTTP '+response.status);const value=await response.json();if(!disposed)store.dispatch('buildingReview/set',{doors:value,status:''});}catch(e){if(!disposed)store.dispatch('buildingReview/set',{status:'문 목록 읽기 실패 · '+e.message});}}
 async function saveDoor(id,door_class){if(store.get('buildingReview').saving||disposed)return;store.dispatch('buildingReview/set',{saving:true,status:'저장 중…'});try{const response=await fetch('/cfbt/lite/doors',{method:'POST',signal:exploreAbort.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({id,door_class})});const value=await response.json();if(!response.ok)throw Error(value.error||'HTTP '+response.status);if(disposed)return;store.dispatch('buildingReview/set',{doors:value,status:id+' · 저장 완료'});await refreshScreening();}catch(e){if(!disposed)store.dispatch('buildingReview/set',{status:'저장 실패 · '+e.message});}finally{if(!disposed)store.dispatch('buildingReview/set',{saving:false});}}

 const explore=createExplorePanel({store,onRun:()=>runScreening(),onRefresh:()=>{refreshScreening();refreshMC();},onMC:()=>runMC(),onResults:()=>{$('shellTab-result').click();$('resultMCLoad').scrollIntoView({block:'center'});if(!$('resultMCLoad').disabled)$('resultMCLoad').click();}});
 async function refreshMC(){
  if(mcPoll)clearTimeout(mcPoll);mcPoll=null;
  try{const response=await fetch('/cfbt/lite/mc',{signal:exploreAbort.signal});if(!response.ok)throw Error('HTTP '+response.status);const value=await response.json();if(disposed)return;const previous=mcJobState;mcJobState=value;explore.mcState(value);
   if((previous?.running&&!value.running)||(value.state==='completed'&&(previous?.id!==value.id||previous?.state!=='completed')))await catalog();
   if(value.running||value.server_busy)mcPoll=setTimeout(refreshMC,3000);
  }catch(error){if(!disposed){explore.mcState({available:false,error:error.message});mcPoll=setTimeout(refreshMC,5000);}}
 }
 async function runMC(){
  const selection=store.get('exploration');explore.mcState(mcJobState||{available:true},true);
  try{const response=await fetch('/cfbt/lite/mc',{method:'POST',signal:exploreAbort.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({room:selection.origin_room_id,samples:selection.samples,duration_s:data.time_s.at(-1),seed:20261025})});const value=await response.json();if(!response.ok)throw Error(value.error||'HTTP '+response.status);if(!disposed)await refreshMC();}
  catch(error){if(!disposed)explore.mcState({...mcJobState,available:true,error:error.message});}
 }
 let catalogOrigin=null;
 cleanup.push(store.subscribe('exploration',()=>{const origin=store.get('exploration').origin_room_id;if(origin!==catalogOrigin){catalogOrigin=origin;catalog().catch(error=>{if(!disposed)explore.status('결과 목록 읽기 실패 · '+error.message);});}}));
 const ruleOptions=()=>{const row=screeningPayload?.score.ranked.find(r=>r.room===store.get('exploration').origin_room_id);if(!row)throw Error('탐색 화점을 먼저 선택하세요.');return {fire_floor:row.floor,fire_room:row.room.replace('CAD_'+row.floor+'_',''),duration_s:data.time_s.at(-1)};};
 function ruleContext(){try{const o=ruleOptions();$('exploreRuleContext').textContent=`정밀 검토 · ${o.fire_floor} ${o.fire_room} · ${o.duration_s/60}분 · 문·창: 서버 기본값`;}catch{$('exploreRuleContext').textContent='탐색 화점 선택 대기';}}
 cleanup.push(store.subscribe('exploration',ruleContext));
 function acceptScreening(value){screeningPayload=value;store.dispatch('buildingReview/set',{rooms:buildingTable(value.score),openings:value.score.opening_states});store.dispatch('screening/set',adaptScreening({...value,buildingId:store.get('building').building_id,floorId:value.score.ranked[0]?.floor??null}));explore.update(value);ruleContext();if(screeningPoll){clearTimeout(screeningPoll);screeningPoll=null;}if(value.progress?.running)screeningPoll=setTimeout(()=>refreshScreening(),3000);}
 async function refreshScreening(){const seq=++screeningRequest;try{const response=await fetch('/cfbt/lite/screening',{signal:exploreAbort.signal});if(!response.ok)throw Error('HTTP '+response.status);const value=await response.json();if(!disposed&&seq===screeningRequest)acceptScreening(value);}catch(error){if(!disposed)explore.status('탐색 목록 읽기 실패 · '+error.message);}}
 async function runScreening(){if(screeningBusy||disposed)return;const state=store.get('exploration');if(!screeningPayload?.score.ranked.some(r=>r.room===state.origin_room_id)||state.top_n>screeningPayload.score.ranked.length){explore.status('적격 실 범위의 N과 화점을 선택하세요.');return;}
  screeningBusy=true;explore.busy(true);let message='';try{const response=await fetch('/cfbt/lite/screening',{method:'POST',signal:exploreAbort.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({top_n:state.top_n,mc_room:state.origin_room_id,run:true})});const value=await response.json();if(!response.ok)throw Error(value.error||'HTTP '+response.status);message='② 실행 요청 완료 · 직렬 계산';await refreshScreening();}catch(error){message='② 실행 요청 실패 · '+error.message;}finally{screeningBusy=false;if(!disposed){explore.busy(false);if(!screeningPayload?.progress?.running)explore.status(message);}}}
 const referenceToggle=$('layer_reference'),referenceVisible=referenceToggle?.checked;
 const legacyChildren=legacyRoot.children.map(o=>[o,o.visible]),people=legacyRoot.children.at(-1);
 let operationsVisible=null;
 function syncOperations(){const visible=store.get('layers').operations;if(visible===operationsVisible)return;operationsVisible=visible;
  if(referenceToggle){referenceToggle.checked=visible;referenceToggle.onchange?.();}
  legacyRoot.visible=visible;for(const [object] of legacyChildren)object.visible=visible&&(object.name==='operation-overlays'||object===people);
 }
 cleanup.push(()=>{for(const [object,visible] of legacyChildren)object.visible=visible;if(referenceToggle){referenceToggle.checked=referenceVisible;referenceToggle.onchange?.();}});
 // Keep the CAD controls/labels and its single canvas. The CAD animation loop
 // calls this host instead of drawing a second scene/starting a second loop.
 const renderer={domElement:R.domElement,setSize:(w,h)=>R.setSize(w,h),render:(scene,camera)=>{
  const hidden=[];
  buildingLayer.syncSource();
  for(const row of buildingAsset.floors){const clone=buildingLayer.floorGroups.get(row.id);if(clone)clone.visible=row.group.visible;row.objects.forEach(source=>{
    hidden.push([source,source.visible]);source.visible=false;});
  }
  try{baseRender(scene,camera);}finally{for(const [object,visible] of hidden)object.visible=visible;}
 }};
 const host=createSceneHost({container:$('v'),THREE:T,store,scene:S,camera:C,layers,clock,adoptedRenderer:renderer,legendContainer:$('cfMeaning'),seriesAt:()=>cache.get(store.get('result')?.result_id)});
 const on=(node,event,fn)=>{node.addEventListener(event,fn);cleanup.push(()=>node.removeEventListener(event,fn));};
 const handler=(node,event,fn)=>{const old=node[event];node[event]=fn;cleanup.push(()=>{node[event]=old;});};
 const name=r=>`${r.cad_floor} ${r.cad_room} · ${r.display_name||'용도 미확인'}`;
 const index=()=>Math.min(data.time_s.length-1,Math.floor(store.get('playback').t_s/10));
 function recordCamera(mode){store.dispatch('camera/fit',{mode,target:O.target.toArray(),pose:{position:C.position.toArray(),quaternion:C.quaternion.toArray(),up:C.up.toArray(),zoom:C.zoom}});}
 function render(){if(!ready||busy||disposed)return;busy=true;try{
  const f=viewer.getFloor();if(f!==lastFloor){lastFloor=f;store.dispatch('floor/set',{floor_id:f==='all'?null:f});}
  const parts=store.get('openings');openings.setPartVisible('window',parts.exterior);openings.setPartVisible('door',parts.interior);
  syncOperations();
  host.render();
  const signature=JSON.stringify([index(),selected?.key,clicked,store.get('playback').playing,f,store.get('realView'),store.get('layers'),store.get('openings'),store.get('risk')]);
  if(signature!==lastPanel){$('liteReal').setAttribute('aria-pressed',String(store.get('realView').enabled));updateLitePanel({data,index:index(),selected,clicked,playing:store.get('playback').playing,floor:f,$,selectionLabel,riskStatus:risk.summary()});const context={building:store.get('building'),result:store.get('result'),series:cache.get(store.get('result').result_id),index:index(),selection:store.get('selection')};display.hud(context);results.update(context);shell.syncStatus();lastPanel=signature;}
 }finally{busy=false;}}
 function frame(){if(!ready||disposed)return;const ms=clock.now();
  if(document.hidden){last=ms;return;}
  if(store.get('playback').playing){fractional+=Math.min(.2,Math.max(0,(ms-last)/1000))*store.get('playback').speed;
   if(fractional>=10){const next=Math.min(data.time_s.at(-1),store.get('playback').t_s+Math.floor(fractional/10)*10);fractional%=10;store.dispatch('playback/seek',{t_s:next});if(next===data.time_s.at(-1))store.dispatch('playback/play',{playing:false});}}
  render();last=ms;
 }
 R.render=frame;
 cleanup.push(()=>{R.render=originalRender;});
 function resize(){const v=$('v');R.setSize(v.clientWidth,v.clientHeight);viewer.L2?.setSize(v.clientWidth,v.clientHeight);C.aspect=v.clientWidth/Math.max(1,v.clientHeight);C.updateProjectionMatrix();render();}
 const observer=new ResizeObserver(resize);observer.observe($('v'));cleanup.push(()=>observer.disconnect());on(window,'resize',resize);
 function fitFloor(){const rooms=data.rooms.filter(r=>viewer.getFloor()==='all'||r.cad_floor===viewer.getFloor());if(!rooms.length)return;
  const bounds=new T.Box3();
  if(viewer.getFloor()==='all'){for(const f of B.floors)for(const p of f.slab||[])for(const xy of p.o){bounds.expandByPoint(new T.Vector3(xy[0],xy[1],f.z));bounds.expandByPoint(new T.Vector3(xy[0],xy[1],f.z+f.h));}}
  else for(const r of rooms)for(const p of r.cad_polys)for(const xy of p.o){bounds.expandByPoint(new T.Vector3(xy[0],xy[1],r.z_m));bounds.expandByPoint(new T.Vector3(xy[0],xy[1],r.z_m+r.height_m));}
  const center=bounds.getCenter(new T.Vector3()),radius=bounds.getSize(new T.Vector3()).length()/2;
  const vertical=C.fov*Math.PI/180,horizontal=2*Math.atan(Math.tan(vertical/2)*C.aspect),distance=radius/Math.sin(Math.min(vertical,horizontal)/2)*1.05;
  O.target.copy(center);C.position.copy(center).add(new T.Vector3(1,-1,1.1).normalize().multiplyScalar(distance));O.update();recordCamera(viewer.getFloor()==='all'?'all':'floor');render();
 }
 for(const id of ['top','iso','resetView','zoomIn','zoomOut']){const button=$(id),old=button.onclick;handler(button,'onclick',function(e){old?.call(this,e);recordCamera(id==='top'?'top':id==='iso'||id==='resetView'?(viewer.getFloor()==='all'?'all':'floor'):store.get('camera').mode);render();});}
 for(const button of $('fbtn').children){const old=button.onclick;handler(button,'onclick',function(e){const position=C.position.clone(),target=O.target.clone(),zoom=C.zoom;autoFit=false;old?.call(this,e);C.position.copy(position);O.target.copy(target);C.zoom=zoom;C.updateProjectionMatrix();O.update();store.dispatch('floor/set',{floor_id:viewer.getFloor()==='all'?null:viewer.getFloor()});recordCamera(store.get('camera').mode);render();});}
 on(R.domElement,'pointerdown',()=>{autoFit=false;});
 cleanup.push(store.subscribe('selection',s=>{if(!data)return;selected=data.rooms.find(r=>r.key===s.cell_id)||data.rooms.find(r=>(r.original_room||r.key)===s.room_id)||selected;$('liteRoom').value=selected.key;if(s.source!=='list'||ready)clicked=true;if(viewer.getFloor()!=='all'&&viewer.getFloor()!==selected.cad_floor)viewer.setFloor(selected.cad_floor);render();}));
 function select(key){const r=data.rooms.find(r=>r.key===key)||selected;store.dispatch('selection/set',{room_id:r.original_room||r.key,cell_id:r.key,source:'list'});}
 handler($('liteRoom'),'onchange',()=>select($('liteRoom').value));
 handler($('liteFocus'),'onclick',()=>{clicked=true;autoFit=false;const p=selected.cad_center_m;O.target.set(p[0],p[1],selected.z_m+1);C.position.set(p[0]+15,p[1]-18,selected.z_m+18);O.update();recordCamera('room');render();});
 handler($('liteFireFocus'),'onclick',()=>{const burning=data.fires.filter(f=>f.Q_kW[index()]>0),fire=burning.find(f=>f.cad_key===selected.key)||burning[0];
  if(!fire){$('liteVisible').textContent='현재 시점에는 연소 중인 화원이 없습니다. 시간을 이동하거나 재생하세요.';return;}
  viewer.setFloor(fire.cad_floor);select(fire.cad_key);autoFit=false;$('liteReal').setAttribute('aria-pressed','true');$('liteSmoke').checked=true;store.dispatch('realView/set',{enabled:true});store.dispatch('layers/toggle',{id:'smoke',visible:true});
  const p=fire.position_m;O.target.set(p[0],p[1],p[2]+.8);C.position.set(p[0]+6,p[1]-8,p[2]+Math.max(6,selected.height_m+3));O.update();recordCamera('fire');render();});
 handler($('liteWhole'),'onclick',fitFloor);handler($('liteBuilding'),'onclick',()=>{viewer.setFloor('all');render();fitFloor();});
 for(const [id,layer] of [['liteCores','core'],['liteSmoke','smoke'],['litePlumes','plume']])handler($(id),'onchange',()=>{store.dispatch('layers/toggle',{id:layer,visible:$(id).checked});render();});
 for(const [id,key] of [['liteExterior','exterior'],['liteDoors','interior']])handler($(id),'onchange',()=>{store.dispatch('openings/set',{[key]:$(id).checked});render();});
 handler($('liteFuel'),'onchange',()=>{store.dispatch('realView/set',{fuelMarkers:$('liteFuel').checked});render();});
 handler($('liteOpacity'),'onchange',()=>{store.dispatch('realView/set',{smokeOpacity:+$('liteOpacity').value});render();});
 handler($('liteReal'),'onclick',()=>{const enabled=!store.get('realView').enabled;store.dispatch('realView/set',{enabled});$('liteReal').setAttribute('aria-pressed',String(enabled));render();});
 handler($('litePlay'),'onclick',()=>{store.dispatch('playback/play',{playing:!store.get('playback').playing});render();});
 handler($('liteSpeed'),'onchange',()=>store.dispatch('playback/speed',{speed:+$('liteSpeed').value}));store.dispatch('playback/speed',{speed:20});
 handler($('liteTime'),'oninput',()=>{store.dispatch('playback/play',{playing:false});store.dispatch('playback/seek',{t_s:Math.floor(+$('liteTime').value/10)*10});render();});
 handler($('liteFold'),'onclick',()=>{$('liteBody').hidden=!$('liteBody').hidden;$('liteFold').textContent=$('liteBody').hidden?'펼치기':'접기';});
 async function install(payload,id){
  if(payload.schema!=='pyrocast-cad-playback-1'||!payload.complete||payload.building_sha256!==initial.building_sha256)throw Error('다른 건물 또는 미완료 계산 결과입니다. 표시하지 않습니다.');
  const seq=store.dispatch('result/load'),byRoom=new Map();
  for(const c of payload.rooms){const key=c.original_room||c.key;if(byRoom.has(key))continue;const f=B.floors.find(f=>f.name===c.cad_floor),r=f?.rooms.find(r=>`CAD_${f.name}_${r.id}`===key);if(!r)throw Error('CAD room missing: '+key);
   byRoom.set(key,{id:key,name:r.names?.join(' / ')||key,cad_floor:c.cad_floor,cad_polys:r.polys,z_m:c.z_m,height_m:c.height_m});}
  const scenario={rooms:[...byRoom.values()],openings:[],cad:{building_sha256:payload.building_sha256}};
  const building=adaptBuilding({scenario,playback:payload,sourceHash:payload.building_sha256}),result=await adaptResult({playback:payload,scenario,building,resultId:id});
  if(seq!==store.get('request').seq)return false;
  ready=false;data=payload;chosen=id;rawSource={source_hash:payload.building_sha256,result_id:id,data:payload,B,groups};store.dispatch('building/set',building);store.dispatch('result/receive',{seq,result});
  $('liteRoom').replaceChildren();for(const r of data.rooms)$('liteRoom').add(new Option(name(r),r.key));
  selected=data.rooms.find(r=>r.key===data.fire_key)||data.rooms[0];clicked=false;select(selected.key);$('liteTime').max=data.time_s.at(-1);$('liteTime').value=0;$('liteLimits').textContent=data.limits.join(' ');
  lastPanel='';ruleContext();ready=true;viewer.setFloor('3F');render();fitFloor();return true;
 }
 let mcSummary=null,mcRun=0,mcAbort=null;
 async function catalog(){const serial=++catalogSerial,originRequested=store.get('exploration').origin_room_id;const r=await fetch('/cfbt/lite/catalog.json'+(originRequested?'?mc_room='+encodeURIComponent(originRequested):''),{signal:exploreAbort.signal});if(!r.ok)return;const c=await r.json();if(disposed||serial!==catalogSerial)return;mcRun++;mcAbort?.abort();mcSummary=c.mc_summary??null;$('liteCase').replaceChildren();for(const entry of c.cases||[])$('liteCase').add(new Option(entry.label,entry.id));$('liteCase').value=chosen;$('liteMC').textContent=c.progress_text||'';results.mc(mcSummary);
  let origin=null;const saved=mcSummary?.rows?.find(row=>row.complete);if(saved){try{const p=mcSummary.rows.some(row=>row.id===chosen)?data:await (await fetch('/cfbt/lite/result/'+encodeURIComponent(saved.id),{signal:exploreAbort.signal})).json();if(p.complete&&p.building_sha256===initial.building_sha256)origin=p.rooms.find(r=>r.key===p.fire_key)?.original_room??p.fire_key;}catch{}}
  if(!disposed&&serial===catalogSerial)explore.catalog(c,origin);
 }
 handler($('resultMCLoad'),'onclick',async()=>{if(!mcSummary)return;const run=++mcRun,summary=mcSummary;mcAbort?.abort();mcAbort=new AbortController();const full=Object.fromEntries(resultTypes.map(([k])=>[k,{rooms:0,unknown:false}]));$('resultMCLoad').disabled=true;
  try{const rows=summary.rows.filter(r=>r.complete);let done=0;
   for(const row of rows){$('resultMCStatus').textContent=`저장 표본 읽는 중 ${done}/${rows.length}`;const response=await fetch('/cfbt/lite/result/'+encodeURIComponent(row.id),{signal:mcAbort.signal});if(!response.ok)throw Error(`${row.id} HTTP ${response.status}`);const p=await response.json();if(run!==mcRun||disposed)return;if(p.building_sha256!==initial.building_sha256||p.schema!=='pyrocast-cad-playback-1')throw Error('다른 건물 또는 형식의 표본');const record=summarizeMCPlayback(p);for(const [key] of resultTypes){full[key].rooms=Math.max(full[key].rooms,record[key].rooms);full[key].unknown ||= record[key].unknown;}done++;}
   results.mc(summary,full);$('resultMCStatus').textContent=`집계 완료 ${done}/${summary.rows.length}표본`;
  }catch(error){if(run===mcRun&&!disposed)$('resultMCStatus').textContent='집계 미완료 · '+error.message;}
  finally{if(run===mcRun&&!disposed)$('resultMCLoad').disabled=false;}
 });
 let loadSerial=0;
 handler($('liteRefresh'),'onclick',catalog);handler($('liteCase'),'onchange',async()=>{const serial=++loadSerial,id=$('liteCase').value,r=await fetch('/cfbt/lite/result/'+encodeURIComponent(id));if(r.ok){const payload=await r.json();if(serial===loadSerial)await install(payload,id);}});
 await install(initial,chosen);await catalog();await refreshScreening();await refreshDoors();await refreshMC();
 try{frozenRules=await attachFrozenRules($('exploreRuleMount'),ruleOptions);const rules=$('cfbtFrozenRules');rules.open=true;
  // The modern presentation boundary moves descriptions to accessible info tips.
 }catch(error){$('exploreRuleMount').textContent='규칙 설정 읽기 실패 · '+error.message;}
 const review=await createMenuReview(panel,viewer);results.mountReview(review);handler($('reviewClose'),'onclick',()=>{$('resultMenuReview').open=false;});handler($('liteReview'),'onclick',()=>{$('shellTab-result').click();$('resultMenuReview').open=true;});document.body.classList.add('cfbtReady');resize();
 const explanations=attachExplanations();
 function dispose(){if(disposed)return;disposed=true;catalogSerial++;if(mcPoll)clearTimeout(mcPoll);explanations.dispose();screeningRequest++;exploreAbort.abort();if(screeningPoll)clearTimeout(screeningPoll);frozenRules?.dispose();loadSerial++;mcRun++;mcAbort?.abort();store.dispatch('result/load');observer.disconnect();for(const off of cleanup.reverse())off();review.dispose();host.dispose();buildingPanel.dispose();explore.dispose();results.dispose();display.dispose();shell.dispose();cache.clear();panel.remove();selectionLabel.remove();style.remove();legacyRoot.visible=legacyVisible;document.body.classList.toggle('cfbtReady',wasReady);if(panelHeight)document.documentElement.style.setProperty('--cfbt-height',panelHeight);else document.documentElement.style.removeProperty('--cfbt-height');}
 on(window,'pagehide',dispose);
 return Object.freeze({store,host,layers,render,install,dispose,diagnostics:()=>({ui:'modern',autoFit,case_id:chosen,canvasCount:$('v').querySelectorAll('canvas').length,legendCount:document.querySelectorAll('#cfMeaning').length})});
}
