import {EmptyLayer} from './empty.js';
import {contains} from '../route/graph.js';
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
 constructor(T,building){super(T);this.building=building;this.floors=[];this.lastData=null;this.lastDraft=null;}
 build(data){for(const r of this.resources)r.dispose();this.resources.clear();this.group.clear();this.floors=[];const T=this.THREE,geo=this.own(new T.BoxGeometry(1,1,1)),mat=this.own(new T.MeshBasicMaterial({color:'#d5ae75',transparent:true,opacity:.75,depthTest:true,depthWrite:false})),rows=new Map(data.rooms.map(r=>[r.id,r]));
  for(const f of this.building.floors){const units=[];for(const r of f.rooms){const id=`CAD_${f.name}_${r.id}`,setting=rows.get(id);if(!setting?.editable)continue;for(const p of fuelPositions(r.polys))units.push({...p,id,height:f.h,z:f.z});}if(!units.length)continue;const mesh=new T.InstancedMesh(geo,mat,units.length);mesh.raycast=()=>{};mesh.name='fuel-quantity-'+f.name;mesh.renderOrder=12;mesh.frustumCulled=false;this.own(mesh);this.group.add(mesh);this.floors.push({floor:f.name,mesh,units});}
 }
 setData(frame){super.setData(frame);const data=frame.fuelSettings?.data,draft=frame.fuelSettings?.draft||{};if(data!==this.lastData&&data)this.build(data);
  if(data&&(data!==this.lastData||draft!==this.lastDraft)){const rows=new Map(data.rooms.map(r=>[r.id,r])),dummy=new this.THREE.Object3D();for(const f of this.floors){f.units.forEach((u,i)=>{const r=rows.get(u.id),size=symbolSize(r.base_load*(draft[u.id]??r.multiplier),u.clearance,u.height);dummy.position.set(...u.p,u.z+.04+size/2);dummy.scale.setScalar(size);dummy.updateMatrix();f.mesh.setMatrixAt(i,dummy.matrix);});f.mesh.instanceMatrix.needsUpdate=true;}}
  for(const f of this.floors)f.mesh.visible=!!data&&frame.realView.fuelMarkers&&(frame.floor.floor_id===null||frame.floor.floor_id===f.floor);this.lastData=data;this.lastDraft=draft;
 }
 dispose(){this.floors=[];this.lastData=null;this.lastDraft=null;super.dispose();}
}
