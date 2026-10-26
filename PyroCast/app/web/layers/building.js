import {EmptyLayer,createEmptyLayers} from './empty.js';
import {applyRenderPolicy} from '../scene/render_order.js';
// Borrow CAD geometry; clone materials. Original colours are never overwritten.
export class BuildingLayer extends EmptyLayer {
 static id='building';
 constructor(THREE,{geometryFor}={}){super(THREE);if(typeof geometryFor!=='function')throw Error('CAD geometry provider required');
  this.geometryFor=geometryFor;this.asset=null;this.lastBuilding=undefined;this.lastResult=undefined;this.floorId=undefined;this.floorGroups=new Map();this.buildCount=0;}
 clearGeometry(){for(const resource of this.resources)resource.dispose();this.resources.clear();this.group?.clear();this.floorGroups.clear();this.asset=null;}
 build(asset){const T=this.THREE;this.clearGeometry();this.asset=asset;this.buildCount++;
  for(const floor of asset.floors){const g=new T.Group();g.name=floor.id;g.position.copy(floor.group.position);g.quaternion.copy(floor.group.quaternion);g.scale.copy(floor.group.scale);this.group.add(g);this.floorGroups.set(floor.id,g);
   for(const source of floor.objects){const object=source.clone(false);
    const material=original=>{const m=this.own(original.clone());if(m.color){
     if(object.name?.startsWith(floor.id+'_'))m.color.set('#aab7c0');
     else if([0x8a8a8a,0x8b5a2b,0x93acb5].includes(m.color.getHex()))m.color.set('#b8c3cb');
     if(object.isLineSegments&&object.userData.cadOutline){m.color.set('#bdcbd5');m.opacity=.42;}
    }return m;};
    object.material=Array.isArray(source.material)?source.material.map(material):material(source.material);
    applyRenderPolicy(object,'building');g.add(object);
   }
  }
 }
 setData(frame){if(this.state!=='mounted')throw Error('Layer is not mounted');this.frame=frame;
  if(frame.building!==this.lastBuilding){const asset=frame.building?this.geometryFor(frame.building):null;
   if(frame.building&&(!asset||asset.source_hash!==frame.building.source_hash))throw Error('Missing/mismatched CAD geometry; no room-box fallback');
   if(asset!==this.asset){if(asset)this.build(asset);else this.clearGeometry();}this.lastBuilding=frame.building;}
  if(frame.resultMeta!==this.lastResult)this.lastResult=frame.resultMeta;
  if(frame.floor?.floor_id!==this.floorId||this.appliedBuild!==this.buildCount){this.floorId=frame.floor?.floor_id??null;for(const [id,g] of this.floorGroups)g.visible=this.floorId===null||id===this.floorId;this.appliedBuild=this.buildCount;}
  this.updateVisibility();
 }
 diagnostics(){return {buildCount:this.buildCount,ownedMaterials:this.resources.size,floors:this.floorGroups.size};}
 dispose(){this.clearGeometry();this.lastBuilding=null;this.lastResult=null;this.geometryFor=null;super.dispose();}
}
export function createBuildingLayers(THREE,options){return [new BuildingLayer(THREE,options),...createEmptyLayers(THREE).filter(layer=>layer.constructor.id!=='building')];}
