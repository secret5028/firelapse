import {EmptyLayer} from './empty.js';
import {applyRenderPolicy} from '../scene/render_order.js';

export class CoreLayer extends EmptyLayer {
 static id='core';
 constructor(THREE,{geometryFor}={}){super(THREE);
  if(typeof geometryFor!=='function')throw Error('CAD core source provider required');
  this.geometryFor=geometryFor;this.asset=null;this.lastBuilding=undefined;this.lastResult=undefined;this.views=[];this.buildCount=0;
 }
 clearGeometry(){for(const resource of this.resources)resource.dispose();this.resources.clear();this.group?.clear();this.views=[];this.asset=null;}
 build(asset){this.clearGeometry();this.asset=asset;this.buildCount++;const T=this.THREE;
  for(const row of asset.floors){const {floor}=row,group=new T.Group();group.name=row.id+'-cores';this.group.add(group);this.views.push({row,group});
   for(const core of floor.transport||[]){
    if(!['stair','elev'].includes(core.kind))continue;
    if(!core.connected&&!core.to_floor&&!(core.meshes||[]).length)continue;
    const color=core.kind==='stair'?'#ffc342':'#55baff',polys=core.region?.length?core.region:core.anchor;
    if(!polys?.length)continue;
    const extrude=(polygons,depth)=>this.own(new T.ExtrudeGeometry(polygons.map(asset.shapeFor),{depth,bevelEnabled:false,curveSegments:1}));
    const geometry=extrude(polys,floor.h);
    const shell=applyRenderPolicy(new T.Mesh(geometry,this.own(new T.MeshBasicMaterial({color,side:T.DoubleSide}))),'core');
    shell.raycast=()=>{};group.add(shell);
    const edges=applyRenderPolicy(new T.LineSegments(this.own(new T.EdgesGeometry(geometry,25)),this.own(new T.LineBasicMaterial({color}))),'core.edge');
    edges.raycast=()=>{};group.add(edges);
    if(core.kind==='stair')for(const step of core.meshes||[]){
     if(!step.polys?.length||!(step.z1>step.z0))continue;
     const tread=applyRenderPolicy(new T.Mesh(extrude(step.polys,step.z1-step.z0),this.own(new T.MeshBasicMaterial({color}))),'core.tread');
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
 // EmptyLayer's core visibility requires floor_id===null and layer toggle ON.
 tick(){for(const {row,group} of this.views){group.position.copy(row.group.position);group.visible=row.group.visible;}}
 diagnostics(){const counts={shells:0,treads:0,edges:0};for(const {group} of this.views)for(const object of group.children){
  if(object.renderOrder===70)counts.shells++;else if(object.renderOrder===72)counts.treads++;else if(object.renderOrder===73)counts.edges++;}
  return {buildCount:this.buildCount,resources:this.resources.size,floors:this.views.length,...counts};
 }
 dispose(){this.clearGeometry();this.geometryFor=null;this.lastBuilding=null;this.lastResult=null;super.dispose();}
}
