import {wallCornerSegments,isWallMesh,isReplacedWallOutline} from './wall_corners.js';
import {EmptyLayer,createEmptyLayers} from './empty.js';
import {applyRenderPolicy} from '../scene/render_order.js';
import {wallOpeningVolumes,trimWallLineGeometry,trimWallJambFaces} from './wall_opening_lines.js';
// Borrow both CAD geometry and materials; restore install() colour overrides.
export class BuildingLayer extends EmptyLayer {
 static id='building';
 constructor(THREE,{geometryFor}={}){super(THREE);if(typeof geometryFor!=='function')throw Error('CAD geometry provider required');
  this.geometryFor=geometryFor;this.asset=null;this.lastBuilding=undefined;this.lastResult=undefined;this.floorId=undefined;this.floorGroups=new Map();this.sourceObjects=new Map();this.materialState=new Map();this.bindings=[];this.buildCount=0;this.cornerResources=new Set();this.cornerLines=[];this.replacedOutlines=new Set();}
 clearCorners(){for(const line of this.cornerLines)line.removeFromParent();for(const r of this.cornerResources)r.dispose();this.cornerResources.clear();this.cornerLines=[];this.replacedOutlines.clear();}
 clearGeometry(){this.clearCorners();for(const [material,before] of this.materialState){material.color.copy(before.color);material.opacity=before.opacity;material.depthWrite=before.depthWrite;
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
    if(!this.materialState.has(material))this.materialState.set(material,{color:material.color.clone(),opacity:material.opacity,transparent:material.transparent,depthWrite:material.depthWrite});
    material.color.set(style.color);if(style.opacity!==null)material.opacity=style.opacity;object.material=material;
    this.materialState.get(material).displayOpacity=material.opacity;
    applyRenderPolicy(object,'building');parentFor(source.parent).add(object);parents.set(source,object);this.sourceObjects.set(source,object);this.bindings.push({source,object});
   }
  }
 }
 applyTransparency(value=.7){
  // 70% preserves the established, material-specific translucent appearance.
  // Endpoints: 0% opaque, 100% invisible. Never multiply last frame's opacity.
  const alpha=base=>value===.7?base:value<.7?1+(base-1)*value/.7:base*(1-value)/.3;
  for(const [material,before] of this.materialState){
   const opacity=alpha(before.displayOpacity),transparent=value===.7?before.transparent:before.transparent||opacity<1;
   material.opacity=opacity;material.depthWrite=opacity===0?false:before.depthWrite;
   if(material.transparent!==transparent){material.transparent=transparent;material.needsUpdate=true;}
  }
  for(const line of this.cornerLines)line.material.opacity=alpha(.32);
 }
 trimOpenings(time){
  const floors=this.asset?.floors||[],signature=JSON.stringify(floors.flatMap(f=>(f.floor?.openings||[]).filter(o=>o.display_schedule).map(o=>{let value=0;for(const [t,v] of o.display_schedule)if(t<=time)value=v;return value;})));
  if(signature===this.openingSignature)return;this.openingSignature=signature;this.trimmedLines=0;this.clearCorners();
  const volumes=floors.map(f=>wallOpeningVolumes(f.floor||{},time));
  for(const resource of this.resources)resource.dispose();this.resources.clear();
  floors.forEach((floor,i)=>{for(const source of floor.objects){const object=this.sourceObjects.get(source);if(!object)continue;
   const clipped=source.isMesh?trimWallJambFaces(this.THREE,source,floor.group,volumes[i]):trimWallLineGeometry(this.THREE,source,floor.group,volumes[i]);object.geometry=clipped?this.own(clipped):source.geometry;if(clipped&&source.isLineSegments)this.trimmedLines++;
  }
   const points=wallCornerSegments(this.THREE,floor,volumes[i]);if(points.length){
    const T=this.THREE,geometry=new T.BufferGeometry();geometry.setAttribute('position',new T.Float32BufferAttribute(points,3));
    const material=new T.LineBasicMaterial({color:'#8da8b7',transparent:true,opacity:.32,linewidth:1,depthTest:true,depthWrite:false});
    const line=new T.LineSegments(geometry,material);line.name=floor.id+'_wall_corners';line.userData.wallSources=floor.objects.filter(isWallMesh);line.renderOrder=-1;line.raycast=()=>{};
    this.floorGroups.get(floor.id).add(line);this.cornerLines.push(line);this.cornerResources.add(geometry);this.cornerResources.add(material);
    // Existing per-piece wireframes would double the edge and expose seams again.
    for(const source of floor.objects)if(isReplacedWallOutline(this.THREE,source,floor)){const object=this.sourceObjects.get(source);object.visible=false;this.replacedOutlines.add(object);}
   }
  });
 }
 // Newly included stairs/glass may sit inside transformed or hidden groups.
 // Preserve that hierarchy instead of flattening their local coordinates.
 syncSource(){for(const line of this.cornerLines)line.visible=line.userData.wallSources.some(s=>s.visible);for(const {source,object} of this.bindings){object.visible=source.visible&&!this.replacedOutlines.has(object);object.position.copy(source.position);object.quaternion.copy(source.quaternion);object.scale.copy(source.scale);}
  for(const floor of this.asset?.floors||[]){const g=this.floorGroups.get(floor.id);g.position.copy(floor.group.position);g.quaternion.copy(floor.group.quaternion);g.scale.copy(floor.group.scale);g.visible=floor.group.visible&&(this.floorId===null||this.floorId===floor.id);}
 }
 setData(frame){if(this.state!=='mounted')throw Error('Layer is not mounted');this.frame=frame;
  if(frame.building!==this.lastBuilding){const asset=frame.building?this.geometryFor(frame.building):null;
   if(frame.building&&(!asset||asset.source_hash!==frame.building.source_hash))throw Error('Missing/mismatched CAD geometry; no room-box fallback');
   if(asset!==this.asset){if(asset)this.build(asset);else this.clearGeometry();}this.lastBuilding=frame.building;}
  if(frame.resultMeta!==this.lastResult)this.lastResult=frame.resultMeta;
  this.trimOpenings(frame.t_s??0);
  this.applyTransparency(frame.realView?.buildingTransparency??.7);
  if(frame.floor?.floor_id!==this.floorId||this.appliedBuild!==this.buildCount){this.floorId=frame.floor?.floor_id??null;for(const [id,g] of this.floorGroups)g.visible=this.floorId===null||id===this.floorId;this.appliedBuild=this.buildCount;}
  this.updateVisibility();
 }
 diagnostics(){return {buildCount:this.buildCount,ownedMaterials:0,borrowedMaterials:this.materialState.size,floors:this.floorGroups.size,drawObjects:this.sourceObjects.size,trimmedLines:this.trimmedLines,cornerSegments:this.cornerLines.reduce((n,l)=>n+l.geometry.attributes.position.count/2,0),ownedCornerResources:this.cornerResources.size};}
 dispose(){this.clearGeometry();this.lastBuilding=null;this.lastResult=null;this.geometryFor=null;super.dispose();}
}
export function createBuildingLayers(THREE,options){return [new BuildingLayer(THREE,options),...createEmptyLayers(THREE).filter(layer=>layer.constructor.id!=='building')];}
