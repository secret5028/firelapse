import * as T from '/vendor/three.module.js';
import './risk.fixture.js';
import {SelectionLayer} from '../web/layers/selection.js';
const assert=(v,m)=>{if(!v)throw Error(m);},equal=(a,b,m)=>assert(JSON.stringify(a)===JSON.stringify(b),m);
window.selectionReady=(async()=>{
 await window.riskReady;const {scene,reference,store,host,activeLayers,seriesCache}=window.buildingFixtureContext;
 const {data,building,old,oldUpdate,refReal}=window.riskFixtureContext;
 const layer=new SelectionLayer(T);layer.mount(scene,store);activeLayers.push(layer);store.dispatch('playback/seek',{t_s:1800});host.render();
 for(const v of layer.views){const ref=old.views.find(x=>x.room.key===v.id);
  equal([...v.ribbon.geometry.attributes.position.array],[...ref.selection.geometry.attributes.position.array],'Original-room ribbon geometry differs: '+v.id);
  equal([...v.pick.geometry.attributes.position.array],[...ref.floor.geometry.attributes.position.array],'Pick geometry differs');equal(v.pick.position.toArray(),ref.floor.position.toArray(),'Pick height differs');
  assert(v.pick.material.opacity===0&&v.pick.userData.liteRoom===v.id,'Invalid picking plane');
 }
 const r3=layer.views.find(v=>v.roomId==='CAD_3F_R3');assert(r3,'R3 cell absent');
 const cases={R2:{room_id:'CAD_3F_R2',cell_id:null,source:'list'},'R3-cell':{room_id:r3.roomId,cell_id:r3.id,source:'list'},none:{room_id:null,cell_id:null,source:'list'}};
 const records={};window.captureSelection=(which,name)=>{
  store.dispatch('selection/set',cases[name]);host.render();
  const selected=cases[name].cell_id?data.rooms.find(r=>r.key===cases[name].cell_id):data.rooms.find(r=>(r.original_room||r.key)===cases[name].room_id)||{key:null};
  oldUpdate(data,180,'3F',selected,old.views,old.riskRooms,()=>({checked:true,textContent:''}));
  const props=o=>[o.visible,o.renderOrder,o.material.color.getHex(),o.material.opacity,o.material.depthTest,o.material.depthWrite,o.material.transparent];
  for(const v of layer.views)equal(props(v.ribbon),props(old.views.find(x=>x.room.key===v.id).selection),'Selected ribbon state differs');
  refReal.update({enabled:true,time:1800,sample:a=>a?.[180]??0,floor:'3F',smokeEnabled:true,smokeOpacity:1,customRiskBoundaries:true,legacySmokeTexture:true,flameDisplay:'growth',plumesEnabled:true,temperatureSmoke:true});refReal.animate(180000);
  records[name]={selection:store.get('selection'),visible:layer.diagnostics().selectedCells};
  if(which==='baseline')host.renderer.render(reference,host.camera);else host.render();
 };
 // Pick an interior triangle centroid, not a polygon bounding-box centre that
 // could fall outside a concave room or inside a stair/column hole.
 function target(id=r3.id){host.render();scene.updateMatrixWorld(true);const v=layer.views.find(v=>v.id===id),g=v.pick.geometry,p=g.attributes.position,index=g.index;let best=-1,center;
  for(let i=0;i<(index?.count??p.count);i+=3){const vertices=[0,1,2].map(k=>new T.Vector3().fromBufferAttribute(p,index?index.getX(i+k):i+k));
   const area=vertices[1].clone().sub(vertices[0]).cross(vertices[2].clone().sub(vertices[0])).length();if(area>best){best=area;center=vertices[0].clone().add(vertices[1]).add(vertices[2]).multiplyScalar(1/3);}}
  const ndc=v.pick.localToWorld(center).project(host.camera),rect=host.renderer.domElement.getBoundingClientRect();return {x:rect.x+(ndc.x+1)/2*rect.width,y:rect.y+(1-ndc.y)/2*rect.height,id:v.id,roomId:v.roomId};
 }
 const clear=()=>{store.dispatch('selection/set',cases.none);host.render();};
 window.selectionTarget=()=>{store.dispatch('floor/set',{floor_id:'3F'});clear();return target();};
 window.checkNativePick=source=>{const s=store.get('selection');assert(s.cell_id===r3.id&&s.room_id===r3.roomId&&s.source===source,'Native pointer selection failed');return s;};
 window.verifySelection=()=>{
  const canvas=host.renderer.domElement,point=target(),camera=store.get('camera');
  function event(type,id=1,pointerType='mouse',dx=0,button=0){canvas.dispatchEvent(new PointerEvent(type,{pointerId:id,pointerType,button,clientX:point.x+dx,clientY:point.y,bubbles:true}));}
  function gesture(pointerType,distance,accepted){clear();event('pointerdown',1,pointerType);event('pointermove',1,pointerType,distance);event('pointerup',1,pointerType);
   assert((store.get('selection').cell_id===r3.id)===accepted,'Drag threshold failed: '+pointerType+'/'+distance);}
  gesture('mouse',5,true);gesture('mouse',5.01,false);gesture('touch',10,true);gesture('touch',10.01,false);
  clear();event('pointerdown');event('pointerup',1,'mouse',6);assert(!store.get('selection').cell_id,'Pointerup-only drag accepted');
  clear();event('pointerdown',1,'touch');event('pointerdown',2,'touch');event('pointerup',2,'touch');event('pointerup',1,'touch');assert(!store.get('selection').cell_id,'Multitouch selected');
  clear();event('pointerdown');event('pointercancel');event('pointerup');assert(!store.get('selection').cell_id,'Cancelled gesture selected');
  clear();event('pointerdown',1,'mouse',0,2);event('pointerup',1,'mouse',0,2);assert(!store.get('selection').cell_id,'Right button selected');
  clear();event('pointerdown');event('pointerup',2);event('pointercancel');assert(!store.get('selection').cell_id,'Wrong pointer ID selected');
  clear();store.dispatch('floor/set',{floor_id:'2F'});host.render();assert(layer.getPickPlanes().length===0,'Hidden floor pick targets exposed');event('pointerdown');event('pointerup');assert(!store.get('selection').cell_id,'Hidden floor selected');store.dispatch('floor/set',{floor_id:'3F'});host.render();
  clear();store.dispatch('layers/toggle',{id:'selection',visible:false});host.render();assert(layer.getPickPlanes().length===0,'Disabled selection pick targets exposed');event('pointerdown');event('pointerup');assert(!store.get('selection').cell_id,'Disabled selection picked');store.dispatch('layers/toggle',{id:'selection',visible:true});host.render();
  gesture('mouse',0,true);equal(store.get('camera'),camera,'Picking or floor changed camera');
  const r2cells=layer.views.filter(v=>v.roomId==='CAD_3F_R2');assert(r2cells.length>1,'No multi-cell R2');
  for(const v of r2cells){store.dispatch('selection/set',{room_id:v.roomId,cell_id:v.id,source:'list'});host.render();assert(layer.diagnostics().selectedCells.length===1,'Duplicate room ribbons');equal([...v.ribbon.geometry.attributes.position.array],[...r2cells[0].ribbon.geometry.attributes.position.array],'Cell selection drew cell boundary');}
  const geometries=layer.views.map(v=>v.ribbon.geometry),frame={building:store.get('building'),resultMeta:store.get('result'),floor:store.get('floor'),selection:store.get('selection')};
  for(let i=0;i<500;i++)layer.setData({...frame,resultMeta:i%2?frame.resultMeta:{...frame.resultMeta},selection:i%2?cases.none:cases.R2});assert(layer.buildCount===1&&layer.views.every((v,i)=>v.ribbon.geometry===geometries[i]),'Selection rebuilt geometry');
  assert(document.querySelectorAll('.cfbtSceneCaption').length===0,'Layer created label DOM');const stats=layer.diagnostics(),resources=[...layer.resources];let freed=0;resources.forEach(r=>r.addEventListener('dispose',()=>freed++));host.dispose();
  assert(freed===resources.length&&layer.resources.size===0,'Selection resources retained');assert(store.diagnostics().subscriptions===0,'Subscription leak');assert(!layer.getPickPlanes().length,'Disposed planes exposed');
  return {case_id:'S09',floor:'3F',origin:'R2',time_s:1800,clock_ms:180000,records,cells:stats.cells,buildCount:stats.buildCount,unchanged_frames:500,mouse_threshold_px:5,touch_threshold_px:10,threshold_edges_tested:true,multitouch_cancel:true,pointercancel:true,primary_button_only:true,hidden_floor_excluded:true,disabled_layer_excluded:true,original_room_for_each_R2_cell:true,camera_unchanged:true,no_layer_label_DOM:true,owned_resources:resources.length,disposed_resources:freed,remaining_resources:0,remaining_subscriptions:0};
 };
 return true;
})();
