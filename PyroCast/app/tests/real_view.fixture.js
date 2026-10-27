import * as T from '/vendor/three.module.js';
import './building.fixture.js';
import {createRealView} from '/simulation/viewer/legacy_real_bridge.js';
import {createRealViewLayers} from '../web/layers/real_view_layers.js';
import {readLegacyRealSource} from '../web/adapters/legacy_real.js';
import {createSceneHost} from '../web/scene/host.js';
const assert=(v,m)=>{if(!v)throw Error(m);},equal=(a,b,m)=>assert(JSON.stringify(a)===JSON.stringify(b),m);
function owned(root){const resources=new Set();root.traverse(o=>{if(o.geometry)resources.add(o.geometry);for(const m of Array.isArray(o.material)?o.material:o.material?[o.material]:[]){resources.add(m);for(const v of Object.values(m))if(v?.isTexture)resources.add(v);for(const u of Object.values(m.uniforms||{}))if(u.value?.isTexture)resources.add(u.value);}});return resources;}
function uniforms(root){const rows=[];root.traverse(o=>{if(!o.material?.uniforms)return;const u=o.material.uniforms;rows.push({order:o.renderOrder,visible:o.visible,time:u.uTime?.value,od:u.uOD?.value,opacity:u.uOpacity?.value,heat:u.uTemperatureSmoke?.value,layerTemp:u.uLayerTemp?.value,position:o.position.toArray(),scale:o.scale.toArray()});});return rows;}
window.realReady=(async()=>{
 await window.ready;const {B,hash,legacy,scene,reference,store,host,activeLayers}=window.buildingFixtureContext;
 const data=await fetch('/legacy/playback.json').then(r=>r.json()),before=JSON.stringify(data);assert(data.fire_key==='CAD_3F_R2_C0','Wrong initial fire');
 host.providePlumeLegend();assert(document.querySelectorAll('#cfMeaning').length===1,'Host did not supply legend anchor');
 const refParent=new T.Group();reference.add(refParent);const direct=createRealView({THREE:T,C:host.camera,groups:legacy.groups,B},data,refParent);
 // Keep the independent reference scene, but release its global legend ID before
 // mounting the wrapper. It uses the same host-provided legend while sampled.
 const refRoot=refParent.children[0];direct.detach();refParent.add(refRoot);
 const source=readLegacyRealSource({building:B,groups:legacy.groups,sourceHash:hash,data,resultId:'S09'});
 const layers=createRealViewLayers(T,{camera:host.camera,sourceFor:()=>source});for(const layer of layers){layer.mount(scene,store);activeLayers.push(layer);}
 const seq=store.dispatch('result/load');store.dispatch('result/receive',{seq,result:{schema:'fixture-result',result_id:'S09',t_end_s:3600}});
 store.dispatch('playback/seek',{t_s:1800});window.capture('layer','3F',false);
 const root=scene.getObjectByName('legacy-real-view-session');assert(root&&source.data===data,'Raw playback identity lost');
 const memoryBefore={...host.renderer.info.memory};const initialStats=layers[0].diagnostics();assert(initialStats.stats.flames.length>0&&initialStats.stats.volumeCount>0&&initialStats.stats.plume.gasVolumes>0,'Empty fire/smoke/plume fixture');
 const records={};
 window.captureReal=(which,name)=>{
  const smoke=name.startsWith('smoke-on'),plume=name.endsWith('plume-on');store.dispatch('layers/toggle',{id:'smoke',visible:smoke});store.dispatch('layers/toggle',{id:'plume',visible:plume});host.render();
  const args={enabled:true,time:store.get('playback').t_s,sample:a=>a?.[180]??0,floor:'3F',smokeEnabled:smoke,smokeOpacity:1,customRiskBoundaries:true,legacySmokeTexture:true,flameDisplay:'growth',plumesEnabled:plume,temperatureSmoke:true};
  direct.update(args);direct.animate(180000);equal(uniforms(root),uniforms(refRoot),'Shader uniforms/geometry differ');
  const active=uniforms(root).filter(r=>r.visible);assert(active.every(r=>r.time===180),'uTime does not follow fixed clock');
  records[name]={visible_smoke:active.filter(r=>r.order===10).length,visible_flame:active.filter(r=>r.order===20).length,visible_plume:active.filter(r=>r.order===15).length,uTime_seconds:[...new Set(active.map(r=>r.time))]};
  if(which==='baseline')host.renderer.render(reference,host.camera);else host.render();
 };
 window.checkReducedMotion=()=>{store.dispatch('layers/toggle',{id:'smoke',visible:true});store.dispatch('layers/toggle',{id:'plume',visible:true});host.render();
  const active=uniforms(root).filter(r=>r.visible);assert(active.every(r=>r.time===0),'Reduced-motion uniform not zero');assert(layers[0].diagnostics().lastAnimateMs===0,'Wrapper did not pass zero animation time');return true;};
 window.verifyReal=()=>{
  store.dispatch('realView/set',{enabled:false});host.render();assert(!root.children[0].visible,'Real view OFF ignored');
  store.dispatch('realView/set',{enabled:true,smokeOpacity:.4,temperatureSmoke:false});host.render();
  assert(uniforms(root).filter(r=>r.order===10).every(r=>r.opacity===.4&&r.heat===0),'Appearance settings not mapped');
  store.dispatch('layers/toggle',{id:'flame',visible:false});host.render();assert(uniforms(root).filter(r=>r.order===20).every(r=>!r.visible),'Flame OFF ignored');
  const smokeActive=uniforms(root).filter(r=>r.order===10&&r.visible).length;assert(smokeActive>0,'Flame toggle hid smoke');
  store.dispatch('layers/toggle',{id:'flame',visible:true});host.render();assert(uniforms(root).some(r=>r.order===20&&r.visible),'Flames not restored');
  store.dispatch('realView/set',{smokeOpacity:1,temperatureSmoke:true});host.render();
  const geometries=[];root.traverse(o=>{if(o.geometry)geometries.push(o.geometry);});
  const frame={building:store.get('building'),resultMeta:{...store.get('result')},t_s:1800,floor:store.get('floor'),layers:store.get('layers'),realView:store.get('realView'),reducedMotion:false};
  for(let i=0;i<500;i++)for(const layer of layers)layer.setData({...frame,selection:{room_id:String(i)}});
  assert(layers[0].diagnostics().builds===1,'Renderer rebuilt for stable input');const after=[];root.traverse(o=>{if(o.geometry)after.push(o.geometry);});assert(after.every((g,i)=>g===geometries[i]),'Geometry identity changed');
  const camera=store.get('camera');store.dispatch('floor/set',{floor_id:'2F'});host.render();assert(!root.children[0].children[0].visible,'3F smoke visible in 2F');equal(store.get('camera'),camera,'Floor changed camera');store.dispatch('floor/set',{floor_id:'3F'});host.render();
  assert(document.querySelectorAll('#cfPlumeLegend').length===1,'Duplicate legend');
  const stats=layers[0].diagnostics(),resources=owned(root);assert(resources.size===stats.resources,'Untracked resource');let freed=0;resources.forEach(r=>r.addEventListener('dispose',()=>freed++));
  const refResources=owned(refRoot);host.dispose();refResources.forEach(r=>r.dispose());refParent.removeFromParent();
  assert(freed===resources.size,'Legacy resources leaked');assert(!scene.getObjectByName('legacy-real-view-session'),'Legacy root retained');assert(!document.getElementById('cfMeaning')&&!document.getElementById('cfPlumeLegend'),'Legend retained');assert(store.diagnostics().subscriptions===0,'Subscription leak');equal(JSON.stringify(data),before,'Raw playback modified');
  // Verify the normal host mounting path also creates its required anchor before
  // the legacy module is invoked, without the fixture's explicit provision call.
  const nextLayers=createRealViewLayers(T,{camera:host.camera,sourceFor:()=>source});
  const nextHost=createSceneHost({container:document.querySelector('#scene'),THREE:T,store,camera:host.camera,layers:nextLayers,clock:{now:()=>180000}});
  nextHost.render();assert(document.querySelectorAll('#cfMeaning').length===1&&document.querySelectorAll('#cfPlumeLegend').length===1,'Automatic legend provisioning failed');
  nextHost.dispose();assert(!document.getElementById('cfMeaning')&&!document.getElementById('cfPlumeLegend'),'Remount legend leaked');
  assert(nextHost.renderer.info.memory.geometries===0&&nextHost.renderer.info.memory.textures===0,'Isolated real-view GPU leak');
  return {case_id:'S09',fire_key:data.fire_key,floor:'3F',playback_time_s:1800,clock_ms:180000,records,builds:stats.builds,unchanged_frames:500,raw_identity_preserved:true,raw_source_unchanged:true,appearance_mapping:true,independent_flame_toggle:true,floor_camera_unchanged:true,owned_resources:resources.size,disposed_resources:freed,remaining_resources:layers[0].diagnostics().resources,remaining_subscriptions:0,legend_removed:true,automatic_legend_remount:true,isolated_gpu_after:nextHost.renderer.info.memory,comparison_scene_memory_before:memoryBefore};
 };
 return true;
})();
