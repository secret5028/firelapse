import {EmptyLayer} from './empty.js';
import {applyRenderPolicy} from '../scene/render_order.js';

// Same two-flight/landing proportions as cad_model_transport.prepare_model.
// Display only: triangle clipping respects concave footprints and their holes.
export function fallbackStairSteps(T,core){
 if(core.kind!=='stair'||core.assumption!=='simplified_return_stair_display_only'||!(core.rise_m>0))return [];
 const points=core.region.flatMap(p=>p.o),xs=points.map(p=>p[0]),ys=points.map(p=>p[1]);
 const swap=Math.max(...xs)-Math.min(...xs)>Math.max(...ys)-Math.min(...ys);
 const local=p=>swap?[p[1],p[0]]:[...p],world=local;
 const pts=points.map(local),x0=Math.min(...pts.map(p=>p[0])),x1=Math.max(...pts.map(p=>p[0])),y0=Math.min(...pts.map(p=>p[1])),y1=Math.max(...pts.map(p=>p[1]));
 const w=x1-x0,h=y1-y0,landing=Math.min(w*.5,h*.2,1.3),run=h-2*landing,rise=core.rise_m,n=Math.max(4,Math.ceil(rise/.36));
 const triangles=[];
 for(const p of core.region){
  const outer=p.o.map(q=>new T.Vector2(...local(q))),holes=(p.h||[]).map(r=>r.map(q=>new T.Vector2(...local(q))));
  const indices=T.ShapeUtils.triangulateShape(outer,holes),vertices=[...outer,...holes.flat()];
  for(const face of indices)triangles.push(face.map(i=>[vertices[i].x,vertices[i].y]));
 }
 const clip=(ring,axis,value,sign)=>{
  const out=[];
  for(let i=0;i<ring.length;i++){
   const a=ring[i],b=ring[(i+1)%ring.length],ia=sign*(a[axis]-value)>=0,ib=sign*(b[axis]-value)>=0;
   if(ia)out.push(a);
   if(ia!==ib){const t=(value-a[axis])/(b[axis]-a[axis]);out.push([a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])]);}
  }return out;
 };
 const steps=[];
 const slab=(xa,ya,xb,yb,z,th=.1)=>{
  const polys=[];
  for(const tri of triangles){let r=tri;for(const [axis,value,sign] of [[0,xa,1],[0,xb,-1],[1,ya,1],[1,yb,-1]])r=clip(r,axis,value,sign);
   const area=Math.abs(r.reduce((a,p,i)=>a+p[0]*r[(i+1)%r.length][1]-r[(i+1)%r.length][0]*p[1],0))/2;
   if(area>.0001)polys.push({o:r.map(world),h:[]});
  }
  if(polys.length)steps.push({polys,z0:z-th,z1:z});
 };
 for(let i=0;i<n;i++){
  slab(x0,y1-landing-(i+1)*run/n,x0+w*.46,y1-landing-i*run/n,(i+1)*rise/(2*n));
  slab(x0+w*.54,y0+landing+i*run/n,x1,y0+landing+(i+1)*run/n,rise/2+(i+1)*rise/(2*n));
 }
 // Full-width floor landing joins the returning flight to the next floor's
 // first flight. A right-half landing leaves the two flights disconnected.
 slab(x0,y0,x1,y0+landing,rise/2,.14);slab(x0,y1-landing,x1,y1,rise,.14);
 return steps;
}

export class CoreLayer extends EmptyLayer {
 static id='core';
 constructor(THREE,{geometryFor,contextFloorsFor=()=>[]}={}){super(THREE);
  if(typeof geometryFor!=='function')throw Error('CAD core source provider required');
  this.geometryFor=geometryFor;this.contextFloorsFor=contextFloorsFor;this.asset=null;this.lastBuilding=undefined;this.lastResult=undefined;this.views=[];this.buildCount=0;
 }
 clearGeometry(){for(const resource of this.resources)resource.dispose();this.resources.clear();this.group?.clear();this.views=[];this.asset=null;}
 build(asset){this.clearGeometry();this.asset=asset;this.buildCount++;const T=this.THREE;
  for(const row of asset.floors){const {floor}=row,group=new T.Group();group.name=row.id+'-cores';this.group.add(group);this.views.push({row,group});
   for(const core of floor.transport||[]){
    if(!['stair','elev'].includes(core.kind))continue;
    if(!core.connected&&!core.to_floor&&!(core.meshes||[]).length)continue;
    const color=core.kind==='stair'?'#2563eb':'#55baff',polys=core.region?.length?core.region:core.anchor;
    if(!polys?.length)continue;
    const extrude=(polygons,depth)=>this.own(new T.ExtrudeGeometry(polygons.map(asset.shapeFor),{depth,bevelEnabled:false,curveSegments:1}));
    const geometry=extrude(polys,floor.h);
    if(core.kind==='elev'){
    const shell=applyRenderPolicy(new T.Mesh(geometry,this.own(new T.MeshBasicMaterial({color,side:T.DoubleSide}))),'core');
    shell.raycast=()=>{};group.add(shell);
    }
    const edges=applyRenderPolicy(new T.LineSegments(this.own(new T.EdgesGeometry(geometry,25)),this.own(new T.LineBasicMaterial({color}))),'core.edge');
    // WebGL native lines are already 1 px; soften stair coverage for a finer outline.
    if(core.kind==='stair'){edges.material.linewidth=1;edges.material.opacity=.60;}
    edges.raycast=()=>{};group.add(edges);
    if(core.kind==='stair')for(const step of core.meshes?.length?core.meshes:fallbackStairSteps(T,core)){
     if(!step.polys?.length||!(step.z1>step.z0))continue;
     const tread=applyRenderPolicy(new T.LineSegments(this.own(new T.EdgesGeometry(extrude(step.polys,step.z1-step.z0),25)),this.own(new T.LineBasicMaterial({color}))),'core.tread');
     tread.material.linewidth=1;tread.material.opacity=.55;
     tread.position.z=step.z0;tread.raycast=()=>{};group.add(tread);
    }
   }
  }
 }
 setData(frame){if(this.state!=='mounted')throw Error('Layer is not mounted');this.frame=frame;
  if(frame.building!==this.lastBuilding){const asset=frame.building?this.geometryFor(frame.building):null;
   if(frame.building&&(!asset||asset.source_hash!==frame.building.source_hash))throw Error('Missing/mismatched CAD core geometry');
   if(asset!==this.asset){if(asset)this.build(asset);else this.clearGeometry();}this.lastBuilding=frame.building;}
  if(frame.resultMeta!==this.lastResult)this.lastResult=frame.resultMeta;
  this.updateVisibility();
 }
 // The toggle controls context/x-ray cores; the selected floor always retains its own cores.
 updateVisibility(){if(this.group)this.group.visible=this.visible!==false||this.frame?.floor?.floor_id!=null;}
 tick(){const floor=this.frame?.floor?.floor_id??null;
  const selectedZ=this.views.find(v=>v.row.id===floor)?.row.group.position.z;
  const context=new Set(this.frame?.layers?.route!==false?this.contextFloorsFor():[]);
  for(const {row,group} of this.views){group.position.copy(row.group.position);
   const below=floor!==null&&Number.isFinite(selectedZ)&&row.group.position.z<selectedZ;
   group.visible=(floor!==null&&row.id===floor)||(this.visible!==false&&((floor===null&&row.group.visible)||(below&&context.has(row.id))));
   for(const object of group.children){const material=object.material;if(!material)continue;
    material.userData.coreOpacity??=material.opacity;
    material.opacity=material.userData.coreOpacity*(below?.35:1);
   }
  }
 }
 diagnostics(){const counts={shells:0,treads:0,edges:0};for(const {group} of this.views)for(const object of group.children){
  if(object.renderOrder===70)counts.shells++;else if(object.renderOrder===72)counts.treads++;else if(object.renderOrder===73)counts.edges++;}
  return {buildCount:this.buildCount,resources:this.resources.size,floors:this.views.length,...counts};
 }
 dispose(){this.clearGeometry();this.geometryFor=null;this.contextFloorsFor=null;this.lastBuilding=null;this.lastResult=null;super.dispose();}
}
