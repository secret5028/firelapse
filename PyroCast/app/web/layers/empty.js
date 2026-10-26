// Stage 2 creates containers only. Existing shaders remain untouched.
import {applyRenderPolicy} from '../scene/render_order.js';
export class EmptyLayer {
 static id='empty';
 constructor(THREE){this.THREE=THREE;this.state='new';this.resources=new Set();this.unsubscribers=[];this.group=null;this.frame=null;}
 mount(scene,store){
  if(this.state!=='new')throw Error('Layer cannot be mounted again');this.state='mounted';this.scene=scene;
  this.group=new this.THREE.Group();this.group.name=this.constructor.id;scene.add(this.group);
  if(this.constructor.id==='openings'){
   for(const kind of ['window','door']){const group=new this.THREE.Group();group.name=kind;applyRenderPolicy(group,'openings.'+kind);this.group.add(group);}
  }else applyRenderPolicy(this.group,this.constructor.id);
  this.unsubscribers.push(store.subscribe('floor',()=>{}));
 }
 own(resource){if(this.state!=='mounted')throw Error('Layer is not mounted');this.resources.add(resource);return resource;}
 setData(frame){if(this.state!=='mounted')throw Error('Layer is not mounted');this.frame=frame;this.updateVisibility();}
 setVisible(value){this.visible=value;this.updateVisibility();}
 updateVisibility(){if(this.group)this.group.visible=this.visible!==false&&(this.constructor.id!=='core'||this.frame?.floor?.floor_id===null);}
 tick(){}
 dispose(){if(this.state==='disposed')return;for(const off of this.unsubscribers)off();this.unsubscribers=[];
  for(const resource of this.resources)resource.dispose();this.resources.clear();this.group?.removeFromParent();this.group?.clear();
  this.group=null;this.scene=null;this.frame=null;this.state='disposed';}
}
export const LAYER_IDS=Object.freeze(['building','openings','core','smoke','flame','plume','risk','selection']);
export const LAYER_TYPES=Object.freeze(LAYER_IDS.map(id=>class extends EmptyLayer {static id=id;}));
export const createEmptyLayers=THREE=>LAYER_TYPES.map(Type=>new Type(THREE));
