import * as T from '/vendor/three.module.js';
import './building.fixture.js';
import {readLegacyOpeningsSource} from '../web/adapters/legacy_openings.js';
import {OpeningsLayer} from '../web/layers/openings.js';
import {exteriorWindowFace} from '../web/layers/openings_geometry.js';
const assert=(v,msg)=>{if(!v)throw Error(msg);},equal=(a,b,msg)=>assert(JSON.stringify(a)===JSON.stringify(b),msg);
window.openingsReady=(async()=>{
 await window.ready;const {B,viewer,hash,legacy,scene,reference,referenceGroups,store,host,activeLayers}=window.buildingFixtureContext;
 const source=readLegacyOpeningsSource({building:B,groups:legacy.groups,sourceHash:hash});const inputBefore=JSON.stringify(B);
 const start=viewer.indexOf('function exteriorWindowFace('),end=viewer.indexOf('// Closed, shared corner vertices:',start);
 const oldFace=new Function(viewer.slice(start,end)+';return exteriorWindowFace;')();
 const begin=viewer.indexOf('const exteriorOverlay=new T.Group()'),finish=viewer.indexOf("O.addEventListener('change',syncExteriorFacing)",begin);
 assert(start>0&&end>start&&begin>0&&finish>begin,'Legacy markers missing');
 const old=new Function('T','B','S','C','exteriorWindowFace',viewer.slice(begin,finish)+';return {exteriorViews,interiorViews,syncExteriorFacing,exteriorOverlay,interiorOverlay};')(T,B,reference,host.camera,oldFace);
 const layer=new OpeningsLayer(T,{geometryFor:()=>source,camera:host.camera});layer.mount(scene,store);activeLayers.push(layer);host.render();
 let candidates=0;for(const f of B.floors)for(const o of f.openings||[]){equal(exteriorWindowFace(f,o),oldFace(f,o),'Window filter/geometry mismatch');candidates++;}
 // Boundaries and exclusions are display filters, never scenario changes.
 const f=B.floors.find(f=>f.name==='3F'),valid=f.openings.find(o=>oldFace(f,o));assert(valid,'No 3F valid window fixture');
 for(const patch of [{span:.39},{span:3.02},{head:(valid.sill??f.sill)+2.41},{name:'테라스 난간'},{kind:'window_inner'},{connection_status:'interior',sides:[]}]){
  const o={...valid,...patch};assert(exteriorWindowFace(f,o)===null,'Invalid exterior window included');}
 for(const view of layer.views){const i=B.floors.findIndex(f=>f.name===view.row.id);
  for(const [kind,expected] of [['windows',old.exteriorViews[i].group],['doors',old.interiorViews[i].group]]){
   equal(view[kind].children.map(x=>x.name),expected.children.map(x=>x.name),'Opening names/count differ');
   view[kind].children.forEach((line,j)=>{const ref=expected.children[j];equal([...line.geometry.attributes.position.array],[...ref.geometry.attributes.position.array],'Opening vertices differ');
    equal([line.renderOrder,line.material.color.getHex(),line.material.opacity,line.material.transparent,line.material.depthTest,line.material.depthWrite],
     [ref.renderOrder,ref.material.color.getHex(),ref.material.opacity,ref.material.transparent,ref.material.depthTest,ref.material.depthWrite],'Render policy differs');
   });
  }
 }
 const frame={building:store.get('building'),resultMeta:{id:'same'},floor:{floor_id:'3F'}},objects=layer.views.flatMap(v=>[...v.windows.children,...v.doors.children]),geometries=objects.map(o=>o.geometry);
 for(let i=0;i<500;i++){layer.setData({...frame,t_s:i,selection:{room_id:String(i)}});layer.tick(0,180);}
 layer.setData({...frame,resultMeta:{id:'changed'}});assert(layer.buildCount===1,'Metadata/time rebuilt geometry');objects.forEach((o,i)=>assert(o.geometry===geometries[i],'Geometry identity changed'));
 const view=layer.views.find(v=>v.row.id==='3F'),line=view.windows.children[0],center=line.userData.exteriorCenter.clone().add(view.windows.position),normal=line.userData.exteriorNormal;
 // Deliberately no camera/fit dispatch and no OrbitControls change event.
 host.camera.position.copy(center).addScaledVector(normal,5);layer.tick();assert(line.visible,'Front facade hidden');
 host.camera.position.copy(center).addScaledVector(normal,-5);layer.tick();assert(!line.visible,'Back facade visible');
 const beforeChecks=layer.windowChecks;layer.tick();assert(layer.windowChecks-beforeChecks===layer.diagnostics().windows,'Not every window tested per tick');
 view.row.group.visible=false;layer.tick();assert(!view.windows.visible&&!view.doors.visible,'Source floor visibility ignored');view.row.group.visible=true;
 layer.setPartVisible('window',false);layer.tick();assert(!view.windows.visible&&view.doors.visible,'Independent window toggle failed');layer.setPartVisible('window',true);
 layer.setPartVisible('door',false);layer.tick();assert(!view.doors.visible,'Door toggle failed');layer.setPartVisible('door',true);
 const oldZ=view.row.group.position.z;view.row.group.position.z+=2;layer.tick();assert(view.windows.position.z===oldZ+2&&view.doors.position.z===oldZ+2,'Floor transform not followed');view.row.group.position.z=oldZ;
 const originalCapture=window.capture,visibility={};
 window.captureOpenings=(which,name)=>{
  originalCapture('layer','3F',name==='top');
  if(name==='back'){const p=host.camera.position,target=store.get('camera').target;store.dispatch('camera/fit',{mode:'floor',target,pose:{position:[2*target[0]-p.x,2*target[1]-p.y,p.z],up:[0,0,1]}});}
  host.render();for(const v of old.exteriorViews){v.group.position.copy(legacy.groups[v.i].position);v.group.visible=legacy.groups[v.i].visible&&B.floors[v.i].name==='3F';}
  for(const v of old.interiorViews){v.group.position.copy(legacy.groups[v.i].position);v.group.visible=legacy.groups[v.i].visible&&B.floors[v.i].name==='3F';}old.syncExteriorFacing();
  const i=B.floors.findIndex(f=>f.name==='3F');equal(view.windows.children.map(l=>l.visible),old.exteriorViews[i].group.children.map(l=>l.visible),'Facing flags differ');
  visibility[name]={windows_shown:view.windows.children.filter(l=>l.visible).map(l=>l.name),window_count:view.windows.children.length,door_lines:view.doors.children.length};
  if(which==='baseline')host.renderer.render(reference,host.camera);else host.render();
 };
 window.verifyOpenings=()=>{const stats=layer.diagnostics(),owned=[...layer.resources];let disposed=0;owned.forEach(r=>r.addEventListener('dispose',()=>disposed++));
  host.dispose();assert(disposed===owned.length,'Owned opening resources leaked');assert(layer.resources.size===0&&layer.views.length===0,'Layer retains resources');
  assert(store.diagnostics().subscriptions===0,'Subscriptions leaked');equal(JSON.stringify(B),inputBefore,'CAD source mutated');
  return {...stats,candidates_compared:candidates,all_vertices_and_materials_match:true,unchanged_frames:500,camera_tick_without_event:true,all_windows_checked_each_tick:true,
   independent_part_toggles:true,source_visibility_and_translation_followed:true,disposed_resources:disposed,remaining_resources:layer.resources.size,remaining_subscriptions:store.diagnostics().subscriptions,visibility,source_unchanged:true};};
 return true;
})();
