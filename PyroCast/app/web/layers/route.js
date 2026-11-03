import {EmptyLayer} from './empty.js';
import {findRoute} from '../route/graph.js';
import {routeRiskRows,routeSampleIndex,ROUTE_CLEAR} from '../route/risk.js';
export class RouteLayer extends EmptyLayer {
 static id='route';
 constructor(T,{graph,targetFor,vehicleSource,onChange}){super(T);Object.assign(this,{graph,targetFor,vehicleSource,onChange});this.signature=null;this.items=[];this.result=null;}
 clear(){for(const r of this.resources)r.dispose();this.resources.clear();this.group?.clear();this.items=[];this.roomMaterials=new Map();this.riskKey=null;}
 build(result){this.clear();const T=this.THREE;
  const makeMaterial=color=>this.own(new T.MeshBasicMaterial({color,transparent:true,opacity:1,depthTest:false,depthWrite:false,side:T.DoubleSide}));
  const outline=makeMaterial('#07131d');
  const add=(object,floor,route=true,order=38)=>{object.renderOrder=order;object.raycast=()=>{};this.group.add(object);this.items.push({object,floor,route});};
  for(const s of result.segments||[]){const a=new T.Vector3(...s.a),b=new T.Vector3(...s.b);a.z+=.12;b.z+=.12;
   if(!this.roomMaterials.has(s.room))this.roomMaterials.set(s.room,makeMaterial(ROUTE_CLEAR));
   const d=new T.Vector3().subVectors(b,a),normal=new T.Vector3(-d.y,d.x,0).normalize();
   if(Math.hypot(d.x,d.y)<.01)normal.set(1,0,0);
   // 0.40m coloured centre + 0.08m dark border on either side. No shader changes.
   for(const [width,material,order] of [[.56,outline,37],[.4,this.roomMaterials.get(s.room),38]]){
    const n=normal.clone().multiplyScalar(width/2),p=[a.clone().add(n),b.clone().add(n),b.clone().sub(n),a.clone().sub(n)],positions=[];
    for(const i of [0,1,2,0,2,3])positions.push(...p[i].toArray());
    const g=this.own(new T.BufferGeometry());g.setAttribute('position',new T.Float32BufferAttribute(positions,3));add(new T.Mesh(g,material),s.floor,true,order);
   }
  }
  for(const tick of result.ticks||[]){const canvas=document.createElement('canvas');canvas.width=canvas.height=64;const c=canvas.getContext('2d');c.fillStyle='#17384d';c.beginPath();c.arc(32,32,29,0,Math.PI*2);c.fill();c.strokeStyle='#38bdf8';c.lineWidth=4;c.stroke();c.fillStyle='#fff';c.font='bold 35px sans-serif';c.textAlign='center';c.textBaseline='middle';c.fillText(String(tick.number),32,33);
   const map=this.own(new T.CanvasTexture(canvas)),m=this.own(new T.SpriteMaterial({map,depthTest:false,depthWrite:false,transparent:true}));const label=new T.Sprite(m);label.position.fromArray(tick.point);label.position.z+=.4;label.scale.set(1,1,1);add(label,tick.floor);
  }
  if(this.vehicleSource){const vehicle=new T.Group();vehicle.rotation.x=Math.PI/2;
   // Borrow existing geometry/materials; include scale person only when requested.
   for(const source of this.vehicleSource.children)if(!source.isSprite&&(this.vehicleSource.userData.includeScalePerson||source.position.x<=4.7))vehicle.add(source.clone());
   vehicle.position.fromArray(result.vehicle||this.graph.defaultVehicle);add(vehicle,'1F',false);
  }
 }
 setData(frame){this.frame=frame;if(this.graph.error){if(this.signature!==this.graph.error){this.signature=this.graph.error;this.onChange?.({error:this.graph.error});}this.updateVisibility();return;}const state=frame.route,target=this.targetFor(),vehicle=state.vehicle||this.graph.defaultVehicle;
  const signature=JSON.stringify([target,vehicle,state.hose_m,state.stair_factor]);
  if(signature!==this.signature){this.signature=signature;this.result={...findRoute(this.graph,target,vehicle,state),vehicle};this.build(this.result);}
  const riskKey=[frame.building,frame.resultMeta,routeSampleIndex(frame.resultMeta,frame.t_s),frame.risk?.history===true];
  if(!this.riskKey||riskKey.some((x,i)=>x!==this.riskKey[i])){
   this.riskKey=riskKey;this.riskDisplay=routeRiskRows(this.result,frame);
   for(const row of this.riskDisplay.rows)this.roomMaterials.get(row.room)?.color.set(row.color);
   this.onChange?.({...this.result,risk_summary:this.riskDisplay});
  }
  for(const {object,floor,route} of this.items)object.visible=(frame.floor.floor_id===null||frame.floor.floor_id===floor)&&(route||state.vehicle_visible);
  this.updateVisibility();
 }
 diagnostics(){return {result:this.result,risk_summary:this.riskDisplay,mainEntrance:this.graph.mainEntrance?.id,entryPoint:this.graph.mainEntrance?.point,defaultVehicle:this.graph.defaultVehicle,sourceEdges:this.graph.sourceEdgeCount,retainedEdges:this.graph.edges?.length,vehicleBorrowed:!!this.vehicleSource,resources:this.resources.size};}
 dispose(){this.clear();this.vehicleSource=null;this.onChange=null;super.dispose();}
}
