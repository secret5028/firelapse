import {createRealView} from '../../../simulation/viewer/legacy_real_bridge.js';

// One imported renderer owns interleaved smoke/flame/plume meshes. Three layer
// facades share this resource session, never refer to one another or duplicate it.
export function createRealViewSession(THREE,{sourceFor,camera,fuelSymbols=false}={}){
 if(typeof sourceFor!=='function'||!camera?.isCamera)throw Error('Raw playback source provider and host camera required');
 const session={root:null,renderer:null,source:null,building:undefined,result:undefined,users:0,builds:0,updates:0,lastAnimateMs:null,resources:new Set(),flames:[],lights:[],units:[]};
 function clear(){
  session.renderer?.detach();for(const resource of session.resources)resource.dispose();session.resources.clear();
  session.root?.clear();session.renderer=null;session.source=null;session.flames=[];session.lights=[];session.units=[];
 }
 function gather(){session.root.traverse(o=>{
  if(o.geometry)session.resources.add(o.geometry);
  for(const m of Array.isArray(o.material)?o.material:o.material?[o.material]:[]){session.resources.add(m);
   for(const value of Object.values(m))if(value?.isTexture)session.resources.add(value);
   for(const u of Object.values(m.uniforms||{}))if(u.value?.isTexture)session.resources.add(u.value);
   if(m.uniforms?.uFire?.value===1)session.flames.push(o);
  }
  if(o.isPointLight)session.lights.push(o);
 });}
 function setData(frame){
  if(frame.building!==session.building||frame.resultMeta!==session.result){
   const source=frame.building&&frame.resultMeta?sourceFor(frame.building,frame.resultMeta):null;
   if(frame.building&&frame.resultMeta&&(!source||source.source_hash!==frame.building.source_hash||source.result_id!==frame.resultMeta.result_id))throw Error('Missing/mismatched raw real-view source');
   if(source!==session.source){clear();if(source){session.source=source;
    try{
     if(fuelSymbols)for(const u of source.data.fuel_symbols||[]){const box=new THREE.BoxGeometry(.4,.4,.4),geometry=new THREE.EdgesGeometry(box);box.dispose();const g=new THREE.LineSegments(geometry,new THREE.LineBasicMaterial({color:'#a6b4ba',transparent:true,opacity:.55}));g.position.set(...u.position_m);g.raycast=()=>{};session.root.add(g);session.units.push({u,g});}
     session.renderer=createRealView({THREE,C:camera,groups:source.groups,B:source.B},source.data,session.root);gather();session.builds++;}
    catch(error){gather();clear();throw error;}
   }}session.building=frame.building;session.result=frame.resultMeta;
  }
 }
 function tick(frame,clock_s){if(!session.renderer)return;
  const {data}=session.source,settings=frame.realView,times=data.time_s;
  // Preserve the legacy output-grid sample, including the last sample at end.
  let lo=0,hi=times.length-1;while(lo<hi){const mid=Math.ceil((lo+hi)/2);if(times[mid]<=frame.t_s)lo=mid;else hi=mid-1;}
  const sample=a=>a?.[lo]??0;
  const enabled=settings.enabled&&(frame.layers.smoke||frame.layers.flame||frame.layers.plume);
  session.renderer.update({enabled,time:frame.t_s,sample,floor:frame.floor.floor_id??'all',
   smokeEnabled:frame.layers.smoke,smokeOpacity:settings.smokeOpacity,customRiskBoundaries:true,legacySmokeTexture:true,
   flameDisplay:'growth',plumesEnabled:frame.layers.plume,noiseAmp:settings.temperaturePattern==='weak'?.4:1,noiseScale:1,rampMode:settings.smokeColor==='neutral'?1:0,temperatureSmoke:settings.temperatureSmoke&&settings.temperaturePattern!=='off'});
  session.updates++;session.lastAnimateMs=frame.reducedMotion?0:clock_s*1000;
  session.renderer.animate(session.lastAnimateMs);
  for(const {u,g} of session.units){const r=data.rooms.find(r=>r.key===u.room);g.visible=frame.realView.fuelMarkers&&(frame.floor.floor_id===null||frame.floor.floor_id===r?.cad_floor);g.material.color.set(data.solvers[u.room]?.Qsolid_kW[lo]>0?'#ff8a3d':'#a6b4ba');}
  // The unchanged bridge hardcodes flamesEnabled=true. Mask only flame draw
  // objects/lights after update; no shader, HRR or geometry changes. Next update
  // restores native visibility before applying the checkbox again.
  if(!frame.layers.flame){for(const mesh of session.flames)mesh.visible=false;for(const light of session.lights)light.intensity=0;}
 }
 const created=new Set();
 return Object.freeze({createLayer(id){
 if(!['smoke','flame','plume'].includes(id)||created.has(id))throw Error('Invalid/duplicate real-view layer');created.add(id);
 return new class {
  static id=id;
  needsPlumeLegend=true;
  constructor(){this.state='new';this.frame=null;}
  mount(scene){if(this.state!=='new')throw Error('Layer cannot be mounted again');
   if(session.root&&session.root.parent!==scene)throw Error('Real-view layers require the same scene');this.state='mounted';
   if(!session.root){session.root=new THREE.Group();session.root.name='legacy-real-view-session';scene.add(session.root);}
   session.users++;
  }
  setData(frame){if(this.state!=='mounted')throw Error('Layer is not mounted');this.frame=frame;if(id==='smoke')setData(frame);}
  setVisible(value){this.visible=value;} // effective per-type switches come from frame.layers
  tick(dt_s,clock_s){if(id==='smoke'&&this.frame)tick(this.frame,clock_s);}
  diagnostics(){return {builds:session.builds,updates:session.updates,resources:session.resources.size,users:session.users,lastAnimateMs:session.lastAnimateMs,stats:session.renderer?.stats()??null};}
  dispose(){if(this.state!=='mounted')return;this.state='disposed';this.frame=null;if(--session.users===0){clear();session.root.removeFromParent();session.root=null;session.building=undefined;session.result=undefined;}}
 }();}});
}
