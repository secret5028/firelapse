import {createStore} from './state/store.js';
import {createSeriesCache} from './state/series_cache.js';
import {adaptBuilding,adaptResult} from './adapters/read.js';
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

// One boundary: existing panel/CAD loader <-> pure store and display layers.
// No simulation, write API, cached-result key or solver imports.
export async function attachModern(viewer,initial,{clock={now:()=>performance.now()}}={}){
 const {THREE:T,B,S,C,O,R,groups,shp,legacyRoot}=viewer;
 // The unchanged lite API rejects payloads from another building before serving.
 // Subsequent case installs must still match this initial server-validated hash.
 const legacyVisible=legacyRoot.visible,wasReady=document.body.classList.contains('cfbtReady'),panelHeight=document.documentElement.style.getPropertyValue('--cfbt-height');
 const {panel,$,selectionLabel,style}=createLitePanel();legacyRoot.visible=false;
 const cache=createSeriesCache(),store=createStore({seriesCache:cache,validators:{building:v=>v.schema==='pyrocast.building/1'&&!v.errors.length,result:v=>v.schema==='pyrocast.result/1'&&!v.errors.length}});
 const shell=createPanelShell({panel,store});
 const display=createDisplayPanel({store,selectionLabel});
 const buildingAsset=readLegacyBuildingSource({building:B,groups,sourceHash:initial.building_sha256});
 const openingsAsset=readLegacyOpeningsSource({building:B,groups,sourceHash:initial.building_sha256});
 const coreAsset=readLegacyCoreSource({building:B,groups,sourceHash:initial.building_sha256,shapeFor:shp});
 const buildingLayer=new BuildingLayer(T,{geometryFor:()=>buildingAsset}),openings=new OpeningsLayer(T,{geometryFor:()=>openingsAsset,camera:C}),core=new CoreLayer(T,{geometryFor:()=>coreAsset});
 let rawSource=null,data=null,selected=null,clicked=false,autoFit=false,chosen=initial.case_id||'stage4',disposed=false,ready=false,busy=false,last=0,fractional=0,lastFloor='',lastPanel='';
 const real=createRealViewLayers(T,{sourceFor:()=>rawSource,camera:C,fuelSymbols:true}),risk=new RiskLayer(T),selection=new SelectionLayer(T);
 const layers=[buildingLayer,openings,core,...real,risk,selection];
 const cleanup=[],originalRender=R.render,baseRender=R.render.bind(R);
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
 const name=r=>`${r.cad_floor} ${r.cad_room} · ${r.display_name||(r.cad_names||[]).slice(0,2).join(' / ')}`;
 const index=()=>Math.min(data.time_s.length-1,Math.floor(store.get('playback').t_s/10));
 function recordCamera(mode){store.dispatch('camera/fit',{mode,target:O.target.toArray(),pose:{position:C.position.toArray(),quaternion:C.quaternion.toArray(),up:C.up.toArray(),zoom:C.zoom}});}
 function render(){if(!ready||busy||disposed)return;busy=true;try{
  const f=viewer.getFloor();if(f!==lastFloor){lastFloor=f;store.dispatch('floor/set',{floor_id:f==='all'?null:f});}
  const parts=store.get('openings');openings.setPartVisible('window',parts.exterior);openings.setPartVisible('door',parts.interior);
  syncOperations();
  host.render();
  const signature=JSON.stringify([index(),selected?.key,clicked,store.get('playback').playing,f,store.get('realView'),store.get('layers'),store.get('openings'),store.get('risk')]);
  if(signature!==lastPanel){updateLitePanel({data,index:index(),selected,clicked,playing:store.get('playback').playing,floor:f,$,selectionLabel,riskStatus:risk.summary()});display.hud({building:store.get('building'),result:store.get('result'),series:cache.get(store.get('result').result_id),index:index(),selection:store.get('selection')});shell.syncStatus();lastPanel=signature;}
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
  lastPanel='';ready=true;viewer.setFloor('3F');render();fitFloor();return true;
 }
 async function catalog(){const r=await fetch('/cfbt/lite/catalog.json');if(!r.ok)return;const c=await r.json();$('liteCase').replaceChildren();for(const entry of c.cases||[])$('liteCase').add(new Option(entry.label,entry.id));$('liteCase').value=chosen;$('liteMC').textContent=c.progress_text||'';
  $('liteMCTable').replaceChildren();$('liteMCSummary').hidden=!c.mc_summary;
  if(c.mc_summary){const add=text=>{const p=document.createElement('div');p.textContent=text;$('liteMCTable').append(p);};
   add(`완주 ${c.mc_summary.completed}/10 · 전체 ${c.mc_summary.wall_s.toFixed(1)}초 · 필수 2표본은 무작위 비율에서 제외`);
   for(const x of c.mc_summary.rows)add(`${x.id}: ${x.complete?`연소 ${x.burning}실 / 연기 위험 ${x.smoke_risk}실`:'미완료 · 안전 판정 불가'}`);
   for(const [key,name] of [['FO','FO'],['FGI','FGI'],['backdraft','백드래프트'],['rollover','롤오버']]){const q=c.mc_summary.rates[key];add(`${name} 조건: 무작위 완주 ${q.numerator}/${q.denominator_completed_random}표본`);}
   add('연기 위험은 2단계 색 규칙, 현상 조건은 공통 조건표 기준. 실제 발생확률이 아닙니다.');}}
 let loadSerial=0;
 handler($('liteRefresh'),'onclick',catalog);handler($('liteCase'),'onchange',async()=>{const serial=++loadSerial,id=$('liteCase').value,r=await fetch('/cfbt/lite/result/'+encodeURIComponent(id));if(r.ok){const payload=await r.json();if(serial===loadSerial)await install(payload,id);}});
 await install(initial,chosen);await catalog();const review=await createMenuReview(panel,viewer);review.hidden=true;handler($('liteReview'),'onclick',()=>{review.hidden=false;});document.body.classList.add('cfbtReady');resize();
 function dispose(){if(disposed)return;disposed=true;loadSerial++;store.dispatch('result/load');observer.disconnect();for(const off of cleanup.reverse())off();review.dispose();host.dispose();display.dispose();shell.dispose();cache.clear();panel.remove();selectionLabel.remove();style.remove();legacyRoot.visible=legacyVisible;document.body.classList.toggle('cfbtReady',wasReady);if(panelHeight)document.documentElement.style.setProperty('--cfbt-height',panelHeight);else document.documentElement.style.removeProperty('--cfbt-height');}
 on(window,'pagehide',dispose);
 return Object.freeze({store,host,layers,render,install,dispose,diagnostics:()=>({ui:'modern',autoFit,case_id:chosen,canvasCount:$('v').querySelectorAll('canvas').length,legendCount:document.querySelectorAll('#cfMeaning').length})});
}
