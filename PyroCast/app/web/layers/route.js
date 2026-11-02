import {EmptyLayer} from './empty.js';
import {findRoute} from '../route/graph.js';
export class RouteLayer extends EmptyLayer {
 static id='route';
 constructor(T,{graph,targetFor,vehicleSource,onChange}){super(T);Object.assign(this,{graph,targetFor,vehicleSource,onChange});this.signature=null;this.items=[];this.result=null;}
 clear(){for(const r of this.resources)r.dispose();this.resources.clear();this.group?.clear();this.items=[];}
 build(result){this.clear();const T=this.THREE;
  const material=this.own(new T.MeshBasicMaterial({color:'#38bdf8',transparent:true,opacity:1,depthTest:false,depthWrite:false}));
  const add=(object,floor,route=true)=>{object.renderOrder=38;object.raycast=()=>{};this.group.add(object);this.items.push({object,floor,route});};
  for(const s of result.segments||[]){const a=new T.Vector3(...s.a),b=new T.Vector3(...s.b);a.z+=.12;b.z+=.12;
   // Thin ribbon on floors; vertical stair spans use the same double-sided ribbon.
   const d=new T.Vector3().subVectors(b,a),normal=new T.Vector3(-d.y,d.x,0).normalize().multiplyScalar(.125);
   if(Math.hypot(d.x,d.y)<.01)normal.set(.125,0,0);
   const p=[a.clone().add(normal),b.clone().add(normal),b.clone().sub(normal),a.clone().sub(normal)],positions=[];
   for(const i of [0,1,2,0,2,3])positions.push(...p[i].toArray());
   const g=this.own(new T.BufferGeometry());g.setAttribute('position',new T.Float32BufferAttribute(positions,3));material.side=T.DoubleSide;add(new T.Mesh(g,material),s.floor);
  }
  for(const tick of result.ticks||[]){const canvas=document.createElement('canvas');canvas.width=canvas.height=64;const c=canvas.getContext('2d');c.fillStyle='#17384d';c.beginPath();c.arc(32,32,29,0,Math.PI*2);c.fill();c.strokeStyle='#38bdf8';c.lineWidth=4;c.stroke();c.fillStyle='#fff';c.font='bold 35px sans-serif';c.textAlign='center';c.textBaseline='middle';c.fillText(String(tick.number),32,33);
   const map=this.own(new T.CanvasTexture(canvas)),m=this.own(new T.SpriteMaterial({map,depthTest:false,depthWrite:false,transparent:true}));const label=new T.Sprite(m);label.position.fromArray(tick.point);label.position.z+=.4;label.scale.set(1,1,1);add(label,tick.floor);
  }
  if(this.vehicleSource){const vehicle=new T.Group();vehicle.rotation.x=Math.PI/2;
   // Borrow the established reference vehicle's geometry/materials; omit human/label.
   for(const source of this.vehicleSource.children)if(!source.isSprite&&source.position.x<=4.7)vehicle.add(source.clone());
   vehicle.position.fromArray(result.vehicle||this.graph.defaultVehicle);add(vehicle,'1F',false);
  }
 }
 setData(frame){this.frame=frame;if(this.graph.error){if(this.signature!==this.graph.error){this.signature=this.graph.error;this.onChange?.({error:this.graph.error});}this.updateVisibility();return;}const state=frame.route,target=this.targetFor(),vehicle=state.vehicle||this.graph.defaultVehicle;
  const signature=JSON.stringify([target,vehicle,state.hose_m,state.stair_factor]);
  if(signature!==this.signature){this.signature=signature;this.result={...findRoute(this.graph,target,vehicle,state),vehicle};this.build(this.result);this.onChange?.(this.result);}
  for(const {object,floor,route} of this.items)object.visible=(frame.floor.floor_id===null||frame.floor.floor_id===floor)&&(route||state.vehicle_visible);
  this.updateVisibility();
 }
 diagnostics(){return {result:this.result,mainEntrance:this.graph.mainEntrance.id,entryPoint:this.graph.mainEntrance.point,defaultVehicle:this.graph.defaultVehicle,sourceEdges:this.graph.sourceEdgeCount,retainedEdges:this.graph.edges.length,vehicleBorrowed:!!this.vehicleSource,resources:this.resources.size};}
 dispose(){this.clear();this.vehicleSource=null;this.onChange=null;super.dispose();}
}
