import {EmptyLayer,createEmptyLayers} from './empty.js';
import {applyRenderPolicy} from '../scene/render_order.js';
import {wallOpeningVolumes,trimWallLineGeometry,trimWallJambFaces} from './wall_opening_lines.js';
// Borrow both CAD geometry and materials; restore install() colour overrides.
export class BuildingLayer extends EmptyLayer {
 static id='building';
 constructor(THREE,{geometryFor}={}){super(THREE);if(typeof geometryFor!=='function')throw Error('CAD geometry provider required');
  this.geometryFor=geometryFor;this.asset=null;this.lastBuilding=undefined;this.lastResult=undefined;this.floorId=undefined;this.floorGroups=new Map();this.sourceObjects=new Map();this.materialState=new Map();this.bindings=[];this.buildCount=0;}
 clearGeometry(){for(const [material,before] of this.materialState){material.color.copy(before.color);material.opacity=before.opacity;
   if(material.transparent!==before.transparent){material.transparent=before.transparent;material.needsUpdate=true;}}
  this.materialState.clear();for(const resource of this.resources)resource.dispose();this.resources.clear();this.group?.clear();this.floorGroups.clear();this.sourceObjects.clear();this.bindings=[];this.asset=null;this.openingSignature=null;this.trimmedLines=0;}
 build(asset){const T=this.THREE;this.clearGeometry();this.asset=asset;this.buildCount++;
  for(const floor of asset.floors){const g=new T.Group();g.name=floor.id;g.position.copy(floor.group.position);g.quaternion.copy(floor.group.quaternion);g.scale.copy(floor.group.scale);this.group.add(g);this.floorGroups.set(floor.id,g);
   const parents=new Map([[floor.group,g]]);
   const parentFor=source=>{if(parents.has(source))return parents.get(source);if(!source)throw Error('CAD source escaped floor hierarchy');
    const parent=parentFor(source.parent),copy=new T.Group();copy.name=source.name;copy.renderOrder=source.renderOrder;copy.position.copy(source.position);copy.quaternion.copy(source.quaternion);copy.scale.copy(source.scale);copy.visible=source.visible;
    parent.add(copy);parents.set(source,copy);this.bindings.push({source,object:copy});return copy;
   };
   for(const [i,source] of floor.objects.entries()){const view=Object.create(source);view.userData={};
    const object=new source.constructor().copy(view,false),style=floor.styles[i];object.userData={...source.userData};
    const material=source.material;
    if(!this.materialState.has(material))this.materialState.set(material,{color:material.color.clone(),opacity:material.opacity,transparent:material.transparent});
    material.color.set(style.color);if(style.opacity!==null)material.opacity=style.opacity;object.material=material;
    applyRenderPolicy(object,'building');parentFor(source.parent).add(object);parents.set(source,object);this.sourceObjects.set(source,object);this.bindings.push({source,object});
   }
  }
 }
 trimOpenings(time){
  const floors=this.asset?.floors||[],signature=JSON.stringify(floors.flatMap(f=>(f.floor?.openings||[]).filter(o=>o.display_schedule).map(o=>{let value=0;for(const [t,v] of o.display_schedule)if(t<=time)value=v;return value;})));
  if(signature===this.openingSignature)return;this.openingSignature=signature;this.trimmedLines=0;
  const volumes=floors.map(f=>wallOpeningVolumes(f.floor||{},time));
  for(const resource of this.resources)resource.dispose();this.resources.clear();
  floors.forEach((floor,i)=>{for(const source of floor.objects){const object=this.sourceObjects.get(source);if(!object)continue;
   const clipped=source.isMesh?trimWallJambFaces(this.THREE,source,floor.group,volumes[i]):trimWallLineGeometry(this.THREE,source,floor.group,volumes[i]);object.geometry=clipped?this.own(clipped):source.geometry;if(clipped&&source.isLineSegments)this.trimmedLines++;
  }});
 }
 // Newly included stairs/glass may sit inside transformed or hidden groups.
 // Preserve that hierarchy instead of flattening their local coordinates.
 syncSource(){for(const {source,object} of this.bindings){object.visible=source.visible;object.position.copy(source.position);object.quaternion.copy(source.quaternion);object.scale.copy(source.scale);}
  for(const floor of this.asset?.floors||[]){const g=this.floorGroups.get(floor.id);g.position.copy(floor.group.position);g.quaternion.copy(floor.group.quaternion);g.scale.copy(floor.group.scale);g.visible=floor.group.visible&&(this.floorId===null||this.floorId===floor.id);}
 }
 setData(frame){if(this.state!=='mounted')throw Error('Layer is not mounted');this.frame=frame;
  if(frame.building!==this.lastBuilding){const asset=frame.building?this.geometryFor(frame.building):null;
   if(frame.building&&(!asset||asset.source_hash!==frame.building.source_hash))throw Error('Missing/mismatched CAD geometry; no room-box fallback');
   if(asset!==this.asset){if(asset)this.build(asset);else this.clearGeometry();}this.lastBuilding=frame.building;}
  if(frame.resultMeta!==this.lastResult)this.lastResult=frame.resultMeta;
  this.trimOpenings(frame.t_s??0);
  if(frame.floor?.floor_id!==this.floorId||this.appliedBuild!==this.buildCount){this.floorId=frame.floor?.floor_id??null;for(const [id,g] of this.floorGroups)g.visible=this.floorId===null||id===this.floorId;this.appliedBuild=this.buildCount;}
  this.updateVisibility();
 }
 diagnostics(){return {buildCount:this.buildCount,ownedMaterials:0,borrowedMaterials:this.materialState.size,floors:this.floorGroups.size,drawObjects:this.sourceObjects.size,trimmedLines:this.trimmedLines};}
 dispose(){this.clearGeometry();this.lastBuilding=null;this.lastResult=null;this.geometryFor=null;super.dispose();}
}
export function createBuildingLayers(THREE,options){return [new BuildingLayer(THREE,options),...createEmptyLayers(THREE).filter(layer=>layer.constructor.id!=='building')];}
