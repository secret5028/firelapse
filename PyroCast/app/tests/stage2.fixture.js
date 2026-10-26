import * as THREE from '/vendor/three.module.js';
import {createStore,legacyDispatchBridge} from '../web/state/store.js';
import {createSeriesCache} from '../web/state/series_cache.js';
import {createSceneHost} from '../web/scene/host.js';
import {createEmptyLayers} from '../web/layers/empty.js';
import {LABELS,RENDER_POLICY,riskHeight} from '../web/scene/render_order.js';
const ok=(value,msg)=>{if(!value)throw Error(msg);};
const equal=(a,b,msg)=>ok(JSON.stringify(a)===JSON.stringify(b),msg);
const throws=(fn,msg)=>{let caught=false;try{fn();}catch{caught=true;}ok(caught,msg);};
window.stage2Done=(async()=>{
 const hostEl=document.querySelector('#scene'),rows=[],seriesCache=createSeriesCache(),store=createStore({seriesCache,validators:{result:r=>r.schema==='fixture'}});
 document.querySelector('#label').textContent=LABELS.upperCombustion;
 let fetchCalls=0;const oldFetch=window.fetch;window.fetch=()=>{fetchCalls++;throw Error('Display must not fetch');};
 const add=window.addEventListener,remove=window.removeEventListener,live=[];
 const capture=o=>typeof o==='boolean'?o:Boolean(o?.capture);
 window.addEventListener=function(type,fn,opts){if(!live.some(x=>x.type===type&&x.fn===fn&&x.capture===capture(opts)))live.push({type,fn,capture:capture(opts)});return add.call(this,type,fn,opts);};
 window.removeEventListener=function(type,fn,opts){const i=live.findIndex(x=>x.type===type&&x.fn===fn&&x.capture===capture(opts));if(i>=0)live.splice(i,1);return remove.call(this,type,fn,opts);};
 try{
  store.dispatch('camera/fit',{mode:'room',target:[0,0,0],pose:{position:[8,-8,6],up:[0,0,1]}});
  const pose=store.get('camera');let cameraNotifications=0;const off=store.subscribe('camera',()=>cameraNotifications++);
  store.dispatch('floor/set',{floor_id:'3F'});equal(store.get('camera'),pose,'floor modified camera');ok(cameraNotifications===0,'camera subscriber fired on floor');off();
  throws(()=>{store.get('camera').pose.position[0]=99;},'snapshot not read-only');
  const seq1=store.dispatch('result/load'),seq2=store.dispatch('result/load');
  ok(store.dispatch('result/receive',{seq:seq1,result:{schema:'fixture',t_end_s:50}})===false,'stale response accepted');
  ok(store.dispatch('result/receive',{seq:seq2,result:{schema:'fixture',result_id:'fixture',t_end_s:100,cells:{C1:{T_upper_C:[20,100]}}}}),'current response rejected');
  ok(!('cells' in store.get('result')),'series retained in metadata store');
  equal(seriesCache.get('fixture').cells.C1.T_upper_C,[20,100],'series cache lost values');
  throws(()=>{seriesCache.get('fixture').cells.C1.T_upper_C[0]=99;},'series cache mutable');
  ok(store.get('playback').t_end_s===100,'result end missing');
  throws(()=>store.dispatch('result/receive',{seq:seq2,result:{schema:'invalid'}}),'contract validation bypass');
  ok(store.dispatch('jobs/start',{id:'a'}),'first job rejected');ok(!store.dispatch('jobs/start',{id:'b'}),'concurrent job accepted');
  ok(!store.dispatch('jobs/finish',{id:'b'}),'wrong job finished');store.dispatch('jobs/finish',{id:'a'});
  equal(Object.keys(legacyDispatchBridge(store)),['dispatch'],'legacy bridge has reader');
  ok(LABELS.upperCombustion==='상층 연소'&&!Object.values(LABELS).some(s=>/bulk/i.test(s)),'forbidden label');
  equal(Object.values(RENDER_POLICY).map(p=>p.order),[0,10,20,30,40,40,50,60,70],'render policy order');
  equal(['FO','FGI','backdraft','rollover','smoke'].map(t=>Math.round(riskHeight(0,t)*1000)),[20,35,50,65,80],'risk offsets');
  const scene=new THREE.Scene();let now=1000;
  for(let cycle=0;cycle<50;cycle++){
   const layers=createEmptyLayers(THREE),queue=new Map();let next=0;
   const host=createSceneHost({container:hostEl,THREE,store,scene,layers,clock:{now:()=>now},
    requestFrame:fn=>{queue.set(++next,fn);return next;},cancelFrame:id=>queue.delete(id)});
   const flush=()=>{const [id,fn]=queue.entries().next().value;queue.delete(id);fn();};
   ok(hostEl.querySelectorAll('canvas').length===1,'canvas count != 1');
   throws(()=>createSceneHost({container:hostEl,THREE,store}),'duplicate host accepted');
   const cameraBefore=host.camera.matrixWorld.toArray();store.dispatch('floor/set',{floor_id:cycle%2?'3F':'2F'});
   equal(host.camera.matrixWorld.toArray(),cameraBefore,'Three camera changed with floor');
   const phases=[];layers[0].tick=(dt,clock)=>phases.push([dt,clock]);
   let freed=0;const geometry=layers[0].own(new THREE.BoxGeometry(1,1,1));geometry.addEventListener('dispose',()=>freed++);
   const texture=layers[0].own(new THREE.DataTexture(new Uint8Array([255,255,255,255]),1,1));texture.needsUpdate=true;texture.addEventListener('dispose',()=>freed++);
   const material=layers[0].own(new THREE.MeshBasicMaterial({map:texture}));material.addEventListener('dispose',()=>freed++);
   layers[0].group.add(new THREE.Mesh(geometry,material));
   host.render();host.render();equal(phases.slice(-2),[[0,now/1000],[0,now/1000]],'fixed clock changed phase');
   ok(host.renderer.info.memory.geometries===1&&host.renderer.info.memory.textures===1,'GPU fixture not allocated');
   store.dispatch('layers/toggle',{id:'smoke',visible:false});host.render();ok(!layers[3].group.visible,'visibility not applied');
   store.dispatch('layers/toggle',{id:'smoke',visible:true});store.dispatch('risk/set',{type:'FO',visible:false});store.dispatch('risk/set',{type:'FO',visible:true});
   store.dispatch('floor/set',{floor_id:null});host.render();ok(layers[2].group.visible,'core hidden in all view');
   store.dispatch('floor/set',{floor_id:'3F'});host.render();ok(!layers[2].group.visible,'core visible in floor view');
   host.start();host.start();ok(queue.size===1,'more than one loop');flush();
   store.dispatch('playback/seek',{t_s:0});store.dispatch('playback/speed',{speed:5});store.dispatch('playback/play',{playing:true});
   now+=1000;flush();ok(store.get('playback').t_s===5,'playback clock not applied');
   host.stop();ok(queue.size===0,'stop retained callback');host.start();host.dispose();host.dispose();
   equal(scene.children.length,0,'scene children retained');ok(freed===3,'owned resources not disposed');
   const memory={...host.renderer.info.memory};ok(memory.geometries===0&&memory.textures===0,'GPU resources retained');
   ok(store.diagnostics().subscriptions===0,'store subscription leak');ok(live.length===0,'window listener leak');
   ok(queue.size===0,'RAF leak');ok(hostEl.querySelectorAll('canvas').length===0,'canvas leak');
   throws(()=>host.start(),'disposed host reused');throws(()=>layers[0].mount(scene,store),'disposed layer reused');
   rows.push({cycle:cycle+1,canvases:0,windowListeners:live.length,subscriptions:store.diagnostics().subscriptions,rafCallbacks:queue.size,sceneChildren:scene.children.length,geometries:memory.geometries,textures:memory.textures,resourcesDisposed:freed});
   // Allow the browser to process context loss between independent mounts.
   await new Promise(resolve=>setTimeout(resolve,0));
  }
  ok(fetchCalls===0,'display triggered fetch');
  seriesCache.clear();ok(seriesCache.size()===0,'series cache did not clear');
  const report={passed:true,three_revision:THREE.REVISION,cycles:50,floor_camera_unchanged:true,display_fetch_calls:fetchCalls,stale_response_discarded:true,single_job_policy:true,series_cache_separate:true,clock_injected:true,layer_reuse_rejected:true,upper_combustion_label:LABELS.upperCombustion,rows};
  document.querySelector('#report').textContent=JSON.stringify({...report,rows:'50/50 cycles: all retained counts zero'},null,2);return report;
 }finally{window.fetch=oldFetch;window.addEventListener=add;window.removeEventListener=remove;}
})();
