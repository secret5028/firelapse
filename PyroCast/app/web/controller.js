import {createModelReview} from './panels/model_review.js';
import {vehicleFitsGround} from './scene/vehicle_placement.js';
import {createAssistantPanel} from './panels/assistant.js';
import {attachExport} from './panels/export.js';
import {routeSampleIndex} from './route/risk.js';
import {readRouteGraph,contains} from './route/graph.js';
import {RouteLayer} from './layers/route.js';
import {createRoutePanel} from './panels/route.js';
import {createFuelSettingsPanel} from './panels/fuel_settings.js';
import {FuelQuantityLayer} from './layers/fuel_quantity.js';
import {createBuildingPanel,buildingTable} from './panels/building.js';
import {attachExplanations} from './panels/explanations.js';
import {createStore} from './state/store.js';
import {viewStorageKey,readSavedView,writeSavedView,restoredView} from './state/saved_view.js';
import {createSeriesCache} from './state/series_cache.js';
import {adaptBuilding,adaptResult,adaptScreening} from './adapters/read.js';
import {readLegacyBuildingSource} from './adapters/legacy_building.js';
import {readLegacyOpeningsSource} from './adapters/legacy_openings.js';
import {readLegacyCoreSource} from './adapters/legacy_core.js';
import {BuildingLayer} from './layers/building.js';
import {OpeningsLayer} from './layers/openings.js';
import {RoomNamesLayer} from './layers/room_names.js';
import {CoreLayer} from './layers/core.js';
import {createRealViewLayers} from './layers/real_view_layers.js';
import {RiskLayer} from './layers/risk.js';
import {SelectionLayer} from './layers/selection.js';
import {createSceneHost} from './scene/host.js';
import {createScaleReference} from './scene/scale_reference.js';
import {createLitePanel,updateLitePanel} from './panels/legacy_lite_panel.js';
import {createPanelShell} from './panels/shell.js';
import {createDisplayPanel} from './panels/display.js';
import {createResultsPanel,resultTypes,worstIndexEntries} from './panels/results.js';
import {latestRoomCases} from './panels/result_list.js';
import {createExplorePanel} from './panels/explore.js';
import {attachFrozenRules} from '/cfbt/frozen_rule_controls.js';

// One boundary: existing panel/CAD loader <-> pure store and display layers.
// HTTP boundary only; no solver or cache-key imports.
export async function attachModern(viewer,initial,{clock={now:()=>performance.now()}}={}){
 const {THREE:T,B,S,C,O,R,groups,shp,legacyRoot}=viewer;
 let viewStorage=null;try{if(!window.__PYROCAST_OFFLINE__)viewStorage=window.localStorage;}catch{}
 const viewKey=viewStorageKey(location.pathname,initial.building_sha256);
 let savedView=readSavedView(viewStorage,viewKey,initial.building_sha256),viewPersistenceReady=false,viewTimer=null;
 // The unchanged lite API rejects payloads from another building before serving.
 if(savedView?.case_id==='model-preview'&&!initial.model_preview)savedView=null;
 // Subsequent case installs must still match this initial server-validated hash.
 const legacyVisible=legacyRoot.visible,wasReady=document.body.classList.contains('cfbtReady'),panelHeight=document.documentElement.style.getPropertyValue('--cfbt-height');
 const {panel,$,selectionLabel,style}=createLitePanel();legacyRoot.visible=false;
 const cache=createSeriesCache(),store=createStore({seriesCache:cache,validators:{building:v=>v.schema==='pyrocast.building/1'&&!v.errors.length,result:v=>v.schema==='pyrocast.result/1'&&!v.errors.length,screening:v=>v.schema==='pyrocast.screening/1'&&!v.errors.length}});
 const displayFloors=[...B.floors].sort((a,b)=>(b.z??0)-(a.z??0));
 const shell=createPanelShell({panel,store,buildingFloors:displayFloors,onShowResult:async id=>{
  if(id===chosen){cancelCaseLoad();showResultOrigin();}else await loadSavedCase(id);
 }});
 const display=createDisplayPanel({store,selectionLabel,isOriginAllowed:room=>screeningPayload?.manual_origins?.some(r=>r.room===room),onOrigin:room=>{if(!screeningPayload?.manual_origins?.some(r=>r.room===room))return;store.dispatch('exploration/set',{origin_room_id:room,origin_mode:'manual'});$('shellTab-explore').click();}});
 const results=createResultsPanel({panel,store});
 const buildingAsset=readLegacyBuildingSource({building:B,groups,sourceHash:initial.building_sha256});
 const openingsAsset=readLegacyOpeningsSource({building:B,groups,sourceHash:initial.building_sha256});
 const coreAsset=readLegacyCoreSource({building:B,groups,sourceHash:initial.building_sha256,shapeFor:shp});
 const buildingLayer=new BuildingLayer(T,{geometryFor:()=>buildingAsset}),openings=new OpeningsLayer(T,{geometryFor:()=>openingsAsset,camera:C}),core=new CoreLayer(T,{geometryFor:()=>coreAsset,contextFloorsFor:()=>route.result?.segments?.map(s=>s.floor)||[]});
 let rawSource=null,data=null,selected=null,clicked=false,autoFit=false,chosen=initial.case_id||'stage4',disposed=false,ready=false,busy=false,last=0,fractional=0,lastFloor='',lastPanel='';
 const real=createRealViewLayers(T,{sourceFor:()=>rawSource,camera:C,fuelSymbols:true}),risk=new RiskLayer(T),selection=new SelectionLayer(T);
 let routeGraph;try{routeGraph=readRouteGraph(B);}catch(error){routeGraph={error:error.message,ground:{z:0,slab:[]},mainEntrance:null,defaultVehicle:null};}
 const referenceGroup=S.children.find(g=>g.children?.some(c=>c.type==='GridHelper')),existingReference=referenceGroup?.children.find(c=>c.isGroup&&c.userData.includeScalePerson);
 const ownedReference=existingReference?null:createScaleReference(T),vehicleSource=existingReference||ownedReference;
 // A scale reference remains visible when the entrance/route is unresolved.
 // This fallback is display-only; it does not invent an entrance or route.
 if(routeGraph.error){const ground=B.floors.find(f=>/^(1F|F1|1층)$/i.test(f.name))||B.floors[0],points=(ground.slab?.length?ground.slab:ground.rooms.flatMap(r=>r.polys||[])).flatMap(p=>p.o||p);
  if(points.length){const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]);routeGraph.ground={...ground,z:ground.z||0};routeGraph.defaultVehicle=[(Math.min(...xs)+Math.max(...xs))/2,Math.min(...ys)-15,ground.z||0];}
 }
 let routeUI=null;
 const route=new RouteLayer(T,{graph:routeGraph,vehicleSource,targetFor:()=>{const target=store.get('route').target_room_id;if(target)return target;const choice=store.get('exploration');if(choice.origin_mode==='manual'&&choice.origin_room_id)return choice.origin_room_id;if(data?.route_target_room_id)return data.route_target_room_id;const r=data?.rooms.find(r=>r.key===data.fire_key);return r?.original_room||r?.key||data?.fire_key;},onChange:r=>routeUI?.update(r)});
 const layers=[buildingLayer,openings,core,new RoomNamesLayer(T,{building:B,groups,camera:C,container:$('v')}),...real,new FuelQuantityLayer(T,B),risk,selection,route];
 const cleanup=[],originalRender=R.render,baseRender=R.render.bind(R);
 if(ownedReference)cleanup.push(()=>ownedReference.userData.dispose());
 let screeningPayload=null,screeningPoll=null,screeningRequest=0,screeningBusy=false,frozenRules=null,mcPoll=null,mcJobState=null,catalogSerial=0;
 const exploreAbort=new AbortController();
 let aiFuelRooms=null;
 const buildingPanel=createBuildingPanel({store});
 let fuelPreviewTimer=null;
 const fuelPanel=createFuelSettingsPanel({store,available:initial.engine_kind!=='cfast_native',onDraft:previewFuelRanking,onSaved:async()=>{clearTimeout(fuelPreviewTimer);await refreshScreening();await refreshFuelRooms();}});cleanup.push(()=>{clearTimeout(fuelPreviewTimer);fuelPanel.dispose();});
 function previewFuelRanking(current,draft){
  clearTimeout(fuelPreviewTimer);++screeningRequest;
  if(!Object.values(draft).some(rows=>Object.keys(rows).length)){refreshScreening();return;}
  explore.previewState('미저장 변경 · 순위 갱신 중…');
  fuelPreviewTimer=setTimeout(async()=>{
   const floor=store.get('floor').floor_id;if(!floor||disposed)return;const seq=++screeningRequest;
   try{
    const changes=Object.fromEntries(['floors','rooms'].map(scope=>[scope,Object.entries(draft[scope]||{}).map(([id,row])=>row?{id,...row}:{id,inherit:true})]));
    const response=await fetch('/cfbt/lite/fuel-settings',{method:'POST',signal:exploreAbort.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({building_sha256:current.building_sha256,revision:current.revision,preview_floor:floor,...changes})});
    const value=await response.json();if(!response.ok)throw Error(value.error||'순위 갱신 실패');if(disposed||seq!==screeningRequest)return;
    acceptScreening({...screeningPayload,score:value.score,preview:true});explore.previewState('미저장 변경 · 순위 미리보기');
   }catch(error){if(!disposed&&seq===screeningRequest)explore.previewState('순위 갱신 실패 · '+error.message);}
  },350);
 }
 async function refreshFuelRooms(){
  if(window.__PYROCAST_OFFLINE__)return;
  try{const response=await fetch('/cfbt/lite/ai/fuel',{signal:exploreAbort.signal});if(!response.ok)throw Error('HTTP '+response.status);const value=await response.json();if(!disposed&&Array.isArray(value.rooms)){aiFuelRooms=value.rooms;store.dispatch('buildingReview/set',{rooms:aiFuelRooms});}}
  catch(e){if(!disposed)store.dispatch('buildingReview/set',{status:'연료표 읽기 실패 · '+e.message});}
 }
 const assistant=createAssistantPanel({store,revealSidebar:shell.revealSidebar,available:viewer.capabilities?.assistant!==false,getContext:()=>({building:initial.building_sha256,case:chosen,floor:store.get('floor').floor_id,room:store.get('selection').room_id,origin:data?.route_target_room_id||data?.fire_key,time_s:store.get('playback').t_s,history:store.get('risk').history,vehicle:route.result?.vehicle,route_settings:{hose_m:store.get('route').hose_m,stair_factor:store.get('route').stair_factor}}),
  onNavigate:fact=>{if(fact.case!==chosen)throw Error('현재 사례와 다른 답변입니다. 해당 사례를 먼저 선택하세요.');const c=data.rooms.find(r=>r.key===fact.cell)||data.rooms.find(r=>(r.original_room||r.key)===fact.room);if(!c)return;viewer.setFloor(c.cad_floor);store.dispatch('floor/set',{floor_id:c.cad_floor});select(c.key);if(Number.isFinite(fact.time_s))store.dispatch('playback/seek',{t_s:fact.time_s});render();},
  onProposal:async(p,rooms,building)=>{if(building!==initial.building_sha256&&building!==(B.building_id||'cad-main'))throw Error('다른 건물 제안');if(p.kind==='mc'||p.kind==='screening'){store.dispatch('exploration/set',{origin_room_id:p.origin,origin_mode:'manual',...(p.samples?{samples:p.samples}:{}),...(p.N?{top_n:p.N}:{})});if(p.kind==='mc')await runMC();else await runScreening(true);return;}
   const path=p.kind==='openings'?'/cfbt/lite/fixed-openings':'/cfbt/lite/fuel-overrides',body=p.kind==='openings'?{assistant_proposal:p.proposal_id}:{proposal_id:p.proposal_id,rooms};const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const v=await response.json();if(!response.ok)throw Error(v.error||'적용 실패');await refreshDoors();await refreshScreening();await refreshFuelRooms();await fuelPanel.refresh();},onSaved:()=>assistant.refreshReports()});cleanup.push(()=>assistant.dispose());
 async function refreshDoors(){try{const response=await fetch('/cfbt/lite/doors',{signal:exploreAbort.signal});if(!response.ok)throw Error('HTTP '+response.status);const value=await response.json();if(!disposed)store.dispatch('buildingReview/set',{doors:value,status:''});}catch(e){if(!disposed)store.dispatch('buildingReview/set',{status:'문 목록 읽기 실패 · '+e.message});}}

 const explore=createExplorePanel({store,floors:displayFloors,onCandidate:row=>{store.dispatch('layers/toggle',{id:'selection',visible:true});store.dispatch('selection/set',{room_id:row.room,cell_id:null,source:'click'});},onFloor:id=>{if(id){viewer.setFloor(id);store.dispatch('floor/set',{floor_id:id});render();}},onApplyWorst:()=>{if(mcSummary?.worst)saveFixed({job_id:mcSummary.job_id},true);},onRun:()=>runScreening(),onRunOrigin:()=>runScreening(true),onRefresh:()=>{refreshScreening();refreshMC();},onMC:()=>runMC(),onCalculate:runCalculation,onCalculationResult:()=>openCalculation(),onResults:()=>{$('shellTab-result').click();$('resultMCLoad').scrollIntoView({block:'center'});if(!$('resultMCLoad').disabled)$('resultMCLoad').click();}});
 if(B.model_provenance?.import_id){const review=createModelReview({container:$('shellPane-building'),building:B,onLocate:x=>{const f=B.floors.find(f=>f.name===x.floor);if(!f)return;viewer.setFloor(f.name);store.dispatch('floor/set',{floor_id:f.name});const room=f.rooms.find(r=>r.id===x.id);if(room)store.dispatch('selection/set',{room_id:`CAD_${f.name}_${room.id}`,cell_id:null,source:'click'});render();}});review.root.open=false;review.root.style.cssText='margin:12px;font-size:11px';$('shellPane-building').append(review.root);cleanup.push(()=>review.dispose());}
 routeUI=createRoutePanel({store,graph:routeGraph});cleanup.push(()=>routeUI.dispose());$('exploreContent').append($('exploreCalculate'));
 async function refreshMC(){
  if(mcPoll)clearTimeout(mcPoll);mcPoll=null;
  try{const response=await fetch('/cfbt/lite/mc',{signal:exploreAbort.signal});if(!response.ok)throw Error('HTTP '+response.status);const value=await response.json();if(disposed)return;const previous=mcJobState;mcJobState=value;explore.mcState(value);
   if((previous?.running&&!value.running)||(value.state==='completed'&&(previous?.id!==value.id||previous?.state!=='completed')))await catalog();
   if(value.running||value.server_busy)mcPoll=setTimeout(refreshMC,3000);
  }catch(error){if(!disposed){explore.mcState({available:false,error:error.message});mcPoll=setTimeout(refreshMC,5000);}}
 }
 let mcStarting=false;
 async function runMC(){
  const selection=store.get('exploration');if(mcStarting||!selection.origin_room_id||!store.get('floor').floor_id||mcJobState?.running||mcJobState?.server_busy)return;mcStarting=true;const calculationKey=explore.calculationKey();explore.mcState(mcJobState||{available:true},true);
  try{const response=await fetch('/cfbt/lite/mc',{method:'POST',signal:exploreAbort.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({room:selection.origin_room_id,samples:selection.samples,duration_s:selection.duration_s,seed:20261025,manual:false,floor:store.get('floor').floor_id,selection_mode:selection.origin_mode==='manual'?'candidate':'score_first'})});const value=await response.json();if(!response.ok)throw Error(value.error||'HTTP '+response.status);if(!disposed){explore.mcSubmitted(value,calculationKey);await refreshMC();}}
  catch(error){if(!disposed)explore.mcState({...mcJobState,room:selection.origin_room_id,available:true,error:error.message});}finally{mcStarting=false;}
 }
 let calculationPoll=null,calculationState={available:false},calculationStarting=false;
 async function refreshCalculation(){
  if(calculationPoll)clearTimeout(calculationPoll);calculationPoll=null;
  if(window.__PYROCAST_OFFLINE__){explore.calculationState({available:false});return;}
  try{const r=await fetch('/cfbt/calculation',{signal:exploreAbort.signal});if(!r.ok)throw Error('실행 연결 없음');const value=await r.json();if(disposed)return;
   const previous=calculationState;calculationState=value;explore.calculationState(value);
   if(value.state==='complete'&&(previous.id!==value.id||previous.state!=='complete'))await catalog();
   if(value.running||value.server_busy)calculationPoll=setTimeout(refreshCalculation,3000);
  }catch(error){if(!disposed)explore.calculationState({available:false,error:error.message});}
 }
 async function runCalculation(engine,mcJobId,fire){
  if(calculationStarting||calculationState.running||disposed)return;calculationStarting=true;
  const choice=store.get('exploration');explore.calculationState({...calculationState,engine,error:null,started_at_ms:Date.now()},true);
  try{const r=await fetch('/cfbt/calculation',{method:'POST',signal:exploreAbort.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({engine,room:choice.origin_room_id,floor:store.get('floor').floor_id,duration_s:choice.duration_s,mc_job_id:mcJobId,...fire})});const value=await r.json();if(!r.ok)throw Error(value.error||'계산 요청 실패');await refreshCalculation();await refreshMC();}
  catch(error){if(!disposed)explore.calculationState({...calculationState,error:error.message});}
  finally{calculationStarting=false;}
 }
 async function openCalculation(){
  const id=calculationState.case_id;if(!id)return;
  try{await loadSavedCase(id);
  }catch(error){if(!disposed)explore.calculationState({...calculationState,error:error.message});}
 }
 cleanup.push(()=>{if(calculationPoll)clearTimeout(calculationPoll);});
 let catalogSelection=null;
 cleanup.push(store.subscribe('exploration',()=>{const {origin_room_id,duration_s}=store.get('exploration');const key=JSON.stringify([origin_room_id,duration_s]);if(key!==catalogSelection){catalogSelection=key;catalog().catch(error=>{if(!disposed)explore.status('결과 목록 읽기 실패 · '+error.message);});}}));
 const ruleOptions=()=>{const row=screeningPayload?.score.ranked.find(r=>r.room===store.get('exploration').origin_room_id);if(!row)throw Error('탐색 화점을 먼저 선택하세요.');return {fire_floor:row.floor,fire_room:row.room.replace('CAD_'+row.floor+'_',''),duration_s:data.time_s.at(-1)};};
 function ruleContext(){try{const o=ruleOptions();$('exploreRuleContext').textContent=`정밀 검토 · ${o.fire_floor} ${o.fire_room} · ${o.duration_s/60}분 · 문·창: 서버 기본값`;}catch{$('exploreRuleContext').textContent='탐색 화점 선택 대기';}}
 cleanup.push(store.subscribe('exploration',ruleContext));
 function acceptScreening(value){screeningPayload=value;lastPanel="";store.dispatch('buildingReview/set',{rooms:aiFuelRooms??buildingTable(value.score),openings:value.score.opening_states});store.dispatch('screening/set',adaptScreening({...value,buildingId:store.get('building').building_id,floorId:value.score.ranked[0]?.floor??null}));explore.update(value);ruleContext();if(screeningPoll){clearTimeout(screeningPoll);screeningPoll=null;}if(value.progress?.running)screeningPoll=setTimeout(()=>refreshScreening(),3000);}
 async function refreshScreening(){const floorId=store.get('floor').floor_id,wasRunning=screeningPayload?.progress?.running,seq=++screeningRequest;
  const currentOrigin=store.get('exploration').origin_room_id;if(!floorId||(currentOrigin&&!currentOrigin.startsWith('CAD_'+floorId+'_')))store.dispatch('exploration/set',{origin_room_id:null});
  const empty=message=>({available:false,unavailable_reason:message,score:{ranked:[],excluded:[],opening_states:[],approved_input:{}},manual_origins:[],comparison:null});
  if(!floorId){explore.update(empty('층 하나를 선택하세요'));return;}
  try{const response=await fetch('/cfbt/lite/screening?floor='+encodeURIComponent(floorId),{signal:exploreAbort.signal});if(!response.ok)throw Error((await response.json()).error||'HTTP '+response.status);let value=await response.json();
   if(!disposed&&seq===screeningRequest){value={...value,score:{...value.score,ranked:value.score.ranked.filter(r=>r.floor===floorId&&(r.origin_budget?.Q_origin_peak_kW??1)>0)},manual_origins:(value.manual_origins||[]).filter(r=>(r.floor??r.room?.split('_')[1])===floorId)};acceptScreening(value);if(wasRunning&&!value.progress?.running)await catalog();}
  }catch(error){if(!disposed&&seq===screeningRequest){explore.update(empty(error.message));explore.status('후보 계산 불가 · '+error.message);}}
 }

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
 function vehiclePositionAllowed(p,yaw=0){
  // Use the displayed ground grid, not an infinite plane or a basement floor.
  S.updateMatrixWorld(true);let bounds=null;
  S.traverse(o=>{if(o.type==='GridHelper'&&o.visible){const box=new T.Box3().setFromObject(o);if(Math.abs(box.min.z-routeGraph.ground.z)<1)bounds=box;}});
  return Math.abs(p[2]-routeGraph.ground.z)<.01&&vehicleFitsGround(p,bounds,routeGraph.ground.slab,yaw);
 }
 let vehicleAnchor=null,previewYaw=0,wasPlacing=false,orbitEnabled=O.enabled;
 function previewVehicle(p){
  if(!p){route.setVehiclePreview(null);return;}
  if(vehicleAnchor&&Math.hypot(p[0]-vehicleAnchor[0],p[1]-vehicleAnchor[1])>.1)previewYaw=Math.atan2(p[1]-vehicleAnchor[1],p[0]-vehicleAnchor[0]);
  const position=vehicleAnchor||p;route.setVehiclePreview(position,previewYaw,vehiclePositionAllowed(position,previewYaw));
 }
 cleanup.push(store.subscribe('route',s=>{
  if(s.placing&&!wasPlacing){vehicleAnchor=null;previewYaw=s.vehicle_yaw||0;orbitEnabled=O.enabled;O.enabled=false;route.setVehiclePreview(s.vehicle||routeGraph.defaultVehicle,previewYaw);}
  if(!s.placing&&wasPlacing){vehicleAnchor=null;route.setVehiclePreview(null);O.enabled=orbitEnabled;}
  wasPlacing=s.placing;
 }));cleanup.push(()=>{if(wasPlacing)O.enabled=orbitEnabled;});
 const host=createSceneHost({container:$('v'),THREE:T,store,scene:S,camera:C,layers,clock,adoptedRenderer:renderer,legendContainer:$('cfMeaning'),groundPick:{z:routeGraph.ground.z,active:()=>store.get('route').placing,hover:previewVehicle,place:p=>{
  previewVehicle(p);const position=vehicleAnchor||p;
  if(!vehiclePositionAllowed(position,previewYaw)){store.dispatch('route/set',{message:'차량 전체가 지상 그리드 안·건물 밖에 놓이도록 선택하세요'});return;}
  if(!vehicleAnchor){vehicleAnchor=[...p];store.dispatch('route/set',{message:'마우스로 방향 조절 · 클릭하여 확정 · Esc 취소'});}
  else store.dispatch('route/set',{vehicle:[...vehicleAnchor],vehicle_yaw:previewYaw,placing:false,message:''});
 }},vehiclePick:position=>routeUI?.showVehicleMenu(position),onRoomPick:openPickedRoom,seriesAt:()=>cache.get(store.get('result')?.result_id)});
 const on=(node,event,fn)=>{node.addEventListener(event,fn);cleanup.push(()=>node.removeEventListener(event,fn));};
 const handler=(node,event,fn)=>{const old=node[event];node[event]=fn;cleanup.push(()=>{node[event]=old;});};
 const name=r=>`${r.cad_floor} ${r.cad_room} · ${r.display_name||'용도 미확인'}`;
 const index=()=>Math.max(0,routeSampleIndex(data,store.get('playback').t_s));
 function recordCamera(mode){store.dispatch('camera/fit',{mode,target:O.target.toArray(),pose:{position:C.position.toArray(),quaternion:C.quaternion.toArray(),up:C.up.toArray(),zoom:C.zoom}});}
 function render(){if(!ready||busy||disposed)return;busy=true;try{
  const f=viewer.getFloor();if(f!==lastFloor){lastFloor=f;store.dispatch('floor/set',{floor_id:f==='all'?null:f});
   const selectedFloor=store.get('building')?.floors.find(row=>row.rooms.some(r=>r.room_id===store.get('selection').room_id));
   if(f!=='all'&&selectedFloor&&selectedFloor.floor_id!==f)store.dispatch('selection/set',{room_id:null,cell_id:null,source:'list'});
  }
  const parts=store.get('openings');openings.setPartVisible('window',parts.exterior);openings.setPartVisible('door',parts.interior);
  host.render();
  const signature=JSON.stringify([index(),selected?.key,store.get('selection'),clicked,store.get('playback').playing,f,store.get('realView'),store.get('layers'),store.get('openings'),store.get('risk')]);
  if(signature!==lastPanel){$('liteReal').setAttribute('aria-pressed',String(store.get('realView').enabled));updateLitePanel({data,index:index(),selected,clicked,playing:store.get('playback').playing,floor:f,$,selectionLabel,riskStatus:risk.summary()});const context={building:store.get('building'),result:store.get('result'),series:cache.get(store.get('result').result_id),index:index(),selection:store.get('selection'),fireInput:data.fire_input};display.hud(context);results.update(context);lastPanel=signature;}
 }finally{busy=false;}}
 // Display controls must update the GPU on input, including paused/throttled
 // animation loops in embedded or background viewers. Dispose owns this listener.
 cleanup.push(store.subscribe('realView',render));
 cleanup.push(store.subscribe('fuelSettings',render));
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
 function fitFloor(front=false){const rooms=data.rooms.filter(r=>viewer.getFloor()==='all'||r.cad_floor===viewer.getFloor());if(!rooms.length)return;
  const bounds=new T.Box3();
  if(viewer.getFloor()==='all'){for(const f of B.floors)for(const p of f.slab?.length?f.slab:f.rooms.flatMap(r=>r.polys||[]))for(const xy of p.o||p){bounds.expandByPoint(new T.Vector3(xy[0],xy[1],f.z));bounds.expandByPoint(new T.Vector3(xy[0],xy[1],f.z+f.h));}
   route.group?.updateWorldMatrix(true,true);for(const item of route.items||[])if(!item.route)bounds.union(new T.Box3().setFromObject(item.object));}
  else for(const r of rooms)for(const p of r.cad_polys)for(const xy of p.o){bounds.expandByPoint(new T.Vector3(xy[0],xy[1],r.z_m));bounds.expandByPoint(new T.Vector3(xy[0],xy[1],r.z_m+r.height_m));}
  const center=bounds.getCenter(new T.Vector3()),radius=bounds.getSize(new T.Vector3()).length()/2;
  const vertical=C.fov*Math.PI/180,horizontal=2*Math.atan(Math.tan(vertical/2)*C.aspect),distance=radius/Math.sin(Math.min(vertical,horizontal)/2)*1.05;
  O.target.copy(center);const direction=front&&routeGraph.front?new T.Vector3(...routeGraph.front,.7):new T.Vector3(1,-1,1.1);C.position.copy(center).add(direction.normalize().multiplyScalar(distance));O.update();recordCamera(viewer.getFloor()==='all'?'all':'floor');render();
 }
 for(const id of ['top','iso','resetView','zoomIn','zoomOut']){const button=$(id),old=button.onclick;handler(button,'onclick',function(e){old?.call(this,e);recordCamera(id==='top'?'top':id==='iso'||id==='resetView'?(viewer.getFloor()==='all'?'all':'floor'):store.get('camera').mode);render();});}
 for(const button of $('fbtn').querySelectorAll('button')){const old=button.onclick;handler(button,'onclick',function(e){const position=C.position.clone(),target=O.target.clone(),zoom=C.zoom;autoFit=false;old?.call(this,e);C.position.copy(position);O.target.copy(target);C.zoom=zoom;C.updateProjectionMatrix();O.update();store.dispatch('floor/set',{floor_id:viewer.getFloor()==='all'?null:viewer.getFloor()});recordCamera(store.get('camera').mode);render();});}
 on(R.domElement,'pointerdown',()=>{autoFit=false;});
 cleanup.push(store.subscribe('selection',s=>{if(!data)return;if(s.room_id)store.dispatch('route/set',{target_room_id:s.room_id});if(['click','touch'].includes(s.source))store.dispatch('layers/toggle',{id:'route',visible:true});const match=data.rooms.find(r=>r.key===s.cell_id)||data.rooms.find(r=>(r.original_room||r.key)===s.room_id);if(match){selected=match;$('liteRoom').value=selected.key;if(viewer.getFloor()!=='all'&&viewer.getFloor()!==selected.cad_floor)viewer.setFloor(selected.cad_floor);}if(s.source!=='list'||ready)clicked=true;render();}));
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
 // Every explicit result-open path selects that result's own origin. A CAD
 // room selected while browsing another floor must never leak into this action.
 function showResultOrigin(){
  const cell=data?.rooms.find(r=>r.key===data.fire_key);
  if(!cell)throw Error('계산 결과의 화점실 정보가 없습니다.');
  viewer.setFloor(cell.cad_floor);store.dispatch('floor/set',{floor_id:cell.cad_floor});
  store.dispatch('layers/toggle',{id:'selection',visible:true});
  if(data.native_mapping?.startsWith('fixed-r8-native-')){
   showPickedResult({room_id:cell.original_room||cell.key,cell_id:cell.key,source:'list'});
   fitFloor(true);saveView();return;
  }
  select(cell.key);shell.showResults();render();fitFloor(true);saveView();
 }
 function showPickedResult(selection){
  const {room_id,cell_id}=selection;
  const result=store.get('result'),series=cache.get(result.result_id);
  const cells=series?.rooms[room_id]?.source_cells;
  if(result.source_refs?.model_preview||!cells?.length)return false;
  const peaks=worstIndexEntries(result,cells).filter(p=>p.value>0&&Number.isFinite(p.time));
  peaks.sort((a,b)=>b.value-a.value||a.time-b.time);
  const peak=peaks[0],fallback=cells.includes(cell_id)?cell_id:cells[0];
  store.dispatch('playback/play',{playing:false});
  store.dispatch('playback/seek',{t_s:peak?.time??result.time_s.find(t=>t>0)??0});
  store.dispatch('selection/set',{...selection,cell_id:peak?.source??fallback});
  store.dispatch('layers/toggle',{id:'selection',visible:true});
  shell.showResults();render();saveView();
  return true;
 }
 async function install(payload,id,{focusOrigin=false,pick=null,isCurrent=()=>true}={}){
  if(payload.schema!=='pyrocast-cad-playback-1'||(!payload.complete&&!(payload===initial&&payload.model_preview===true&&id==='model-preview'))||payload.building_sha256!==initial.building_sha256)throw Error('다른 건물 또는 미완료 계산 결과입니다. 표시하지 않습니다.');
  const seq=store.dispatch('result/load'),byRoom=new Map();
  for(const c of payload.rooms){const key=c.original_room||c.key;if(byRoom.has(key))continue;const f=B.floors.find(f=>f.name===c.cad_floor),r=f?.rooms.find(r=>`CAD_${f.name}_${r.id}`===key);if(!r)throw Error('CAD room missing: '+key);
   byRoom.set(key,{id:key,name:r.names?.join(' / ')||key,cad_floor:c.cad_floor,cad_polys:r.polys,z_m:c.z_m,height_m:c.height_m});}
  // CAD selection is available beyond the saved calculation scope. These rooms
  // have geometry only: no synthetic solver cells or zero-valued time series.
  for(const f of B.floors)for(const r of f.rooms){const key=`CAD_${f.name}_${r.id}`;
   if(!byRoom.has(key))byRoom.set(key,{id:key,name:r.names?.join(' / ')||key,cad_floor:f.name,cad_polys:r.polys,z_m:f.z,height_m:f.h});}
  const scenario={rooms:[...byRoom.values()],openings:[],cad:{building_sha256:payload.building_sha256}};
  const building=adaptBuilding({scenario,playback:payload,sourceHash:payload.building_sha256}),result=await adaptResult({playback:payload,scenario,building,resultId:id});
  if(!isCurrent()||seq!==store.get('request').seq)return false;
  if(pick&&!result.rooms[pick.room_id]?.source_cells.length)throw Error('선택한 실의 저장 계산값이 없습니다.');
  ready=false;data=payload;chosen=id;store.dispatch('buildingReview/set',{playbackOpenings:payload.display_opening_state??null});rawSource={source_hash:payload.building_sha256,result_id:id,data:payload,B,groups};store.dispatch('building/set',building);store.dispatch('result/receive',{seq,result});
  $('liteRoom').replaceChildren();for(const r of data.rooms)$('liteRoom').add(new Option(name(r),r.key));
  selected=data.rooms.find(r=>r.key===data.fire_key)||data.rooms[0];clicked=false;store.dispatch('selection/set',{room_id:null,cell_id:null,source:'list'});$('liteTime').max=data.time_s.at(-1);$('liteTime').value=0;$('liteLimits').textContent=data.limits.join(' ');
  $('liteTime').step=data.output_step_s||10;
  for(const id of ['shellPlay','shellTime','litePlay','liteTime'])$(id).disabled=!!payload.model_preview;
  lastPanel='';ruleContext();ready=true;
  if(pick)showPickedResult(pick);
  else if(focusOrigin)showResultOrigin();
  else{viewer.setFloor(selected.cad_floor);render();fitFloor();}
  return true;
 }
 let mcSummary=null;
 async function saveFixed(body,playWorst=false){
  if(disposed||store.get('buildingReview').saving)return;
  const worstCase=mcSummary?.worst?.case_id;
  store.dispatch('buildingReview/set',{saving:true,status:'확정 급기 저장 중…'});
  $('resultMCApplyWorst').disabled=true;
  try{
   const response=await fetch('/cfbt/lite/fixed-openings',{method:'POST',signal:exploreAbort.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
   const value=await response.json();if(!response.ok)throw Error(value.error||'HTTP '+response.status);
   if(disposed)return;
   const rows=store.get('buildingReview').doors?.rows;
   store.dispatch('buildingReview/set',{doors:value.fixed_by_room?{...value,rows:rows??value.rows}:value,status:'이후 실행 입력 적용 · 현재 결과 유지'});
   if(value.fixed_state)store.dispatch('openings/set',{fixed:true});
   if(playWorst){const caseId=value.case_id||worstCase;if(!caseId)throw Error('최악 사례 ID 없음');const result=await fetch('/cfbt/lite/result/'+encodeURIComponent(caseId),{signal:exploreAbort.signal});if(!result.ok)throw Error('최악 재생 결과 읽기 실패');await install(await result.json(),caseId,{focusOrigin:true});}
   $('resultMCStatus').textContent=value.fixed_state?`표본 ${value.fixed_state.sample_id} 적용 완료`:'확정 급기 해제';
   await refreshScreening();await catalog();
   $('resultMCStatus').textContent=value.fixed_state?`표본 ${value.fixed_state.sample_id} 적용 완료`:'확정 급기 해제';
  }catch(error){
   if(!disposed){store.dispatch('buildingReview/set',{status:'확정 급기 저장 실패 · '+error.message});$('resultMCStatus').className='status-error';$('resultMCStatus').textContent=error.message;}
  }finally{
   if(!disposed){store.dispatch('buildingReview/set',{saving:false});$('resultMCApplyWorst').disabled=!mcSummary?.worst;}
  }
 }
 handler($('resultMCApplyWorst'),'onclick',()=>{if(mcSummary?.worst)saveFixed({job_id:mcSummary.job_id});});
 const reuseByCase=new Map();
 let casesByRoom=new Map(),coverageByRoom=new Map();
 const showReuse=value=>{$('resultReuse').dataset.caseId=value?.case_id||chosen;$('resultReuse').textContent=value?.label||'과거 결과 재사용';$('resultReuse').title=value?.equivalent?'저장 입력·엔진·계산 의존성 검증 일치':'현재 계산과의 동등성이 증명되지 않은 저장 결과';};
 handler($('resultReplay'),'onclick',async()=>{const id=chosen;$('resultReplay').disabled=true;try{const r=await fetch('/cfbt/reuse/lite/'+encodeURIComponent(id),{signal:exploreAbort.signal});const value=await r.json();if(!r.ok)throw Error(value.error||'재사용 실패');if(!disposed&&id===chosen){reuseByCase.set(id,value);showReuse(value);}}catch(e){if(!disposed)$('resultReuse').textContent='재사용 확인 실패 · '+e.message;}finally{if(!disposed)$('resultReplay').disabled=false;}});
 async function catalog(){const serial=++catalogSerial,{origin_room_id,duration_s}=store.get('exploration');const query=origin_room_id?'?'+new URLSearchParams({mc_room:origin_room_id,mc_duration_s:duration_s}):'';const r=await fetch('/cfbt/lite/catalog.json'+query,{signal:exploreAbort.signal});if(!r.ok)return;const c=await r.json();if(disposed||serial!==catalogSerial)return;mcSummary=c.mc_summary??null;casesByRoom=latestRoomCases(c.cases||[]);coverageByRoom=latestRoomCases(c.cases||[],entry=>entry.covered_room_ids||[]);shell.setResults(c.cases);$('liteCase').replaceChildren();for(const entry of c.cases||[])$('liteCase').add(new Option(entry.label,entry.id));$('liteCase').value=chosen;for(const [id,value] of Object.entries(c.reuse_by_case||{}))reuseByCase.set(id,value);showReuse(reuseByCase.get(chosen));$('liteMC').textContent=c.progress_text||'';results.mc(mcSummary,mcSummary?.rooms_max);
  if(!disposed&&serial===catalogSerial)explore.catalog(c,mcSummary?.source_room??null);
 }
 handler($('resultMCLoad'),'onclick',async()=>{if(!mcSummary)return;$('resultMCLoad').disabled=true;$('resultMCStatus').className='status-busy';
  try{await catalog();}catch(error){if(!disposed){$('resultMCStatus').className='status-error';$('resultMCStatus').textContent='집계 읽기 실패 · '+error.message;}}
  finally{if(!disposed)$('resultMCLoad').disabled=!mcSummary;}
 });
 let loadSerial=0;
 function cancelCaseLoad(){loadSerial++;$('resultReplay').disabled=false;}
 async function openPickedRoom(pick){
  const {room_id}=pick;
  if(!room_id||!ready||disposed)return;
  cancelCaseLoad();
  const completed=calculationState.state==='complete'&&calculationState.room===room_id?calculationState.case_id:null;
  let caseId=completed||casesByRoom.get(room_id)?.id;
  if((!caseId||caseId===chosen)&&showPickedResult(pick))return;
  if(!caseId||caseId===chosen)caseId=coverageByRoom.get(room_id)?.id;
  if(!caseId||caseId===chosen)return;
  const serial=loadSerial+1;
  try{await loadSavedCase(caseId,{pick});}
  catch(error){if(!disposed&&serial===loadSerial){shell.showResults();$('resultReuse').textContent='결과 읽기 실패 · '+error.message;}}
 }
 async function loadSavedCase(id,{pick=null}={}){const serial=++loadSerial;$('resultReplay').disabled=true;
  const isCurrent=()=>!disposed&&serial===loadSerial;
  try{const r=await fetch('/cfbt/lite/result/'+encodeURIComponent(id),{signal:exploreAbort.signal});if(!r.ok)throw Error('HTTP '+r.status);const payload=await r.json();if(disposed||serial!==loadSerial)return false;
   const installed=await install(payload,id,{focusOrigin:true,pick,isCurrent});if(installed&&isCurrent()){$('liteCase').value=id;showReuse(reuseByCase.get(id));}return installed;
  }finally{if(!disposed&&serial===loadSerial)$('resultReplay').disabled=false;}
 }
 handler($('liteRefresh'),'onclick',catalog);handler($('liteCase'),'onchange',()=>loadSavedCase($('liteCase').value).catch(error=>{if(!disposed)$('resultReuse').textContent='결과 읽기 실패 · '+error.message;}));
 let restored=false;
 if(savedView){try{
  let payload=initial;
  if(savedView.case_id!==chosen){const r=await fetch('/cfbt/lite/result/'+encodeURIComponent(savedView.case_id),{signal:exploreAbort.signal});if(!r.ok)throw Error('저장 결과 없음');payload=await r.json();}
  await install(payload,savedView.case_id);restored=true;
 }catch{savedView=null;try{viewStorage?.removeItem(viewKey);}catch{}}}
 if(!restored)await install(initial,initial.case_id||'stage4');
 if(data.model_preview)$('shellTab-building').click();
 viewer.setFloor('all');resize();fitFloor(true);
 if(restored){
  if(Array.isArray(savedView.vehicle)&&savedView.vehicle.length===3&&Number.isFinite(savedView.vehicle_yaw)&&vehiclePositionAllowed(savedView.vehicle,savedView.vehicle_yaw))store.dispatch('route/set',{vehicle:savedView.vehicle,vehicle_yaw:savedView.vehicle_yaw});
  const v=restoredView(savedView,store.get('building'),store.get('playback').t_end_s);
  store.dispatch('selection/set',v.selection);viewer.setFloor(v.floor??'all');store.dispatch('floor/set',{floor_id:v.floor});
  store.dispatch('playback/seek',{t_s:v.time_s});store.dispatch('playback/play',{playing:false});$('shellTab-'+v.tab).click();render();fitFloor(true);
 }
 await catalog();await refreshScreening();await refreshDoors();await refreshMC();await refreshCalculation();await refreshFuelRooms();
 cleanup.push(store.subscribe('floor',()=>{if(ready)refreshScreening();}));
 try{if(viewer.capabilities?.frozenRules===false){$('exploreRuleMount').textContent='현재 간략 규칙 사용 · 정밀 실행 연결 전';}else if(initial.engine_kind==='cfast_native'){$('exploreRuleMount').textContent='순정 CFAST 저장 입력 · 보기 전용';}else{frozenRules=await attachFrozenRules($('exploreRuleMount'),ruleOptions);const rules=$('cfbtFrozenRules');rules.open=true;}
  // The modern presentation boundary moves descriptions to accessible info tips.
 }catch(error){$('exploreRuleMount').textContent='규칙 설정 읽기 실패 · '+error.message;}
 document.body.classList.add('cfbtReady');resize();
 cleanup.push(attachExport({store,viewer,getCase:()=>chosen,getRoute:()=>({...route.result,risk_summary:route.riskDisplay}),render}));
 const explanations=attachExplanations();
 function dispose(){if(disposed)return;disposed=true;catalogSerial++;if(mcPoll)clearTimeout(mcPoll);explanations.dispose();screeningRequest++;exploreAbort.abort();if(screeningPoll)clearTimeout(screeningPoll);frozenRules?.dispose();loadSerial++;store.dispatch('result/load');observer.disconnect();for(const off of cleanup.reverse())off();host.dispose();buildingPanel.dispose();explore.dispose();results.dispose();display.dispose();shell.dispose();cache.clear();panel.remove();selectionLabel.remove();style.remove();legacyRoot.visible=legacyVisible;document.body.classList.toggle('cfbtReady',wasReady);if(panelHeight)document.documentElement.style.setProperty('--cfbt-height',panelHeight);else document.documentElement.style.removeProperty('--cfbt-height');}
 function saveView(){if(viewTimer!==null){clearTimeout(viewTimer);viewTimer=null;}if(!viewPersistenceReady||!ready||disposed)return;
  writeSavedView(viewStorage,viewKey,{hash:initial.building_sha256,case_id:chosen,floor:store.get('floor').floor_id,time_s:store.get('playback').t_s,
   vehicle:store.get('route').vehicle,vehicle_yaw:store.get('route').vehicle_yaw,selection:store.get('selection'),selection_explicit:clicked&&Boolean(store.get('selection').room_id),tab:$('pyroShellTabs').querySelector('[aria-selected="true"]')?.id.replace('shellTab-','')||'result'});
 }
 function scheduleView(){if(!viewPersistenceReady)return;if(viewTimer===null)viewTimer=setTimeout(saveView,300);}
 viewPersistenceReady=true;
 for(const slice of ['result','floor','selection','playback','route'])cleanup.push(store.subscribe(slice,scheduleView));
 on($('pyroShellTabs'),'click',scheduleView);on(document,'visibilitychange',()=>{if(document.hidden)saveView();});
 // Flush synchronously before the scene is disposed on refresh or navigation.
 on(window,'pagehide',saveView);cleanup.push(()=>{if(viewTimer!==null)clearTimeout(viewTimer);});saveView();
 on(window,'pagehide',dispose);
 return Object.freeze({store,host,layers,render,install,dispose,diagnostics:()=>({ui:'modern',autoFit,case_id:chosen,canvasCount:$('v').querySelectorAll('canvas').length,legendCount:document.querySelectorAll('#cfMeaning').length})});
}
