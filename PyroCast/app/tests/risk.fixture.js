import * as T from '/vendor/three.module.js';
import './building.fixture.js';
import {createRealView} from '/simulation/viewer/legacy_real_bridge.js';
import {createRealViewLayers} from '../web/layers/real_view_layers.js';
import {readLegacyRealSource} from '../web/adapters/legacy_real.js';
import {RiskLayer} from '../web/layers/risk.js';
import {displayV8Gates} from '../web/scene/render_order.js';
const assert=(v,m)=>{if(!v)throw Error(m);},equal=(a,b,m)=>assert(JSON.stringify(a)===JSON.stringify(b),m);
window.riskReady=(async()=>{
 await window.ready;const {B,viewer,hash,legacy,scene,reference,store,host,activeLayers,seriesCache}=window.buildingFixtureContext;
 const [data,building,result]=await Promise.all(['/legacy/playback.json','/adapted/building.json','/adapted/result.json'].map(p=>fetch(p).then(r=>r.json())));
 const before=JSON.stringify([building,result]);assert(data.fire_key==='CAD_3F_R2_C0','Wrong fire');
 store.dispatch('building/set',building);const seq=store.dispatch('result/load');store.dispatch('result/receive',{seq,result});
 store.dispatch('selection/set',{room_id:'CAD_3F_R2',cell_id:'CAD_3F_R2_C0',source:'list'});
 const refRoot=new T.Group();reference.add(refRoot);
 const jStart=viewer.indexOf('function joinedSelectionRibbons('),jEnd=viewer.indexOf('// Inventory of existing controls:',jStart);
 const joined=new Function(viewer.slice(jStart,jEnd)+';return joinedSelectionRibbons;')();
 const hStart=viewer.indexOf(' function selectionGeometry('),hEnd=viewer.indexOf(' function install(',hStart);
 const bStart=viewer.indexOf('for(const room of data.rooms){const group='),bEnd=viewer.indexOf('for(const u of data.fuel_symbols)',bStart);
 assert(hStart>0&&hEnd>hStart&&bEnd>bStart,'Legacy risk builder markers missing');
 const old=new Function('T','B','data','root','shp','joinedSelectionRibbons',viewer.slice(hStart,hEnd)+';const views=[],riskRooms=[];'+viewer.slice(bStart,bEnd)+';return {views,riskRooms};')(T,B,data,refRoot,legacy.shp,joined);
 const uStart=viewer.indexOf('const riskCounts={FO:0'),uEnd=viewer.indexOf('for(const {u,g} of units)',uStart);
 const oldUpdate=new Function('data','index','floor','selected','views','riskRooms','$',viewer.slice(uStart,uEnd)+';return riskCounts;');
 host.providePlumeLegend();const refReal=createRealView({THREE:T,C:host.camera,groups:legacy.groups,B},data,refRoot),refRealRoot=refRoot.children.at(-1);refReal.detach();refRoot.add(refRealRoot);
 const source=readLegacyRealSource({building:B,groups:legacy.groups,sourceHash:hash,data,resultId:'S09'});
 const realLayers=createRealViewLayers(T,{camera:host.camera,sourceFor:()=>source});for(const layer of realLayers){layer.mount(scene,store);activeLayers.push(layer);}
 const risk=new RiskLayer(T);risk.mount(scene,store);activeLayers.push(risk);window.capture('layer','3F',false);
 function props(o){return [o.visible,o.position.toArray(),o.renderOrder,o.material.color.getHex(),o.material.opacity,o.material.transparent,o.material.depthTest,o.material.depthWrite,o.material.gapSize??null];}
 function compareGeometry(a,b){equal([...a.geometry.attributes.position.array],[...b.geometry.attributes.position.array],'Risk geometry differs');}
 for(const v of risk.views){const ref=old.views.find(x=>x.room.key===v.id);for(const [key,oldKey] of [['tint','floor'],['line','line'],['interfaceLine','interfaceLine'],['interfacePlane','interfacePlane']])compareGeometry(v[key],ref[oldKey]);}
 for(const row of risk.rooms){const ref=old.riskRooms.find(x=>x.key===row.id);row.meshes.forEach((m,j)=>compareGeometry(m,ref.meshes[j]));}
 // Search the adapted payload only, not the raw result, for the first overlap.
 const roomCells=building.floors.flatMap(f=>f.rooms).map(r=>({id:r.room_id,cells:r.cells.map(c=>c.cell_id)}));let overlapTime=null,overlapRooms=[];
 for(let i=0;i<result.time_s.length&&overlapTime===null;i++)for(const room of roomCells){const active=new Set();
  for(const id of room.cells){const d=result.legacy_color[id],s=result.cells[id],g=displayV8Gates({color:d.color[i],smoke_stage:result.cell_conditions[id][i].smoke_stage,oxygen:s.O2_upper_volfrac[i],loc:d.LOC_vol_fraction,rollover_band:d.rollover_band[i]});for(const [k,v] of Object.entries(g))if(v)active.add(k);}
  if(active.size>1){overlapTime=result.time_s[i];overlapRooms.push({room_id:room.id,types:[...active]});}
 }
 assert(overlapTime!==null,'S09 has no overlapping ribbons');assert(overlapTime!==1800,'Additional overlap capture must differ');window.riskCaptureTimes=[1800,overlapTime];const records={};
 window.captureRisk=(which,time)=>{store.dispatch('playback/seek',{t_s:time});host.render();const index=data.time_s.indexOf(time);assert(index>=0,'Not an output sample');
  const counts=oldUpdate(data,index,'3F',data.rooms.find(r=>r.key===data.fire_key),old.views,old.riskRooms,()=>({checked:true,textContent:''}));
  // Selection ribbon belongs to the next layer, so exclude it from both scenes.
  old.views.forEach(v=>v.selection.visible=false);
  for(const v of risk.views){const ref=old.views.find(x=>x.room.key===v.id);equal(v.group.visible,ref.group.visible,'Cell floor visibility differs');for(const [k,ok] of [['tint','floor'],['line','line'],['interfaceLine','interfaceLine'],['interfacePlane','interfacePlane']])equal(props(v[k]),props(ref[ok]),'Cell display differs: '+v.id+'/'+k);}
  for(const row of risk.rooms){const ref=old.riskRooms.find(x=>x.key===row.id);row.meshes.forEach((m,j)=>equal(props(m),props(ref.meshes[j]),'Ribbon differs: '+row.id));}
  equal(risk.diagnostics().counts,counts,'Room OR counts differ');
  refReal.update({enabled:true,time,sample:a=>a?.[index]??0,floor:'3F',smokeEnabled:true,smokeOpacity:1,customRiskBoundaries:true,legacySmokeTexture:true,flameDisplay:'growth',plumesEnabled:true,temperatureSmoke:true});refReal.animate(180000);
  records[time]={counts:risk.counts,overlap:risk.activeRooms.filter(r=>r.types.length>1),status:risk.summary()};
  if(which==='baseline')host.renderer.render(reference,host.camera);else host.render();
 };
 window.verifyRisk=()=>{
  const frame={building:store.get('building'),resultMeta:store.get('result'),series:seriesCache.get('S09'),t_s:1800,floor:store.get('floor'),selection:store.get('selection'),risk:store.get('risk'),layers:store.get('layers')};
  // Throw on every shared condition criterion; only smoke_stage may be read.
  const forbidden=new Proxy({}, {get(){throw Error('Shared condition accessed');}});
  const guarded={...frame.resultMeta,conditions:forbidden,cell_conditions:Object.fromEntries(Object.entries(frame.resultMeta.cell_conditions).map(([id,timeline])=>[id,Object.fromEntries(Object.entries(timeline).map(([i,value])=>[i,new Proxy(value,{get(obj,key){if(key!=='smoke_stage')throw Error('Condition criterion accessed');return obj[key];}})]))]))};
  risk.setData({...frame,resultMeta:guarded});risk.tick();
  assert(!displayV8Gates({color:'#a855f7',smoke_stage:0,oxygen:.2,loc:.12,rollover_band:false}).FGI,'Colour-only FGI fallback remains');
  assert(!displayV8Gates({color:'#f97316',smoke_stage:0,oxygen:.2,loc:.12,rollover_band:false}).rollover,'Colour-only rollover fallback remains');
  assert(!displayV8Gates({color:'#facc15',smoke_stage:0,oxygen:.1,loc:.12,rollover_band:false}).backdraft,'Colour-only BD fallback remains');
  // Display-only synthetic samples cover types absent from the saved captures.
  const index=180,at=(values,value)=>values.map((x,i)=>i===index?value:x);
  const testMeta={...frame.resultMeta,legacy_color:{...frame.resultMeta.legacy_color},cell_conditions:{...frame.resultMeta.cell_conditions},boundary_by_cell:{...frame.resultMeta.boundary_by_cell}};
  const testSeries={...frame.series,cells:{...frame.series.cells}};
  function patch(id,{color='',stage=0,oxygen=.2,h=1,roll=false,boundary=false}={}){const d=frame.resultMeta.legacy_color[id],s=frame.series.cells[id];
   testMeta.legacy_color[id]={color:at(d.color,color),rollover_band:at(d.rollover_band,roll),LOC_vol_fraction:.12};
   testMeta.cell_conditions[id]={...frame.resultMeta.cell_conditions[id],[index]:{smoke_stage:stage}};
   testMeta.boundary_by_cell[id]=at(frame.resultMeta.boundary_by_cell[id],boundary);
   testSeries.cells[id]={...s,interface_m:at(s.interface_m,h),O2_upper_volfrac:at(s.O2_upper_volfrac,oxygen),legacy_optical:{...s.legacy_optical,ODu:at(s.legacy_optical.ODu,.5)}};
  }
  const multi=risk.rooms.find(r=>r.members.length>=2);multi.members.forEach(v=>patch(v.id));
  patch(multi.members[0].id,{color:'#ef4444',stage:2,oxygen:.12,h:1.2});patch(multi.members[1].id,{stage:2,oxygen:.1,h:.7,roll:true});
  const testFrame={...frame,resultMeta:testMeta,series:testSeries};risk.setData(testFrame);risk.tick();
  assert(multi.meshes.every(m=>m.visible),'Independent room OR lost a ribbon');
  multi.meshes.forEach((m,i)=>assert(Math.abs(m.position.z-(multi.members[0].meta.z_m+.7+i*.14))<1e-9,'Active member minimum height/offset changed'));
  assert(multi.members.every(v=>!v.line.visible),'Cell line visible beneath active room ribbons');
  const single=risk.rooms.find(r=>r.members.length===1&&!r.members[0].isCell),v=single.members[0];patch(v.id,{color:'#9ca3af',boundary:true});risk.setData(testFrame);risk.tick();
  assert(v.line.visible&&v.line.material.gapSize===.25&&v.tint.material.opacity===.025,'Grey boundary policy changed');
  patch(v.id);risk.setData({...testFrame,selection:{room_id:single.id,cell_id:v.id}});risk.tick();
  assert(v.interfaceLine.visible&&v.interfaceLine.material.color.getHexString()==='e7f2fa'&&v.interfacePlane.visible&&v.interfacePlane.material.opacity===.07&&v.tint.material.opacity===0,'Selected neutral smoke interface changed');
  risk.setData({...testFrame,selection:{room_id:single.id,cell_id:v.id},layers:{...frame.layers,smoke:false}});risk.tick();assert(!v.interfaceLine.visible&&!v.interfacePlane.visible,'Smoke OFF retained interface');
  const geometries=risk.views.map(v=>v.line.geometry);for(let i=0;i<500;i++)risk.setData({...frame,selection:{room_id:String(i),cell_id:null}});
  assert(risk.buildCount===1,'Risk geometry rebuilt');assert(risk.views.every((v,i)=>v.line.geometry===geometries[i]),'Geometry identity changed');
  const camera=store.get('camera');store.dispatch('floor/set',{floor_id:'2F'});host.render();assert(risk.rooms.every(r=>r.meshes.every(m=>!m.visible)),'Ribbon leaked to another floor');equal(store.get('camera'),camera,'Floor changed camera');store.dispatch('floor/set',{floor_id:'3F'});
  store.dispatch('risk/set',{type:'FO',visible:false});host.render();assert(risk.rooms.every(r=>!r.meshes[0].visible),'FO toggle ignored');store.dispatch('risk/set',{type:'FO',visible:true});host.render();
  const stats=risk.diagnostics(),resources=[...risk.resources];let disposed=0;resources.forEach(r=>r.addEventListener('dispose',()=>disposed++));host.dispose();
  assert(disposed===resources.length&&risk.resources.size===0,'Risk resources leaked');assert(store.diagnostics().subscriptions===0,'Subscriptions retained');equal(JSON.stringify([building,result]),before,'Adapted input changed');
  return {case_id:'S09',origin:'R2',floor:'3F',clock_ms:180000,capture_times:[1800,overlapTime],first_overlap:overlapRooms,records,rooms:stats.rooms,cells:stats.cells,builds:stats.buildCount,unchanged_frames:500,conditions_forbidden_test:true,strict_gates:true,synthetic_four_type_OR:true,synthetic_grey_and_selected_interface:true,adapted_inputs_only:true,geometry_materials_exact:true,owned_resources:resources.length,disposed_resources:disposed,remaining_resources:risk.resources.size,remaining_subscriptions:0};
 };
 window.riskFixtureContext={data,building,result,old,oldUpdate,refReal,refRoot,risk};
 return true;
})();
