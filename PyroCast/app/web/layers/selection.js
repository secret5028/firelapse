import {EmptyLayer} from './empty.js';
import {selectionOutlineMaterials,selectionOutlineGeometry,selectionOutlineMesh} from './selection_outline.js';
import {ROOM_PICK_LAYER} from '../scene/picking.js';

const polygons=row=>row.polygons_m.map(p=>({o:p.polygon_m,h:p.holes_m}));
export class SelectionLayer extends EmptyLayer {
 static id='selection';
 constructor(THREE){super(THREE);this.building=undefined;this.resultMeta=undefined;this.views=[];this.buildCount=0;}
 clearGeometry(){for(const resource of this.resources)resource.dispose();this.resources.clear();this.group?.clear();this.views=[];}
 build(building){this.clearGeometry();this.buildCount++;const T=this.THREE;
  const shape=p=>{const s=new T.Shape(p.o.map(v=>new T.Vector2(...v)));for(const h of p.h)s.holes.push(new T.Path(h.map(v=>new T.Vector2(...v))));return s;};
  const ribbonMaterials=selectionOutlineMaterials(T,r=>this.own(r));
  const pickMaterial=this.own(new T.MeshBasicMaterial({color:'#ffffff',side:T.DoubleSide,transparent:true,opacity:0,depthWrite:false}));
  for(const floor of building.floors)for(const room of floor.rooms){const sharedRibbons=new Map();
   const pickAreas=room.cells.length?room.cells:[{cell_id:null,polygons_m:room.polygons_m,legacy_display:{z_m:room.floor_z_m}}];
   for(const cell of pickAreas){const z=cell.legacy_display?.z_m;if(!Number.isFinite(z))throw Error('Selection requires adapter cell floor height');
    const group=new T.Group();group.name=cell.cell_id??room.room_id;this.group.add(group);
    const pick=new T.Mesh(this.own(new T.ShapeGeometry(polygons(cell).map(shape))),pickMaterial);pick.position.z=z+.07;
    pick.layers.set(ROOM_PICK_LAYER);
    pick.userData.liteRoom=cell.cell_id;pick.userData.roomId=room.room_id;pick.userData.floorId=floor.floor_id;group.add(pick);
    // Cell picks still highlight the original room perimeter, only at floor level.
    if(!sharedRibbons.has(z))sharedRibbons.set(z,selectionOutlineGeometry(T,r=>this.own(r),polygons(cell.cell_id===room.room_id?cell:room),z));
    const ribbon=selectionOutlineMesh(T,sharedRibbons.get(z),ribbonMaterials);ribbon.visible=false;group.add(ribbon);
    this.views.push({id:cell.cell_id,roomId:room.room_id,floorId:floor.floor_id,group,pick,ribbon});
   }
  }
 }
 setData(frame){if(this.state!=='mounted')throw Error('Layer is not mounted');this.frame=frame;
  if(frame.building!==this.building){if(frame.building)this.build(frame.building);else this.clearGeometry();this.building=frame.building;}
  if(frame.resultMeta!==this.resultMeta)this.resultMeta=frame.resultMeta;
  const chosen=frame.selection?.cell_id?this.views.find(v=>v.id===frame.selection.cell_id):this.views.find(v=>v.roomId===frame.selection?.room_id);
  for(const v of this.views){v.group.visible=frame.floor.floor_id===null||frame.floor.floor_id===v.floorId;v.ribbon.visible=v===chosen;}
  this.updateVisibility();
 }
 getPickPlanes(){if(!this.group?.visible)return [];return this.views.filter(v=>v.group.visible&&v.pick.visible).map(v=>v.pick);}
 diagnostics(){return {buildCount:this.buildCount,cells:this.views.length,resources:this.resources.size,pickPlanes:this.getPickPlanes().length,selectedCells:this.views.filter(v=>v.group.visible&&v.ribbon.visible&&this.group.visible).map(v=>v.id)};}
 dispose(){this.clearGeometry();this.building=null;this.resultMeta=null;super.dispose();}
}
