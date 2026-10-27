import * as T from '/vendor/three.module.js';
import {readLegacyBuildingSource} from '../web/adapters/legacy_building.js';
import {BuildingLayer} from '../web/layers/building.js';
import {createSceneHost} from '../web/scene/host.js';
import {createStore} from '../web/state/store.js';
import {applyRenderPolicy,RENDER_POLICY,riskHeight,displayV8Gates} from '../web/scene/render_order.js';
const assert=(v,msg)=>{if(!v)throw Error(msg);};
window.ready=(async()=>{
 const [B,model,viewer,hash]=await Promise.all([fetch('/legacy/building.json').then(r=>r.json()),fetch('/legacy/model.txt').then(r=>r.text()),fetch('/legacy/viewer.txt').then(r=>r.text()),fetch('/legacy/hash.txt').then(r=>r.text())]);
 const start=model.indexOf('const mat='),end=model.indexOf('// ---- 문짝',start);assert(start>0&&end>start,'Legacy builder markers missing');
 const oldScene=new T.Scene();class Label extends T.Object3D{}
 // Execute the unchanged geometry construction block, not a reimplementation.
 const legacy=new Function('THREE','B','S','CSS2DObject','dark','ceilStateDefault','applyCeil',model.slice(start,end)+';return {groups,mat,ceilState,shp};')
  (T,B,oldScene,Label,true,f=>Math.min(f.h-.3,Math.max(f.ceil_rule?.min_h||2.4,f.h-(f.ceil_rule?.plenum||1))),()=>{});
 const XR=['wall','door_head','win_low','win_head','beam'];
 for(const k of XR){Object.assign(legacy.mat[k],{opacity:.45,transparent:true,depthWrite:false,side:T.DoubleSide});}
 legacy.groups.forEach((g,i)=>{for(const m of [...g.children])if(m.isMesh&&XR.some(k=>m.material===legacy.mat[k])){
  const edge=new T.LineSegments(new T.EdgesGeometry(m.geometry,30),new T.LineBasicMaterial({color:0x9bb8c9,transparent:true,opacity:.45}));edge.userData.cadOutline=true;g.add(edge);
 }const st=legacy.ceilState[i];if(st.mesh){st.mesh.position.z=st.h;st.mesh.visible=st.on;}if(st.on&&B.floors[i].beams==='above_ceiling')st.beams.forEach(m=>m.visible=false);});
 const asset=readLegacyBuildingSource({building:B,groups:legacy.groups,sourceHash:hash});
 const original=asset.floors.flatMap(f=>f.objects).map(o=>({o,mat:o.material,color:o.material.color?.getHex(),opacity:o.material.opacity,geo:o.geometry}));
 const reference=new T.Scene(),referenceGroups=[];
 for(const f of asset.floors){const g=new T.Group();g.name=f.id;g.position.copy(f.group.position);for(const src of f.objects){const o=src.clone(false);o.material=src.material.clone();g.add(o);}reference.add(g);referenceGroups.push(g);}
 const colourStart=viewer.indexOf('for(const f of B.floors)groups.find'),colourEnd=viewer.indexOf('for(const room of data.rooms)',colourStart);
 assert(colourStart>0&&colourEnd>colourStart,'Legacy install colour block missing');
 new Function('B','groups',viewer.slice(colourStart,colourEnd))(B,referenceGroups);
 const light=scene=>{scene.background=new T.Color('#0c1c29');scene.add(new T.HemisphereLight(0xffffff,0x666666,1.6));const d=new T.DirectionalLight(0xffffff,1.4);d.position.set(40,-60,90);scene.add(d);};
 light(reference);const scene=new T.Scene();light(scene);
 const store=createStore({validators:{building:v=>v.schema==='fixture'}}),layer=new BuildingLayer(T,{geometryFor:()=>asset});
 store.dispatch('building/set',{schema:'fixture',source_hash:hash});
 const activeLayers=[layer];
 const host=createSceneHost({container:document.querySelector('#scene'),THREE:T,store,scene,layers:activeLayers,clock:{now:()=>180000}});
 const meta={id:'unchanged'},frame={building:store.get('building'),resultMeta:meta,floor:{floor_id:'3F'}};
 host.render();const buildCount=layer.buildCount,identities=[...layer.floorGroups.values()].flatMap(g=>g.children).map(o=>[o,o.geometry,o.material]);
 for(let i=0;i<500;i++)layer.setData({...frame,t_s:i*10,selection:{room_id:'R'+i%3}});
 layer.setData({...frame,resultMeta:{id:'new-result'}});assert(layer.buildCount===buildCount,'Static geometry rebuilt');
 identities.forEach(([o,g,m])=>assert(o.geometry===g&&o.material===m,'Object resource identity changed'));
 let policyCount=0;for(const g of layer.floorGroups.values())for(const o of g.children){assert(o.renderOrder===0,'Draw object policy missing');policyCount++;}
 let groupRejected=false;try{applyRenderPolicy(new T.Group(),'risk');}catch{groupRejected=true;}assert(groupRejected,'Group accepted');
 for(const key of ['risk','selection','openings.door']){const m=new T.LineBasicMaterial(),line=new T.Line(new T.BufferGeometry(),m);applyRenderPolicy(line,key);assert(m.transparent&&m.opacity===RENDER_POLICY[key].opacity&&!m.depthTest&&!m.depthWrite,'Transparent overlay policy');m.dispose();line.geometry.dispose();}
 assert(Math.abs(riskHeight(16.1,3,[1,1.5],'rollover')-17.52)<1e-9,'Smoke-interface ribbon height changed');
 const gates=displayV8Gates({color:'#ef4444',smoke_stage:2,oxygen:.15,loc:.12,rollover_band:true,conditions:{FGI:{met:false}}});
 assert(gates.FO&&gates.FGI&&gates.rollover&&!gates.backdraft,'v8 independent gates replaced by shared conditions');
 function pose(floor,top){store.dispatch('floor/set',{floor_id:floor});host.render();for(const g of referenceGroups)g.visible=floor===null||g.name===floor;
  const box=new T.Box3();for(const g of layer.floorGroups.values())if(g.visible)box.union(new T.Box3().setFromObject(g));const center=box.getCenter(new T.Vector3()),size=box.getSize(new T.Vector3()),d=Math.max(size.x,size.y,size.z)*1.22;
  store.dispatch('camera/fit',{mode:top?'top':floor?'floor':'all',target:center.toArray(),pose:{position:top?[center.x,center.y-.01,center.z+d*1.4]:[center.x+d*.7,center.y-d,center.z+d*.9],up:[0,0,1]}});host.render();
 }
 window.capture=(which,floor,top=false)=>{pose(floor,top);if(which==='baseline')host.renderer.render(reference,host.camera);else host.render();};
 window.verify=()=>{let sourcePreserved=true;for(const r of original)sourcePreserved&&=r.o.material===r.mat&&r.mat.color?.getHex()===r.color&&r.mat.opacity===r.opacity&&r.o.geometry===r.geo;
  const sourceGeometries=new Set(original.map(r=>r.geo));let sourceDisposed=0;for(const g of sourceGeometries)g.addEventListener('dispose',()=>sourceDisposed++);
  const matCount=layer.resources.size;let materialsDisposed=0;for(const m of layer.resources)m.addEventListener('dispose',()=>materialsDisposed++);
  host.dispose();assert(layer.resources.size===0&&materialsDisposed===matCount,'Owned materials leaked');assert(sourceDisposed===0,'Borrowed geometry disposed');assert(sourcePreserved,'Source material changed');
  return {sourcePreserved,borrowed_geometry_disposals:sourceDisposed,materials_disposed:materialsDisposed,building_objects:policyCount,builds:buildCount,unchanged_frames:500,result_change_rebuilt:false,floors:asset.floors.length,clock_ms:180000,group_policy_rejected:groupRejected,subscriptions:store.diagnostics().subscriptions};};
 window.buildingFixtureContext={B,viewer,hash,legacy,asset,scene,reference,referenceGroups,store,host,activeLayers};
 return true;
})();
