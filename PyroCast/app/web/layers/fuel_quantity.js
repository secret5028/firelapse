import {selectionOutlineMaterials,selectionOutlineGeometry,selectionOutlineMesh} from './selection_outline.js';
import {EmptyLayer} from './empty.js';
import {contains} from '../route/graph.js';
import {resolveFuel} from '../state/fuel_settings.js';
import {ROOM_PICK_LAYER} from '../scene/picking.js';
// Symbols describe quantity, not physical furniture or extra simulation fuel units.
function distanceToSegment(p,a,b){const dx=b[0]-a[0],dy=b[1]-a[1],t=Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy||1)));return Math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy);}
export function fuelPositions(polys){
 const candidates=[];
 for(const poly of polys||[]){const xs=poly.o.map(p=>p[0]),ys=poly.o.map(p=>p[1]),x0=Math.min(...xs),y0=Math.min(...ys),w=Math.max(...xs)-x0,h=Math.max(...ys)-y0;
  for(let i=1;i<8;i++)for(let j=1;j<8;j++){const p=[x0+w*i/8,y0+h*j/8];if(!contains(p,[poly]))continue;let clearance=Infinity;for(const ring of [poly.o,...(poly.h||[])])for(let k=0;k<ring.length;k++)clearance=Math.min(clearance,distanceToSegment(p,ring[k],ring[(k+1)%ring.length]));if(clearance>.25)candidates.push({p,clearance});}
 }
 candidates.sort((a,b)=>b.clearance-a.clearance);const selected=[];for(const c of candidates){if(selected.every(s=>Math.hypot(c.p[0]-s.p[0],c.p[1]-s.p[1])>2.5))selected.push(c);if(selected.length===4)break;}return selected;
}
export function symbolSize(load,clearance,height){return Math.min(1.5,Math.max(.15,.65*Math.cbrt(Math.max(0,load)/500)),(clearance-.05)*Math.SQRT2,Math.max(0,height-.2));}
export class FuelQuantityLayer extends EmptyLayer{
 static id='fuelQuantity';
 constructor(T,building){super(T);this.building=building;this.floors=[];this.picks=[];this.lastData=null;this.lastDraft=null;this.revision=null;}
 build(data){for(const r of this.resources)r.dispose();this.resources.clear();this.group.clear();this.floors=[];const T=this.THREE,geo=this.own(new T.BoxGeometry(1,1,1)),mat=this.own(new T.MeshBasicMaterial({color:'#d5ae75',transparent:true,opacity:.75,depthTest:true,depthWrite:false})),rows=new Map(data.rooms.map(r=>[r.id,r]));
  for(const f of this.building.floors){const units=[];for(const r of f.rooms){const id=`CAD_${f.name}_${r.id}`,setting=rows.get(id);if(!setting?.editable)continue;for(const p of fuelPositions(r.polys))units.push({...p,id,height:f.h,z:f.z});}if(!units.length)continue;const mesh=new T.InstancedMesh(geo,mat,units.length);mesh.raycast=()=>{};mesh.name='fuel-quantity-'+f.name;mesh.renderOrder=12;mesh.frustumCulled=false;this.own(mesh);this.group.add(mesh);this.floors.push({floor:f.name,mesh,units});}
 }
 buildPicks(data,adapter){const T=this.THREE;this.picks=[];const known=new Set((adapter?.floors||[]).flatMap(f=>f.rooms.map(r=>r.room_id))),ids=new Set(data.rooms.filter(r=>r.editable).map(r=>r.id));
  const mat=this.own(new T.MeshBasicMaterial({side:T.DoubleSide,transparent:true,opacity:0,depthWrite:false})),lineMaterials=selectionOutlineMaterials(T,r=>this.own(r));
  for(const f of this.building.floors)for(const r of f.rooms){const id=`CAD_${f.name}_${r.id}`;if(!ids.has(id)||known.has(id))continue;
   const shapes=(r.polys||[]).map(p=>{const s=new T.Shape(p.o.map(v=>new T.Vector2(...v)));for(const h of p.h||[])s.holes.push(new T.Path(h.map(v=>new T.Vector2(...v))));return s;});
   const pick=new T.Mesh(this.own(new T.ShapeGeometry(shapes)),mat);pick.position.z=f.z+.07;pick.layers.set(ROOM_PICK_LAYER);pick.userData={roomId:id,liteRoom:null,floorId:f.name};this.group.add(pick);
   const line=selectionOutlineMesh(T,selectionOutlineGeometry(T,r=>this.own(r),r.polys||[],f.z),lineMaterials);this.group.add(line);this.picks.push({pick,line,id,floor:f.name});
  }
 }
 setData(frame){super.setData(frame);const data=frame.fuelSettings?.data,draft=frame.fuelSettings?.draft||{},rebuilt=!!data&&(data.revision!==this.revision||frame.building!==this.adapter);if(rebuilt){this.build(data);this.buildPicks(data,frame.building);this.revision=data.revision;this.adapter=frame.building;}
  if(data&&(rebuilt||data!==this.lastData||draft!==this.lastDraft)){const rows=new Map(data.rooms.map(r=>[r.id,r])),dummy=new this.THREE.Object3D();for(const f of this.floors){f.units.forEach((u,i)=>{const r=rows.get(u.id),value=resolveFuel(data,draft,r),size=value.pending?0:symbolSize(value.load,u.clearance,u.height);dummy.position.set(...u.p,u.z+.04+size/2);dummy.scale.setScalar(size);dummy.updateMatrix();f.mesh.setMatrixAt(i,dummy.matrix);});f.mesh.instanceMatrix.needsUpdate=true;}}
  for(const p of this.picks){p.pick.visible=frame.floor.floor_id===null||frame.floor.floor_id===p.floor;p.line.visible=p.pick.visible&&frame.layers.selection&&frame.selection.room_id===p.id;}
  for(const f of this.floors)f.mesh.visible=!!data&&frame.realView.fuelMarkers&&(frame.floor.floor_id===null||frame.floor.floor_id===f.floor);this.lastData=data;this.lastDraft=draft;
 }
 getPickPlanes(){return this.group?.visible?this.picks.filter(p=>p.pick.visible).map(p=>p.pick):[];}
 dispose(){this.floors=[];this.lastData=null;this.lastDraft=null;super.dispose();}
}
