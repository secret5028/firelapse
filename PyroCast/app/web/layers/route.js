import {ROOM_PICK_LAYER} from '../scene/picking.js';
import {EmptyLayer} from './empty.js';
import {findRoute} from '../route/graph.js';
import {routeRiskRows,routeSampleIndex} from '../route/risk.js';
export class RouteLayer extends EmptyLayer {
 static id='route';
 constructor(T,{graph,targetFor,vehicleSource,onChange}){super(T);Object.assign(this,{graph,targetFor,vehicleSource,onChange});this.signature=null;this.items=[];this.result=null;}
 clear(){for(const r of this.resources)r.dispose();this.resources.clear();this.group?.clear();this.items=[];this.vehiclePick=null;this.vehicleObject=null;this.roomMaterials=new Map();this.riskKey=null;}
 build(result){this.clear();const T=this.THREE;
  // Crisp narrow ribbons render after smoke, while testing solid-object depth.
  // Vehicles/equipment still occlude the hose; x-ray walls remain translucent.
  const makeMaterial=color=>this.own(new T.MeshBasicMaterial({color,transparent:true,opacity:1,depthTest:true,depthWrite:false,side:T.DoubleSide}));
  const outline=makeMaterial('#07131d');
  const add=(object,floor,route=true,order=38)=>{object.renderOrder=order;object.raycast=()=>{};this.group.add(object);this.items.push({object,floor,route});};
  const batches=new Map(),segments=result.segments||[];
  for(const [index,s] of segments.entries()){const a=new T.Vector3(...s.a),b=new T.Vector3(...s.b);a.z+=.12;b.z+=.12;
   if(!this.roomMaterials.has(s.room)){
    const material=makeMaterial('#ffffff');material.polygonOffset=true;material.polygonOffsetFactor=-1;material.polygonOffsetUnits=-1;
    this.roomMaterials.set(s.room,material);
   }
   const d=new T.Vector3().subVectors(b,a),normal=new T.Vector3(-d.y,d.x,0).normalize();
   if(Math.hypot(d.x,d.y)<.01)normal.set(1,0,0);
   // 0.18m coloured centre + 0.05m dark border on either side.
   for(const [width,material,order] of [[.28,outline,37],[.18,this.roomMaterials.get(s.room),38]]){
    const join=(other,point)=>{if(!other||other.floor!==s.floor||other.stair||s.stair)return normal.clone().multiplyScalar(width/2);const end=point===s.a?other.b:other.a;if(end.some((v,k)=>Math.abs(v-point[k])>1e-6))return normal.clone().multiplyScalar(width/2);
     const od=new T.Vector3(...other.b).sub(new T.Vector3(...other.a)),on=new T.Vector3(-od.y,od.x,0).normalize(),mid=normal.clone().add(on).normalize(),dot=mid.dot(normal);return dot>.5?mid.multiplyScalar(width/2/dot):normal.clone().multiplyScalar(width/2);};
    const na=join(segments[index-1],s.a),nb=join(segments[index+1],s.b),p=[a.clone().add(na),b.clone().add(nb),b.clone().sub(nb),a.clone().sub(na)],positions=[];
    for(const i of [0,1,2,0,2,3])positions.push(...p[i].toArray());
    const key=JSON.stringify([s.floor,s.room,order]);if(!batches.has(key))batches.set(key,{positions:[],material,floor:s.floor,order});batches.get(key).positions.push(...positions);
   }
  }
  for(const batch of batches.values()){const g=this.own(new T.BufferGeometry());g.setAttribute('position',new T.Float32BufferAttribute(batch.positions,3));add(new T.Mesh(g,batch.material),batch.floor,true,batch.order);}
  for(const tick of result.ticks||[]){const canvas=document.createElement('canvas');canvas.width=canvas.height=64;const c=canvas.getContext('2d');c.fillStyle='#17384d';c.beginPath();c.arc(32,32,29,0,Math.PI*2);c.fill();c.strokeStyle='#ffffff';c.lineWidth=4;c.stroke();c.fillStyle='#fff';c.font='bold 35px sans-serif';c.textAlign='center';c.textBaseline='middle';c.fillText(String(tick.number),32,33);
   const map=this.own(new T.CanvasTexture(canvas)),m=this.own(new T.SpriteMaterial({map,depthTest:true,depthWrite:false,transparent:true}));const label=new T.Sprite(m);label.position.fromArray(tick.point);label.position.z+=.4;label.scale.set(1,1,1);add(label,tick.floor);
  }
  if(this.vehicleSource){const vehicle=new T.Group();vehicle.rotation.x=Math.PI/2;
   // Borrow existing geometry/materials; include scale person only when requested.
   for(const source of this.vehicleSource.children)if(!source.isSprite&&(this.vehicleSource.userData.includeScalePerson||source.position.x<=4.7))vehicle.add(source.clone());
   const pick=new T.Mesh(this.own(new T.BoxGeometry(8,3.2,2.6)),this.own(new T.MeshBasicMaterial({transparent:true,opacity:0,depthWrite:false,side:T.DoubleSide})));pick.position.y=1.6;pick.layers.set(ROOM_PICK_LAYER);pick.userData.routeVehicle=true;vehicle.add(pick);this.vehiclePick=pick;
   vehicle.position.fromArray(result.vehicle||this.graph.defaultVehicle);this.vehicleObject=vehicle;vehicle.rotation.set(Math.PI/2,0,this.frame?.route.vehicle_yaw||0,'ZYX');add(vehicle,'1F',false);
  }
 }
 setData(frame){this.frame=frame;if(this.vehicleObject)this.vehicleObject.rotation.set(Math.PI/2,0,frame.route.vehicle_yaw||0,'ZYX');if(this.graph.error){const errorKey=JSON.stringify([this.graph.error,frame.route.vehicle]);if(this.signature!==errorKey){this.signature=errorKey;if(this.graph.defaultVehicle)this.build({vehicle:frame.route.vehicle||this.graph.defaultVehicle});this.onChange?.({error:this.graph.error});}for(const {object} of this.items)object.visible=frame.route.vehicle_visible;this.updateVisibility();return;}const state=frame.route,target=this.targetFor(),vehicle=state.vehicle||this.graph.defaultVehicle;
  const signature=JSON.stringify([target,vehicle,state.hose_m,state.stair_factor]);
  if(signature!==this.signature){this.signature=signature;this.result={...findRoute(this.graph,target,vehicle,state),vehicle};this.build(this.result);}
  const riskKey=[frame.building,frame.resultMeta,routeSampleIndex(frame.resultMeta,frame.t_s),frame.risk?.history===true];
  if(!this.riskKey||riskKey.some((x,i)=>x!==this.riskKey[i])){
   this.riskKey=riskKey;this.riskDisplay=routeRiskRows(this.result,frame);
   // The hose stays white; risk values and colours remain in the summary table.
   this.onChange?.({...this.result,risk_summary:this.riskDisplay});
  }
  for(const {object,route} of this.items)object.visible=route||state.vehicle_visible;
  this.updateVisibility();
 }
 setVehiclePreview(point,yaw=0,valid=true){
  if(!point){if(this.preview)this.preview.visible=false;return;}
  const T=this.THREE;
  if(!this.preview&&this.vehicleSource){
   this.preview=new T.Group();this.preview.name='vehicle-placement-preview';this.previewMaterials=new Set();
   for(const source of this.vehicleSource.children){if(source.isSprite||source.position.x>4.7)continue;
    const copy=source.clone();copy.traverse(o=>{o.raycast=()=>{};if(o.material){const clone=m=>{const c=m.clone();c.transparent=true;c.opacity=.32;c.depthWrite=false;c.depthTest=false;this.previewMaterials.add(c);return c;};o.material=Array.isArray(o.material)?o.material.map(clone):clone(o.material);o.renderOrder=80;}});this.preview.add(copy);
   }this.scene.add(this.preview);
  }
  if(this.preview){this.preview.visible=true;this.preview.position.fromArray(point);this.preview.rotation.set(Math.PI/2,0,yaw,'ZYX');for(const m of this.previewMaterials)m.color?.set(valid?'#75deef':'#f26464');}
 }
 getVehiclePickPlanes(){return this.vehiclePick&&this.group?.visible&&this.vehiclePick.parent?.visible?[this.vehiclePick]:[];}
 diagnostics(){return {result:this.result,risk_summary:this.riskDisplay,mainEntrance:this.graph.mainEntrance?.id,entryPoint:this.graph.mainEntrance?.point,defaultVehicle:this.graph.defaultVehicle,sourceEdges:this.graph.sourceEdgeCount,retainedEdges:this.graph.edges?.length,vehicleBorrowed:!!this.vehicleSource,resources:this.resources.size};}
 dispose(){this.preview?.removeFromParent();for(const m of this.previewMaterials||[])m.dispose();this.preview=null;this.clear();this.vehicleSource=null;this.onChange=null;super.dispose();}
}
