import {createAIFuelPanel} from './panels/ai_fuel.js';
import {createAssistantPanel} from './panels/assistant.js';
import {attachExport} from './panels/export.js';
import {routeSampleIndex} from './route/risk.js';
import {readRouteGraph,contains} from './route/graph.js';
import {RouteLayer} from './layers/route.js';
import {createRoutePanel} from './panels/route.js';
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
import {createLitePanel,updateLitePanel} from './panels/legacy_lite_panel.js';
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
 const display=createDisplayPanel({store,selectionLabel,isOriginAllowed:room=>screeningPayload?.manual_origins?.some(r=>r.room===room),onOrigin:room=>{if(!screeningPayload?.manual_origins?.some(r=>r.room===room))return;store.dispatch('exploration/set',{origin_room_id:room,origin_mode:'manual'});$('shellTab-explore').click();}});
 const results=createResultsPanel({panel,store});
 const buildingAsset=readLegacyBuildingSource({building:B,groups,sourceHash:initial.building_sha256});
 const openingsAsset=readLegacyOpeningsSource({building:B,groups,sourceHash:initial.building_sha256});
 const coreAsset=readLegacyCoreSource({building:B,groups,sourceHash:initial.building_sha256,shapeFor:shp});
 const buildingLayer=new BuildingLayer(T,{geometryFor:()=>buildingAsset}),openings=new OpeningsLayer(T,{geometryFor:()=>openingsAsset,camera:C}),core=new CoreLayer(T,{geometryFor:()=>coreAsset});
 let rawSource=null,data=null,selected=null,clicked=false,autoFit=false,chosen=initial.case_id||'stage4',disposed=false,ready=false,busy=false,last=0,fractional=0,lastFloor='',lastPanel='';
 const real=createRealViewLayers(T,{sourceFor:()=>rawSource,camera:C,fuelSymbols:true}),risk=new RiskLayer(T),selection=new SelectionLayer(T);
 let routeGraph;try{routeGraph=readRouteGraph(B);}catch(error){routeGraph={error:error.message,ground:{z:0,slab:[]},mainEntrance:null,defaultVehicle:null};}
 const referenceGroup=S.children.find(g=>g.children?.some(c=>c.type==='GridHelper')),vehicleSource=referenceGroup?.children.find(c=>c.isGroup);
 let routeUI=null;
 const route=new RouteLayer(T,{graph:routeGraph,vehicleSource,targetFor:()=>{const choice=store.get('exploration');if(choice.origin_mode==='manual'&&choice.origin_room_id)return choice.origin_room_id;if(data?.route_target_room_id)return data.route_target_room_id;const r=data?.rooms.find(r=>r.key===data.fire_key);return r?.original_room||r?.key||data?.fire_key;},onChange:r=>routeUI?.update(r)});
 const layers=[buildingLayer,openings,core,...real,risk,selection,route];
 const cleanup=[],originalRender=R.render,baseRender=R.render.bind(R);
 let screeningPayload=null,screeningPoll=null,screeningRequest=0,screeningBusy=false,frozenRules=null,mcPoll=null,mcJobState=null,catalogSerial=0;
 const exploreAbort=new AbortController();
 let aiFuelRooms=null;
 const buildingPanel=createBuildingPanel({store,building:B,onLocate:row=>{
  const floor=B.floors.find(f=>f.name===row.floor),item=floor?.rooms.find(r=>r.id===row.id)||floor?.openings.find(o=>o.id===row.id);
  const points=(item?.polys||[]).flatMap(p=>Array.isArray(p)?p:p.o||[]);if(!points.length)return;
  const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]),x=(Math.min(...xs)+Math.max(...xs))/2,y=(Math.min(...ys)+Math.max(...ys))/2,z=floor.z||0;
  viewer.setFloor(row.floor);store.dispatch('floor/set',{floor_id:row.floor});
  const d=Math.max(8,Math.max(...xs)-Math.min(...xs),Math.max(...ys)-Math.min(...ys));
  store.dispatch('camera/fit',{mode:'room',target:[x,y,z+1],pose:{position:[x+d,y-d,z+d],up:[0,0,1]}});render();
 },onSave:saveDoor,onClearFixed:()=>saveFixed({clear:true}),onRefresh:async()=>{await refreshDoors();await refreshScreening();}});
 const aiFuel=createAIFuelPanel({onApplied:()=>refreshScreening(),onRooms:rooms=>{if(!Array.isArray(rooms))return;aiFuelRooms=rooms;store.dispatch('buildingReview/set',{rooms});}});
 const assistant=createAssistantPanel({store,available:viewer.capabilities?.assistant!==false,getContext:()=>({building:initial.building_sha256,case:chosen,floor:store.get('floor').floor_id,room:store.get('selection').room_id,origin:data?.route_target_room_id||data?.fire_key,time_s:store.get('playback').t_s,history:store.get('risk').history,vehicle:route.result?.vehicle,route_settings:{hose_m:store.get('route').hose_m,stair_factor:store.get('route').stair_factor}}),
  onNavigate:fact=>{if(fact.case!==chosen)throw Error('현재 사례와 다른 답변입니다. 해당 사례를 먼저 선택하세요.');const c=data.rooms.find(r=>r.key===fact.cell)||data.rooms.find(r=>(r.original_room||r.key)===fact.room);if(!c)return;viewer.setFloor(c.cad_floor);store.dispatch('floor/set',{floor_id:c.cad_floor});select(c.key);if(Number.isFinite(fact.time_s))store.dispatch('playback/seek',{t_s:fact.time_s});render();},
  onProposal:async(p,rooms,building)=>{if(building!==initial.building_sha256&&building!==(B.building_id||'cad-main'))throw Error('다른 건물 제안');if(p.kind==='mc'||p.kind==='screening'){store.dispatch('exploration/set',{origin_room_id:p.origin,origin_mode:'manual',...(p.samples?{samples:p.samples}:{}),...(p.N?{top_n:p.N}:{})});if(p.kind==='mc')await runMC();else await runScreening(true);return;}
   const path=p.kind==='openings'?'/cfbt/lite/fixed-openings':'/cfbt/lite/fuel-overrides',body=p.kind==='openings'?{assistant_proposal:p.proposal_id}:{proposal_id:p.proposal_id,rooms};const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const v=await response.json();if(!response.ok)throw Error(v.error||'적용 실패');await refreshDoors();await refreshScreening();await aiFuel.refresh();},onSaved:()=>assistant.refreshReports()});cleanup.push(()=>assistant.dispose());
 async function refreshDoors(){try{const response=await fetch('/cfbt/lite/doors',{signal:exploreAbort.signal});if(!response.ok)throw Error('HTTP '+response.status);const value=await response.json();if(!disposed)store.dispatch('buildingReview/set',{doors:value,status:''});}catch(e){if(!disposed)store.dispatch('buildingReview/set',{status:'문 목록 읽기 실패 · '+e.message});}}
 async function saveDoor(id,door_class){if(store.get('buildingReview').saving||disposed)return;store.dispatch('buildingReview/set',{saving:true,status:'저장 중…'});try{const response=await fetch('/cfbt/lite/doors',{method:'POST',signal:exploreAbort.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({id,door_class})});const value=await response.json();if(!response.ok)throw Error(value.error||'HTTP '+response.status);if(disposed)return;store.dispatch('buildingReview/set',{doors:value,status:id+' · 저장 완료'});await refreshScreening();}catch(e){if(!disposed)store.dispatch('buildingReview/set',{status:'저장 실패 · '+e.message});}finally{if(!disposed)store.dispatch('buildingReview/set',{saving:false});}}

 const explore=createExplorePanel({store,onRun:()=>runScreening(),onRunOrigin:()=>runScreening(true),onRefresh:()=>{refreshScreening();refreshMC();},onMC:()=>runMC(),onResults:()=>{$('shellTab-result').click();$('resultMCLoad').scrollIntoView({block:'center'});if(!$('resultMCLoad').disabled)$('resultMCLoad').click();}});
 routeUI=createRoutePanel({store,graph:routeGraph});cleanup.push(()=>routeUI.dispose());
 async function refreshMC(){
  if(mcPoll)clearTimeout(mcPoll);mcPoll=null;
  try{const response=await fetch('/cfbt/lite/mc',{signal:exploreAbort.signal});if(!response.ok)throw Error('HTTP '+response.status);const value=await response.json();if(disposed)return;const previous=mcJobState;mcJobState=value;explore.mcState(value);
   if((previous?.running&&!value.running)||(value.state==='completed'&&(previous?.id!==value.id||previous?.state!=='completed')))await catalog();
   if(value.running||value.server_busy)mcPoll=setTimeout(refreshMC,3000);
  }catch(error){if(!disposed){explore.mcState({available:false,error:error.message});mcPoll=setTimeout(refreshMC,5000);}}
 }
 async function runMC(){
  const selection=store.get('exploration');explore.mcState(mcJobState||{available:true},true);
  try{const response=await fetch('/cfbt/lite/mc',{method:'POST',signal:exploreAbort.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({room:selection.origin_room_id,samples:selection.samples,duration_s:data.time_s.at(-1),seed:20261025,manual:selection.origin_mode==='manual'})});const value=await response.json();if(!response.ok)throw Error(value.error||'HTTP '+response.status);if(!disposed)await refreshMC();}
  catch(error){if(!disposed)explore.mcState({...mcJobState,available:true,error:error.message});}
 }
 let catalogOrigin=null;
 cleanup.push(store.subscribe('exploration',()=>{const origin=store.get('exploration').origin_room_id;if(origin!==catalogOrigin){catalogOrigin=origin;catalog().catch(error=>{if(!disposed)explore.status('결과 목록 읽기 실패 · '+error.message);});}}));
 const ruleOptions=()=>{const row=screeningPayload?.score.ranked.find(r=>r.room===store.get('exploration').origin_room_id);if(!row)throw Error('탐색 화점을 먼저 선택하세요.');return {fire_floor:row.floor,fire_room:row.room.replace('CAD_'+row.floor+'_',''),duration_s:data.time_s.at(-1)};};
 function ruleContext(){try{const o=ruleOptions();$('exploreRuleContext').textContent=`정밀 검토 · ${o.fire_floor} ${o.fire_room} · ${o.duration_s/60}분 · 문·창: 서버 기본값`;}catch{$('exploreRuleContext').textContent='탐색 화점 선택 대기';}}
 cleanup.push(store.subscribe('exploration',ruleContext));
 function acceptScreening(value){screeningPayload=value;lastPanel="";store.dispatch('buildingReview/set',{rooms:aiFuelRooms??buildingTable(value.score),openings:value.score.opening_states});store.dispatch('screening/set',adaptScreening({...value,buildingId:store.get('building').building_id,floorId:value.score.ranked[0]?.floor??null}));explore.update(value);ruleContext();if(screeningPoll){clearTimeout(screeningPoll);screeningPoll=null;}if(value.progress?.running)screeningPoll=setTimeout(()=>refreshScreening(),3000);}
 async function refreshScreening(){const wasRunning=screeningPayload?.progress?.running;const seq=++screeningRequest;try{const response=await fetch('/cfbt/lite/screening'+(viewer.getScreeningFloor?.()?'?floor='+encodeURIComponent(viewer.getScreeningFloor()):''),{signal:exploreAbort.signal});if(!response.ok)throw Error('HTTP '+response.status);const value=await response.json();if(!disposed&&seq===screeningRequest){acceptScreening(value);if(wasRunning&&!value.progress?.running)await catalog();}}catch(error){if(!disposed)explore.status('탐색 목록 읽기 실패 · '+error.message);}}
 async function runScreening(manual=false){if(screeningBusy||disposed)return;const state=store.get('exploration');if(manual?!screeningPayload?.manual_origins?.some(r=>r.room===state.origin_room_id):state.top_n>screeningPayload.score.ranked.length){explore.status('적격 실 범위의 N과 화점을 선택하세요.');return;}
  screeningBusy=true;explore.busy(true);let message='';try{const response=await fetch('/cfbt/lite/screening'+(viewer.getScreeningFloor?.()?'?floor='+encodeURIComponent(viewer.getScreeningFloor()):''),{method:'POST',signal:exploreAbort.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({top_n:state.top_n,mc_room:manual?state.origin_room_id:(screeningPayload.score.ranked.some(r=>r.room===state.origin_room_id)?state.origin_room_id:null),run:true,...(manual?{rooms:[state.origin_room_id]}:{})})});const value=await response.json();if(!response.ok)throw Error(value.error||'HTTP '+response.status);message='② 실행 요청 완료 · 직렬 계산';await refreshScreening();if(!disposed&&!screeningPoll)screeningPoll=setTimeout(refreshScreening,1000);}catch(error){message='② 실행 요청 실패 · '+error.message;}finally{screeningBusy=false;if(!disposed){explore.busy(false);if(!screeningPayload?.progress?.running)explore.status(message);}}}
 // Imported CAD operation/person objects are not part of the supported UI.
 const referenceToggle=$('layer_reference');if(referenceToggle){referenceToggle.checked=false;referenceToggle.onchange?.();referenceToggle.disabled=true;referenceToggle.closest('label').hidden=true;}
 // Keep the CAD controls/labels and its single canvas. The CAD animation loop
 // calls this host instead of drawing a second scene/starting a second loop.
 const renderer={domElement:R.domElement,setSize:(w,h)=>R.setSize(w,h),render:(scene,camera)=>{
  const hidden=[];
  buildingLayer.syncSource();
  for(const row of buildingAsset.floors){const clone=buildingLayer.floorGroups.get(row.id);if(clone)clone.visible=row.group.visible;row.objects.forEach(source=>{
    hidden.push([source,source.visible]);source.visible=false;});
  }
  display.applyScene({risk,scene,camera,route});
  try{baseRender(scene,camera);}finally{for(const [object,visible] of hidden)object.visible=visible;}
 }};
 const host=createSceneHost({container:$('v'),THREE:T,store,scene:S,camera:C,layers,clock,adoptedRenderer:renderer,legendContainer:$('cfMeaning'),groundPick:{z:routeGraph.ground.z,active:()=>!routeGraph.error&&store.get('route').placing,place:p=>{if(contains(p,routeGraph.ground.slab))store.dispatch('route/set',{message:'건물 밖 지면을 선택하세요'});else store.dispatch('route/set',{vehicle:p,placing:false,message:''});}},seriesAt:()=>cache.get(store.get('result')?.result_id)});
 const on=(node,event,fn)=>{node.addEventListener(event,fn);cleanup.push(()=>node.removeEventListener(event,fn));};
 const handler=(node,event,fn)=>{const old=node[event];node[event]=fn;cleanup.push(()=>{node[event]=old;});};
 const name=r=>`${r.cad_floor} ${r.cad_room} · ${r.display_name||'용도 미확인'}`;
 const index=()=>Math.max(0,routeSampleIndex(data,store.get('playback').t_s));
 function recordCamera(mode){store.dispatch('camera/fit',{mode,target:O.target.toArray(),pose:{position:C.position.toArray(),quaternion:C.quaternion.toArray(),up:C.up.toArray(),zoom:C.zoom}});}
 function render(){if(!ready||busy||disposed)return;busy=true;try{
  const f=viewer.getFloor();if(f!==lastFloor){lastFloor=f;store.dispatch('floor/set',{floor_id:f==='all'?null:f});}
  const parts=store.get('openings');openings.setPartVisible('window',parts.exterior);openings.setPartVisible('door',parts.interior);
  host.render();
  const signature=JSON.stringify([index(),selected?.key,clicked,store.get('playback').playing,f,store.get('realView'),store.get('layers'),store.get('openings'),store.get('risk')]);
  if(signature!==lastPanel){$('liteReal').setAttribute('aria-pressed',String(store.get('realView').enabled));updateLitePanel({data,index:index(),selected,clicked,playing:store.get('playback').playing,floor:f,$,selectionLabel,riskStatus:risk.summary()});const context={building:store.get('building'),result:store.get('result'),series:cache.get(store.get('result').result_id),index:index(),selection:store.get('selection')};display.hud(context);results.update(context);shell.syncStatus();lastPanel=signature;}
 }finally{busy=false;}}
 // Display controls must update the GPU on input, including paused/throttled
 // animation loops in embedded or background viewers. Dispose owns this listener.
 cleanup.push(store.subscribe('realView',render));
 cleanup.push(store.subscribe('openings',render));
 cleanup.push(store.subscribe('buildingReview',render));
 function frame(){if(!ready||disposed)return;const ms=clock.now();
  if(document.hidden){last=ms;return;}
  if(store.get('playback').playing){fractional+=Math.min(.2,Math.max(0,(ms-last)/1000))*store.get('playback').speed;
   const step=data.output_step_s||10;if(fractional>=step){const next=Math.min(data.time_s.at(-1),store.get('playback').t_s+Math.floor(fractional/step)*step);fractional%=step;store.dispatch('playback/seek',{t_s:next});if(next===data.time_s.at(-1))store.dispatch('playback/play',{playing:false});}}
  render();last=ms;
 }
 R.render=frame;
 cleanup.push(()=>{R.render=originalRender;});
 function resize(){const v=$('v');R.setSize(v.clientWidth,v.clientHeight);viewer.L2?.setSize(v.clientWidth,v.clientHeight);C.aspect=v.clientWidth/Math.max(1,v.clientHeight);C.updateProjectionMatrix();render();}
 let resizeFrame=null;const observer=new ResizeObserver(()=>{if(resizeFrame===null)resizeFrame=requestAnimationFrame(()=>{resizeFrame=null;if(!disposed)resize();});});observer.observe($('v'));cleanup.push(()=>{observer.disconnect();if(resizeFrame!==null)cancelAnimationFrame(resizeFrame);});on(window,'resize',resize);
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
 handler($('liteTime'),'oninput',()=>{store.dispatch('playback/play',{playing:false});store.dispatch('playback/seek',{t_s:+$('liteTime').value});render();});
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
  $('liteTime').step=data.output_step_s||10;
  lastPanel='';ruleContext();ready=true;viewer.setFloor(selected.cad_floor);render();fitFloor();return true;
 }
 let mcSummary=null,mcRun=0,mcAbort=null;
 async function saveFixed(body){
  if(disposed||store.get('buildingReview').saving)return;
  store.dispatch('buildingReview/set',{saving:true,status:'확정 급기 저장 중…'});
  $('resultMCApplyWorst').disabled=true;
  try{
   const response=await fetch('/cfbt/lite/fixed-openings',{method:'POST',signal:exploreAbort.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
   const value=await response.json();if(!response.ok)throw Error(value.error||'HTTP '+response.status);
   if(disposed)return;
   store.dispatch('buildingReview/set',{doors:value,status:'이후 실행 입력 적용 · 현재 결과 유지'});
   $('resultMCStatus').textContent=value.fixed_state?`표본 ${value.fixed_state.sample_id} 적용 완료`:'확정 급기 해제';
   await refreshScreening();await catalog();
   $('resultMCStatus').textContent=value.fixed_state?`표본 ${value.fixed_state.sample_id} 적용 완료`:'확정 급기 해제';
  }catch(error){
   if(!disposed){store.dispatch('buildingReview/set',{status:'확정 급기 저장 실패 · '+error.message});$('resultMCStatus').textContent=error.message;}
  }finally{
   if(!disposed){store.dispatch('buildingReview/set',{saving:false});$('resultMCApplyWorst').disabled=!mcSummary?.worst;}
  }
 }
 handler($('resultMCApplyWorst'),'onclick',()=>{if(mcSummary?.worst)saveFixed({job_id:mcSummary.job_id});});
 const reuseByCase=new Map();
 const showReuse=value=>{$('resultReuse').dataset.caseId=value?.case_id||chosen;$('resultReuse').textContent=value?.label||'과거 결과 재사용';$('resultReuse').title=value?.equivalent?'저장 입력·엔진·계산 의존성 검증 일치':'현재 계산과의 동등성이 증명되지 않은 저장 결과';};
 handler($('resultReplay'),'onclick',async()=>{const id=chosen;$('resultReplay').disabled=true;try{const r=await fetch('/cfbt/reuse/lite/'+encodeURIComponent(id),{signal:exploreAbort.signal});const value=await r.json();if(!r.ok)throw Error(value.error||'재사용 실패');if(!disposed&&id===chosen){reuseByCase.set(id,value);showReuse(value);}}catch(e){if(!disposed)$('resultReuse').textContent='재사용 확인 실패 · '+e.message;}finally{if(!disposed)$('resultReplay').disabled=false;}});
 async function catalog(){const serial=++catalogSerial,originRequested=store.get('exploration').origin_room_id;const r=await fetch('/cfbt/lite/catalog.json'+(originRequested?'?mc_room='+encodeURIComponent(originRequested):''),{signal:exploreAbort.signal});if(!r.ok)return;const c=await r.json();if(disposed||serial!==catalogSerial)return;mcRun++;mcAbort?.abort();mcSummary=c.mc_summary??null;$('liteCase').replaceChildren();for(const entry of c.cases||[])$('liteCase').add(new Option(entry.label,entry.id));$('liteCase').value=chosen;for(const [id,value] of Object.entries(c.reuse_by_case||{}))reuseByCase.set(id,value);showReuse(reuseByCase.get(chosen));$('liteMC').textContent=c.progress_text||'';results.mc(mcSummary);
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
 handler($('liteRefresh'),'onclick',catalog);handler($('liteCase'),'onchange',async()=>{const serial=++loadSerial,id=$('liteCase').value;$('resultReplay').disabled=true;try{const r=await fetch('/cfbt/lite/result/'+encodeURIComponent(id));if(r.ok){const payload=await r.json();if(serial===loadSerial){await install(payload,id);showReuse(reuseByCase.get(id));}}}finally{if(!disposed&&serial===loadSerial)$('resultReplay').disabled=false;}});
 await install(initial,chosen);await catalog();await refreshScreening();await refreshDoors();await refreshMC();await aiFuel.refresh();
 try{if(viewer.capabilities?.frozenRules===false){$('exploreRuleMount').textContent='현재 간략 규칙 사용 · 정밀 실행 연결 전';}else if(initial.engine_kind==='cfast_native'){$('exploreRuleMount').textContent='순정 CFAST 저장 입력 · 보기 전용';}else{frozenRules=await attachFrozenRules($('exploreRuleMount'),ruleOptions);const rules=$('cfbtFrozenRules');rules.open=true;}
  // The modern presentation boundary moves descriptions to accessible info tips.
 }catch(error){$('exploreRuleMount').textContent='규칙 설정 읽기 실패 · '+error.message;}
 document.body.classList.add('cfbtReady');resize();
 cleanup.push(attachExport({store,viewer,getCase:()=>chosen,getRoute:()=>({...route.result,risk_summary:route.riskDisplay}),render}));
 const explanations=attachExplanations();
 function dispose(){if(disposed)return;disposed=true;catalogSerial++;if(mcPoll)clearTimeout(mcPoll);explanations.dispose();screeningRequest++;exploreAbort.abort();if(screeningPoll)clearTimeout(screeningPoll);frozenRules?.dispose();loadSerial++;mcRun++;mcAbort?.abort();store.dispatch('result/load');observer.disconnect();for(const off of cleanup.reverse())off();host.dispose();aiFuel.dispose();buildingPanel.dispose();explore.dispose();results.dispose();display.dispose();shell.dispose();cache.clear();panel.remove();selectionLabel.remove();style.remove();legacyRoot.visible=legacyVisible;document.body.classList.toggle('cfbtReady',wasReady);if(panelHeight)document.documentElement.style.setProperty('--cfbt-height',panelHeight);else document.documentElement.style.removeProperty('--cfbt-height');}
 on(window,'pagehide',dispose);
 return Object.freeze({store,host,layers,render,install,dispose,diagnostics:()=>({ui:'modern',autoFit,case_id:chosen,canvasCount:$('v').querySelectorAll('canvas').length,legendCount:document.querySelectorAll('#cfMeaning').length})});
}
