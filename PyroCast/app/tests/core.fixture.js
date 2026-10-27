import * as T from '/vendor/three.module.js';
import './building.fixture.js';
import {readLegacyCoreSource} from '../web/adapters/legacy_core.js';
import {CoreLayer} from '../web/layers/core.js';
const assert=(v,msg)=>{if(!v)throw Error(msg);},equal=(a,b,msg)=>assert(JSON.stringify(a)===JSON.stringify(b),msg);
window.coreReady=(async()=>{
 await window.ready;const {B,viewer,hash,legacy,scene,reference,store,host,activeLayers}=window.buildingFixtureContext;
 const before=JSON.stringify(B),source=readLegacyCoreSource({building:B,groups:legacy.groups,sourceHash:hash,shapeFor:legacy.shp});
 const begin=viewer.indexOf('const coreViews=[]'),end=viewer.indexOf('const selectionLabel=',begin);
 assert(begin>0&&end>begin,'Legacy core markers missing');
 const originalBuilder=new Function('T','B','groups','shp','coreOverlay',viewer.slice(begin,end)+';return coreViews;');
 const originalRoot=new T.Group();reference.add(originalRoot);const old=originalBuilder(T,B,legacy.groups,legacy.shp,originalRoot);
 const layer=new CoreLayer(T,{geometryFor:()=>source});layer.mount(scene,store);activeLayers.push(layer);host.render();
 function compare(actual,expected){equal(actual.children.length,expected.children.length,'Core object count differs');
  actual.children.forEach((object,i)=>{const ref=expected.children[i];
   equal(object.type,ref.type,'Object type differs');equal(object.position.toArray(),ref.position.toArray(),'Tread elevation differs');
   equal([...object.geometry.attributes.position.array],[...ref.geometry.attributes.position.array],'Core vertices differ');
   equal(object.geometry.index?[...object.geometry.index.array]:null,ref.geometry.index?[...ref.geometry.index.array]:null,'Core indices differ');
   const props=o=>[o.renderOrder,o.material.type,o.material.color.getHex(),o.material.opacity,o.material.transparent,o.material.depthTest,o.material.depthWrite,o.material.side];
   equal(props(object),props(ref),'Core material/order differs');
  });
 }
 for(let i=0;i<layer.views.length;i++)compare(layer.views[i].group,old[i].group);
 // Guard all three connectivity alternatives, missing footprints, and invalid treads.
 const footprint={o:[[0,0],[2,0],[2,2],[0,2]],h:[]},step={polys:[footprint],z0:0,z1:.2};
 const synthetic={floors:[{name:'fixture',h:3,transport:[
  {kind:'stair',anchor:[footprint]}, // not connected: exclude
  {kind:'elev',connected:true,region:[footprint]},
  {kind:'stair',to_floor:'2F',anchor:[footprint]},
  {kind:'stair',anchor:[footprint],meshes:[step,{polys:[],z0:0,z1:.2},{polys:[footprint],z0:1,z1:1}]},
  {kind:'ramp',connected:true,region:[footprint]},
  {kind:'stair',connected:true}, // no footprint: exclude
 ]}]};
 const sg=new T.Group();sg.name='fixture';const ss=readLegacyCoreSource({building:synthetic,groups:[sg],sourceHash:hash,shapeFor:legacy.shp});
 const check=new CoreLayer(T,{geometryFor:()=>ss});check.mount(new T.Scene(),store);check.setData({building:{source_hash:hash},floor:{floor_id:null}});
 const expectedRoot=new T.Group(),expected=originalBuilder(T,synthetic,[sg],legacy.shp,expectedRoot);compare(check.views[0].group,expected[0].group);
 equal(check.diagnostics().shells,3,'Connectivity filter failed');equal(check.diagnostics().treads,1,'Invalid tread included');check.dispose();
 expectedRoot.traverse(o=>{o.geometry?.dispose();o.material?.dispose();});
 const checkbox=document.querySelector('#coreToggle');host.listen(checkbox,'change',()=>store.dispatch('layers/toggle',{id:'core',visible:checkbox.checked}));
 const checked=value=>{checkbox.checked=value;checkbox.dispatchEvent(new Event('change'));host.render();};
 const cameraBefore=store.get('camera');
 for(const floor_id of [null,'3F'])for(const on of [false,true]){store.dispatch('floor/set',{floor_id});checked(on);assert(layer.group.visible===(floor_id===null&&on),'All-floor/checkbox AND gate failed');}
 equal(store.get('camera'),cameraBefore,'Floor/toggle changed camera');
 store.dispatch('floor/set',{floor_id:null});checked(true);
 const frame={building:store.get('building'),resultMeta:{id:'same'},floor:{floor_id:null}},objects=layer.views.flatMap(v=>v.group.children),geometries=objects.map(o=>o.geometry);
 for(let i=0;i<500;i++){layer.setData({...frame,t_s:i,selection:{room_id:String(i)}});layer.tick();}
 layer.setData({...frame,resultMeta:{id:'new'}});assert(layer.buildCount===1,'Static core rebuilt');objects.forEach((o,i)=>assert(o.geometry===geometries[i],'Core geometry replaced'));
 const view=layer.views.find(v=>v.group.children.length),oldZ=view.row.group.position.z;
 view.row.group.visible=false;view.row.group.position.z+=2;layer.tick();assert(!view.group.visible&&view.group.position.z===oldZ+2,'Source floor visibility/translation ignored');view.row.group.visible=true;view.row.group.position.z=oldZ;
 const originalCapture=window.capture;
 window.captureCore=(which,name)=>{originalCapture('layer',null,false);checked(name!=='all-off');
  if(name==='all-back'){const p=host.camera.position,target=store.get('camera').target;store.dispatch('camera/fit',{mode:'all',target,pose:{position:[2*target[0]-p.x,2*target[1]-p.y,p.z],up:[0,0,1]}});}
  host.render();originalRoot.visible=store.get('floor').floor_id===null&&checkbox.checked;
  for(const v of old){v.group.position.copy(legacy.groups[v.i].position);v.group.visible=legacy.groups[v.i].visible;}
  assert(layer.group.visible===originalRoot.visible,'Reference visibility differs');if(which==='baseline')host.renderer.render(reference,host.camera);else host.render();
 };
 window.verifyCore=()=>{const stats=layer.diagnostics(),owned=[...layer.resources];let disposed=0;owned.forEach(r=>r.addEventListener('dispose',()=>disposed++));
  host.dispose();assert(disposed===owned.length,'Core resources leaked');assert(layer.resources.size===0&&layer.views.length===0,'Retained core resources');assert(store.diagnostics().subscriptions===0,'Subscriptions leaked');equal(JSON.stringify(B),before,'CAD source mutated');
  return {...stats,transport_candidates:B.floors.reduce((n,f)=>n+(f.transport||[]).length,0),vertices_materials_match:true,connectivity_alternatives_and_invalid_treads:true,
   all_floor_checkbox_gate:true,camera_unchanged:true,unchanged_frames:500,source_visibility_translation:true,disposed_resources:disposed,remaining_resources:0,remaining_subscriptions:0,source_unchanged:true,clock_ms:180000};};
 return true;
})();
