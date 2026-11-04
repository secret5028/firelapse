import {EmptyLayer} from './empty.js';
import {applyRenderPolicy} from '../scene/render_order.js';
import {exteriorWindowFace} from './openings_geometry.js';

export class OpeningsLayer extends EmptyLayer {
 static id='openings';
 constructor(THREE,{geometryFor,camera}={}){super(THREE);
  if(typeof geometryFor!=='function'||!camera?.isCamera)throw Error('CAD source provider and camera required');
  this.geometryFor=geometryFor;this.camera=camera;this.asset=null;this.lastBuilding=undefined;this.lastResult=undefined;
  this.views=[];this.buildCount=0;this.tickCount=0;this.windowChecks=0;this.parts={window:true,door:true};
  this.cameraPosition=new THREE.Vector3();this.delta=new THREE.Vector3();this.center=new THREE.Vector3();this.normal=new THREE.Vector3();
 }
 clearGeometry(){for(const resource of this.resources)resource.dispose();this.resources.clear();this.group?.clear();this.views=[];this.asset=null;}
 build(asset){this.clearGeometry();this.asset=asset;this.buildCount++;const T=this.THREE;
  const windowMaterial=this.own(new T.LineBasicMaterial({color:'#62dcb0',linewidth:1})),doorMaterial=this.own(new T.LineBasicMaterial({color:'#e6bd68'}));
  const elevatorMaterial=this.own(new T.LineBasicMaterial({color:'#80d1ff',linewidth:1}));
  const fixedMaterials={};
  const annotate=(line,vertices,floor,opening,policy,normalVisible=true)=>{
   if(!fixedMaterials[policy]){const open=this.own(line.material.clone()),closed=this.own(line.material.clone());open.color.set('#62dcb0');closed.color.set('#c0cbd3');fixedMaterials[policy]={open,closed};}
   const {open:fixedOpen,closed:fixedClosed}=fixedMaterials[policy];
   const cross=applyRenderPolicy(new T.LineSegments(this.own(new T.BufferGeometry().setFromPoints([vertices[0],vertices[2],vertices[1],vertices[3]])),fixedClosed),policy);
   cross.name='closed-opening-mark';cross.raycast=()=>{};cross.visible=false;line.add(cross);
   Object.assign(line.userData,{openingId:`CAD_${floor.name}_${opening.id}`,normalMaterial:line.material,normalVisible,fixedOpen,fixedClosed,cross});
  };
  for(const row of asset.floors){const {floor}=row,windows=new T.Group(),doors=new T.Group();windows.name=floor.name+'-windows';doors.name=floor.name+'-doors';this.group.add(windows,doors);this.views.push({row,windows,doors});
   for(const opening of floor.openings||[]){
    const face=exteriorWindowFace(floor,opening);
    if(face){const line=applyRenderPolicy(new T.LineLoop(this.own(new T.BufferGeometry().setFromPoints(face.corners.map(p=>new T.Vector3(...p)))),windowMaterial),'openings.window');
     line.name=`exterior-window-${floor.name}-${opening.id}`;line.raycast=()=>{};
     line.userData.exteriorNormal=new T.Vector3(...face.normal);line.userData.exteriorCenter=new T.Vector3(...face.center);
     annotate(line,face.corners.map(p=>new T.Vector3(...p)),floor,opening,'openings.window');windows.add(line);}
    if(!['door','door_elev'].includes(opening.kind))continue;
    const normalVisible=opening.connection_status==='interior'||!!opening.display_frame;
    let spans=opening.display_span?[opening.display_span]:(opening.leaves||[]).map(l=>[l.hinge,l.closed]);
    if(!spans.length){let longest=0,span=null;for(const ring of opening.polys||[])for(let j=0;j<ring.length;j++){
     const a=ring[j],b=ring[(j+1)%ring.length],length=Math.hypot(b[0]-a[0],b[1]-a[1]);if(length>longest){longest=length;span=[a,b];}
    }if(span)spans=[span];}
    const height=opening.door_h||floor.door_h||2.1;
    for(const [a,b] of spans){const vertices=[[...a,opening.sill_m??.035],[...b,opening.sill_m??.035],[...b,height],[...a,height]].map(p=>new T.Vector3(...p));
     const line=applyRenderPolicy(new T.LineLoop(this.own(new T.BufferGeometry().setFromPoints(vertices)),opening.kind==='door_elev'?elevatorMaterial:doorMaterial),'openings.door');
     line.name=`interior-door-${floor.name}-${opening.id}`;line.raycast=()=>{};
     annotate(line,vertices,floor,opening,'openings.door',normalVisible);
     if(opening.kind==='door_elev'){
      const mid=[(a[0]+b[0])/2,(a[1]+b[1])/2];
      const seam=applyRenderPolicy(new T.Line(this.own(new T.BufferGeometry().setFromPoints([new T.Vector3(...mid,opening.sill_m??.035),new T.Vector3(...mid,height)])),elevatorMaterial),'openings.door');
      seam.raycast=()=>{};line.add(seam);line.userData.elevatorDoor=true;line.userData.displayOnly=!!opening.display_only;
     }
     doors.add(line);}
    if(opening.display_schedule){const [a,b]=spans[0],bottom=opening.sill_m??.035;
     const material=this.own(new T.MeshBasicMaterial({color:'#62dcb0',transparent:true,opacity:.35,side:T.DoubleSide,depthTest:false,depthWrite:false}));
     const fill=new T.Mesh(this.own(new T.PlaneGeometry(Math.hypot(b[0]-a[0],b[1]-a[1]),height-bottom)),material);
     fill.position.set((a[0]+b[0])/2,(a[1]+b[1])/2,(bottom+height)/2);fill.rotation.set(Math.PI/2,0,Math.atan2(b[1]-a[1],b[0]-a[0]));fill.renderOrder=34;
     fill.name='scheduled-opening-'+opening.id;fill.userData.schedule=opening.display_schedule;fill.raycast=()=>{};doors.add(fill);
    }
   }
  }
 }
 setData(frame){if(this.state!=='mounted')throw Error('Layer is not mounted');this.frame=frame;
  if(frame.building!==this.lastBuilding){const asset=frame.building?this.geometryFor(frame.building):null;
   if(frame.building&&(!asset||asset.source_hash!==frame.building.source_hash))throw Error('Missing/mismatched opening geometry');
   if(asset!==this.asset){if(asset)this.build(asset);else this.clearGeometry();}this.lastBuilding=frame.building;}
  if(frame.resultMeta!==this.lastResult)this.lastResult=frame.resultMeta;
  this.updateVisibility();
 }
 // Keep the two existing display checkboxes independent; no new store/UI here.
 setPartVisible(kind,value){if(!Object.hasOwn(this.parts,kind)||typeof value!=='boolean')throw Error('Invalid opening visibility');this.parts[kind]=value;}
 tick(){if(this.state!=='mounted'||!this.frame)return;this.tickCount++;
  this.camera.getWorldPosition(this.cameraPosition);const floorId=this.frame.floor?.floor_id??null;
  for(const {row,windows,doors} of this.views){
   const visible=row.group.visible&&(floorId===null||row.id===floorId);
   for(const group of [windows,doors]){group.position.copy(row.group.position);group.updateWorldMatrix(true,false);}
   const fixed=this.frame.fixedOpenings;
   windows.visible=visible&&(this.parts.window||!!fixed);doors.visible=visible&&(this.parts.door||!!fixed);
   const applyState=(line,normal)=>{const d=line.userData,s=fixed?.states[d.openingId];
    line.visible=!!s||(normal&&d.normalVisible);line.material=s?(s.open?d.fixedOpen:d.fixedClosed):d.normalMaterial;
    d.cross.visible=!!s&&!s.open;d.confirmedState=s??null;
   };
   for(const o of doors.children)if(o.userData.schedule){let f=0;for(const [t,v] of o.userData.schedule)if(t<=this.frame.t_s)f=v;o.visible=this.parts.door&&!fixed&&f>0;o.scale.x=Math.max(.00001,f);o.userData.displayFraction=f;}else applyState(o,this.parts.door);
   for(const line of windows.children){this.center.copy(line.userData.exteriorCenter).applyMatrix4(windows.matrixWorld);
    this.normal.copy(line.userData.exteriorNormal).transformDirection(windows.matrixWorld);
    applyState(line,this.parts.window);line.visible&&=this.delta.copy(this.cameraPosition).sub(this.center).dot(this.normal)>0;this.windowChecks++;}
  }
 }
 diagnostics(){return {buildCount:this.buildCount,ticks:this.tickCount,windowChecks:this.windowChecks,resources:this.resources.size,
  windows:this.views.reduce((n,v)=>n+v.windows.children.length,0),doors:this.views.reduce((n,v)=>n+v.doors.children.length,0)};}
 dispose(){this.clearGeometry();this.geometryFor=null;this.camera=null;this.lastBuilding=null;this.lastResult=null;super.dispose();}
}
