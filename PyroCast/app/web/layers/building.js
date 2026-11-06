import {missingDoorHeaders} from './door_headers.js';
import {wallCornerSegments,isWallMesh,isReplacedWallOutline} from './wall_corners.js';
import {EmptyLayer,createEmptyLayers} from './empty.js';
import {applyRenderPolicy} from '../scene/render_order.js';
import {wallOpeningVolumes,trimWallLineGeometry,trimWallJambFaces} from './wall_opening_lines.js';
// Borrow both CAD geometry and materials; restore install() colour overrides.
export class BuildingLayer extends EmptyLayer {
 static id='building';
 constructor(THREE,{geometryFor}={}){super(THREE);if(typeof geometryFor!=='function')throw Error('CAD geometry provider required');
  this.geometryFor=geometryFor;this.asset=null;this.lastBuilding=undefined;this.lastResult=undefined;this.floorId=undefined;this.floorGroups=new Map();this.sourceObjects=new Map();this.materialState=new Map();this.bindings=[];this.buildCount=0;this.cornerResources=new Set();this.cornerLines=[];this.outlineOccluders=[];this.replacedOutlines=new Set();this.basementMaterials=new Map();this.slabMaterials=new Map();this.headerResources=new Set();this.headerSources=[];this.sourceAsset=null;}
 clearCorners(){for(const {proxy} of this.outlineOccluders)proxy.removeFromParent();this.outlineOccluders=[];for(const line of this.cornerLines)line.removeFromParent();for(const r of this.cornerResources)r.dispose();this.cornerResources.clear();this.cornerLines=[];this.replacedOutlines.clear();}
 clearGeometry(){this.clearCorners();for(const [material,before] of this.materialState){material.color.copy(before.color);material.opacity=before.opacity;material.depthWrite=before.depthWrite;
   if(material.transparent!==before.transparent){material.transparent=before.transparent;material.needsUpdate=true;}}
  this.materialState.clear();for(const material of this.slabMaterials.keys())material.dispose();this.slabMaterials.clear();for(const material of this.basementMaterials.keys())material.dispose();this.basementMaterials.clear();for(const resource of this.resources)resource.dispose();this.resources.clear();this.group?.clear();this.floorGroups.clear();this.sourceObjects.clear();this.bindings=[];this.asset=null;this.sourceAsset=null;this.openingSignature=null;this.trimmedLines=0;for(const r of this.headerResources)r.dispose();this.headerResources.clear();for(const s of this.headerSources)s.parent=null;this.headerSources=[];}
 build(asset){const T=this.THREE;this.clearGeometry();this.sourceAsset=asset;this.buildCount++;
  const floors=asset.floors.map(f=>{const objects=[...f.objects],styles=[...f.styles];for(const band of missingDoorHeaders(T,f.floor||{})){
   const shapes=band.polys.map(p=>new T.Shape(p.o.map(v=>new T.Vector2(...v)))),geometry=new T.ExtrudeGeometry(shapes,{depth:band.z1-band.z0,bevelEnabled:false}),material=new T.MeshLambertMaterial({color:'#93acb5',transparent:true,opacity:.25,depthWrite:false,side:T.DoubleSide}),source=new T.Mesh(geometry,material);
   source.name=f.id+'_door_head';source.position.z=band.z0;source.parent=f.group;source.userData={displayHeader:true,openingId:band.opening_id};this.headerSources.push(source);this.headerResources.add(geometry);this.headerResources.add(material);objects.push(source);styles.push({color:'#b8c3cb',opacity:null});
  }return {...f,objects,styles};});this.asset={...asset,floors};asset=this.asset;
  for(const floor of asset.floors){const g=new T.Group();g.name=floor.id;g.position.copy(floor.group.position);g.quaternion.copy(floor.group.quaternion);g.scale.copy(floor.group.scale);this.group.add(g);this.floorGroups.set(floor.id,g);
   const parents=new Map([[floor.group,g]]),basement=/^(B\d+|지하\s*\d+층)$/i.test(floor.id),floorMaterials=new Map();
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
    // Isolate only basement display opacity, including when CAD floors share a material.
    if(basement){if(!floorMaterials.has(material)){const copy=material.clone();floorMaterials.set(material,copy);this.basementMaterials.set(copy,material);}object.material=floorMaterials.get(material);}
    // Floor slabs may share materials with walls and other floors: isolate the display override.
    if(source.isMesh&&(/_slab(?:_|$)/.test(source.name||'')||source.userData.floorSlab)){
     const base=object.material,copy=base.clone();object.material=copy;this.slabMaterials.set(copy,{base,floorId:floor.id});
    }
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
  const whole=(this.frame?.floor?.floor_id??null)===null;
  for(const [material,source] of this.basementMaterials){material.opacity=source.opacity*(whole ? .8 : 1);material.depthWrite=source.depthWrite;const transparent=source.transparent||material.opacity<1;if(material.transparent!==transparent){material.transparent=transparent;material.needsUpdate=true;}}
  for(const [material,{base,floorId}] of this.slabMaterials){
   const selected=this.frame?.floor?.floor_id===floorId;
   material.opacity=selected?alpha(.92):base.opacity;material.depthWrite=base.depthWrite;
   const transparent=selected?material.opacity<1:base.transparent;
   if(material.transparent!==transparent){material.transparent=transparent;material.needsUpdate=true;}
  }
  for(const {object,proxy} of this.outlineOccluders)proxy.visible=object.visible&&object.material.opacity>0;
  const dark=this.frame?.realView?.wallOutline!=='light';
  for(const line of this.cornerLines){line.material.color.set(dark?'#101820':'#8da8b7');line.material.opacity=alpha(dark?.8:.32)*(whole&&line.userData.basement ? .8 : 1);line.renderOrder=30;}

 }
 trimOpenings(time){
  const floors=this.asset?.floors||[],signature=JSON.stringify(floors.flatMap(f=>(f.floor?.openings||[]).filter(o=>o.display_schedule).map(o=>{let value=0;for(const [t,v] of o.display_schedule)if(t<=time)value=v;return value;})));
  if(signature===this.openingSignature)return;this.openingSignature=signature;this.trimmedLines=0;this.clearCorners();
  const volumes=floors.map(f=>wallOpeningVolumes(f.floor||{},time));
  for(const resource of this.resources)resource.dispose();this.resources.clear();
  floors.forEach((floor,i)=>{for(const source of floor.objects){const object=this.sourceObjects.get(source);if(!object)continue;
   const clipped=source.isMesh?trimWallJambFaces(this.THREE,source,floor.group,volumes[i]):trimWallLineGeometry(this.THREE,source,floor.group,volumes[i]);object.geometry=clipped?this.own(clipped):source.geometry;if(clipped&&source.isLineSegments)this.trimmedLines++;
  }
   // Late depth-only pass: preserve translucent wall colour, but hide rear wall
   // edges. Use the actual opening-trimmed mesh, never a solid room bounding box.
   const T=this.THREE,depthMaterial=new T.MeshBasicMaterial({colorWrite:false,depthWrite:true,depthTest:true,transparent:true,side:T.DoubleSide,polygonOffset:true,polygonOffsetFactor:1,polygonOffsetUnits:1});
   this.cornerResources.add(depthMaterial);
   for(const source of floor.objects){const object=this.sourceObjects.get(source);
    if(!object?.isMesh||!(isWallMesh(source)||/_slab(?:_|$)/.test(source.name||'')||source.userData.floorSlab))continue;
    const proxy=new T.Mesh(object.geometry,depthMaterial);proxy.name=source.name+'_outline_depth';proxy.position.copy(object.position);proxy.quaternion.copy(object.quaternion);proxy.scale.copy(object.scale);proxy.renderOrder=29;proxy.raycast=()=>{};object.parent.add(proxy);this.outlineOccluders.push({object,proxy});
   }
   const points=wallCornerSegments(this.THREE,floor,volumes[i]);if(points.length){
    const T=this.THREE,geometry=new T.BufferGeometry();geometry.setAttribute('position',new T.Float32BufferAttribute(points,3));
    const material=new T.LineBasicMaterial({color:'#101820',transparent:true,opacity:.8,linewidth:1,depthTest:true,depthWrite:false});
    const line=new T.LineSegments(geometry,material);line.name=floor.id+'_wall_corners';line.userData.basement=/^(B\d+|지하\s*\d+층)$/i.test(floor.id);line.userData.wallSources=floor.objects.filter(isWallMesh);// Draw real wall edges after smoke, before risk/selection; keep depth occlusion.
    line.renderOrder=30;line.raycast=()=>{};
    this.floorGroups.get(floor.id).add(line);this.cornerLines.push(line);this.cornerResources.add(geometry);this.cornerResources.add(material);
    // Existing per-piece wireframes would double the edge and expose seams again.
    for(const source of floor.objects)if(isReplacedWallOutline(this.THREE,source,floor)){const object=this.sourceObjects.get(source);object.visible=false;this.replacedOutlines.add(object);}
   }
  });
 }
 // Newly included stairs/glass may sit inside transformed or hidden groups.
 // Preserve that hierarchy instead of flattening their local coordinates.
 syncSource(){for(const line of this.cornerLines)line.visible=line.userData.wallSources.some(s=>s.visible);for(const {source,object} of this.bindings){object.visible=source.visible&&!this.replacedOutlines.has(object);object.position.copy(source.position);object.quaternion.copy(source.quaternion);object.scale.copy(source.scale);}
  for(const {object,proxy} of this.outlineOccluders){proxy.visible=object.visible&&object.material.opacity>0;proxy.position.copy(object.position);proxy.quaternion.copy(object.quaternion);proxy.scale.copy(object.scale);}
  for(const floor of this.asset?.floors||[]){const g=this.floorGroups.get(floor.id);g.position.copy(floor.group.position);g.quaternion.copy(floor.group.quaternion);g.scale.copy(floor.group.scale);g.visible=floor.group.visible&&(this.floorId===null||this.floorId===floor.id);}
 }
 setData(frame){if(this.state!=='mounted')throw Error('Layer is not mounted');this.frame=frame;
  if(frame.building!==this.lastBuilding){const asset=frame.building?this.geometryFor(frame.building):null;
   if(frame.building&&(!asset||asset.source_hash!==frame.building.source_hash))throw Error('Missing/mismatched CAD geometry; no room-box fallback');
   if(asset!==this.sourceAsset){if(asset)this.build(asset);else this.clearGeometry();}this.lastBuilding=frame.building;}
  if(frame.resultMeta!==this.lastResult)this.lastResult=frame.resultMeta;
  this.trimOpenings(frame.t_s??0);
  this.applyTransparency(frame.realView?.buildingTransparency??.7);
  if(frame.floor?.floor_id!==this.floorId||this.appliedBuild!==this.buildCount){this.floorId=frame.floor?.floor_id??null;for(const [id,g] of this.floorGroups)g.visible=this.floorId===null||id===this.floorId;this.appliedBuild=this.buildCount;}
  this.updateVisibility();
 }
 diagnostics(){return {outlineOccluders:this.outlineOccluders.length,inferredDoorHeaders:this.headerSources.length,buildCount:this.buildCount,ownedMaterials:this.basementMaterials.size+this.slabMaterials.size,borrowedMaterials:this.materialState.size,floors:this.floorGroups.size,drawObjects:this.sourceObjects.size,trimmedLines:this.trimmedLines,cornerSegments:this.cornerLines.reduce((n,l)=>n+l.geometry.attributes.position.count/2,0),ownedCornerResources:this.cornerResources.size};}
 dispose(){this.clearGeometry();this.lastBuilding=null;this.lastResult=null;this.geometryFor=null;super.dispose();}
}
export function createBuildingLayers(THREE,options){return [new BuildingLayer(THREE,options),...createEmptyLayers(THREE).filter(layer=>layer.constructor.id!=='building')];}
