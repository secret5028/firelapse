import {EmptyLayer} from './empty.js';
import {applyRenderPolicy} from '../scene/render_order.js';
import {joinedSelectionRibbons} from './risk_geometry.js';

const polygons=row=>row.polygons_m.map(p=>({o:p.polygon_m,h:p.holes_m}));
export class SelectionLayer extends EmptyLayer {
 static id='selection';
 constructor(THREE){super(THREE);this.building=undefined;this.resultMeta=undefined;this.views=[];this.buildCount=0;}
 clearGeometry(){for(const resource of this.resources)resource.dispose();this.resources.clear();this.group?.clear();this.views=[];}
 build(building){this.clearGeometry();this.buildCount++;const T=this.THREE;
  const shape=p=>{const s=new T.Shape(p.o.map(v=>new T.Vector2(...v)));for(const h of p.h)s.holes.push(new T.Path(h.map(v=>new T.Vector2(...v))));return s;};
  const ribbonMaterial=this.own(new T.MeshBasicMaterial({color:'#42e8ff',side:T.DoubleSide,transparent:true,opacity:.95,depthTest:false,depthWrite:false}));
  const pickMaterial=this.own(new T.MeshBasicMaterial({color:'#ffffff',side:T.DoubleSide,transparent:true,opacity:0,depthWrite:false}));
  for(const floor of building.floors)for(const room of floor.rooms){const sharedRibbons=new Map();
   for(const cell of room.cells){const z=cell.legacy_display?.z_m;if(!Number.isFinite(z))throw Error('Selection requires adapter cell floor height');
    const group=new T.Group();group.name=cell.cell_id;this.group.add(group);
    const pick=new T.Mesh(this.own(new T.ShapeGeometry(polygons(cell).map(shape))),pickMaterial);pick.position.z=z+.07;
    pick.userData.liteRoom=cell.cell_id;pick.userData.roomId=room.room_id;pick.userData.floorId=floor.floor_id;group.add(pick);
    if(!sharedRibbons.has(z)){const pts=[];
     // Select the original room, even when picking a partitioned solver cell.
     for(const p of polygons(cell.cell_id===room.room_id?cell:room))for(const ribbon of joinedSelectionRibbons(p))for(let i=0;i<ribbon.outer.length;i++){
      const j=(i+1)%ribbon.outer.length,q=[ribbon.outer[i],ribbon.outer[j],ribbon.inner[j],ribbon.inner[i]];
      for(const k of [0,1,2,0,2,3])pts.push(q[k][0],q[k][1],z+.08);
     }
     const geo=this.own(new T.BufferGeometry());geo.setAttribute('position',new T.Float32BufferAttribute(pts,3));sharedRibbons.set(z,geo);
    }
    const ribbon=applyRenderPolicy(new T.Mesh(sharedRibbons.get(z),ribbonMaterial),'selection');ribbon.visible=false;ribbon.raycast=()=>{};group.add(ribbon);
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
