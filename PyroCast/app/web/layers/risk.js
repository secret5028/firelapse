import {EmptyLayer} from './empty.js';
import {applyRenderPolicy} from '../scene/render_order.js';
import {boundarySegments,joinedSelectionRibbons,dashedRibbonVertices} from './risk_geometry.js';
import {roomFgiRollover} from '../adapters/fgi_rollover.js';

const types=['FO','FGI','backdraft'],colors=['#ef4444','#a855f7','#facc15'];
const polygons=row=>row.polygons_m.map(p=>({o:p.polygon_m,h:p.holes_m}));
export class RiskLayer extends EmptyLayer {
 static id='risk';
 constructor(THREE){super(THREE);this.building=undefined;this.resultMeta=undefined;this.views=[];this.rooms=[];this.buildCount=0;this.counts={};}
 clearGeometry(){for(const resource of this.resources)resource.dispose();this.resources.clear();this.group?.clear();this.views=[];this.rooms=[];}
 build(building){this.clearGeometry();this.buildCount++;const T=this.THREE;
  const shape=p=>{const s=new T.Shape(p.o.map(v=>new T.Vector2(...v)));for(const h of p.h)s.holes.push(new T.Path(h.map(v=>new T.Vector2(...v))));return s;};
  const lines=segments=>{const pts=[];for(const {a,b} of segments)pts.push(a[0],a[1],0,b[0],b[1],0);const g=this.own(new T.BufferGeometry());g.setAttribute('position',new T.Float32BufferAttribute(pts,3));return g;};
  for(const floor of building.floors)for(const room of floor.rooms){const members=[],original=polygons(room);
   for(const cell of room.cells){const meta=cell.legacy_display;if(!meta)throw Error('Risk display requires adapter legacy_display cell metadata');
    const ps=polygons(cell),isCell=cell.cell_id!==room.room_id,segments=boundarySegments({cad_polys:ps},isCell?{polys:original}:null);
    const group=new T.Group();group.name=cell.cell_id;this.group.add(group);
    const tint=new T.Mesh(this.own(new T.ShapeGeometry(ps.map(shape))),this.own(new T.MeshBasicMaterial({color:'#ffffff',transparent:true,opacity:0,side:T.DoubleSide,depthWrite:false})));
    tint.position.z=meta.z_m+.07;tint.raycast=()=>{};group.add(tint);
    const line=applyRenderPolicy(new T.LineSegments(lines(segments),this.own(new T.LineDashedMaterial({color:'#fff',dashSize:.4,gapSize:0,transparent:true,opacity:.95,depthTest:false,depthWrite:false}))),'cellOutline');
    line.computeLineDistances();line.raycast=()=>{};group.add(line);
    const interfaceLine=applyRenderPolicy(new T.LineSegments(lines(segments),this.own(new T.LineDashedMaterial({color:'#e7f2fa',dashSize:.35,gapSize:.2,transparent:true,opacity:.9,depthTest:false,depthWrite:false}))),'interfaceLine');
    interfaceLine.computeLineDistances();interfaceLine.raycast=()=>{};group.add(interfaceLine);
    const interfacePlane=applyRenderPolicy(new T.Mesh(this.own(tint.geometry.clone()),this.own(new T.MeshBasicMaterial({color:'#d8e9f5',transparent:true,opacity:.07,side:T.DoubleSide,depthTest:false,depthWrite:false}))),'interfacePlane');
    interfacePlane.raycast=()=>{};group.add(interfacePlane);
    const view={id:cell.cell_id,roomId:room.room_id,floorId:floor.floor_id,meta,isCell,group,tint,line,interfaceLine,interfacePlane};members.push(view);this.views.push(view);
   }
   if(!members.length)continue;
   const verts=[];for(const p of original)for(const ribbon of joinedSelectionRibbons({o:p.o,h:[]},.055,.04))for(let i=0;i<ribbon.outer.length;i++){
    const j=(i+1)%ribbon.outer.length,q=[ribbon.outer[i],ribbon.outer[j],ribbon.inner[j],ribbon.inner[i]];
    for(const k of [0,1,2,0,2,3])verts.push(q[k][0],q[k][1],0);
   }
   const historyVerts=dashedRibbonVertices(original.flatMap(p=>joinedSelectionRibbons({o:p.o,h:[]},.055,.04)));
   const createMeshes=vertices=>colors.map(color=>{const geo=this.own(new T.BufferGeometry());geo.setAttribute('position',new T.Float32BufferAttribute(vertices,3));
    const mesh=applyRenderPolicy(new T.Mesh(geo,this.own(new T.MeshBasicMaterial({color,side:T.DoubleSide,transparent:true,opacity:1,depthTest:false,depthWrite:false}))),'risk');mesh.raycast=()=>{};this.group.add(mesh);return mesh;});
   // Transparent objects share r35; create dashed ribbons before their solid overlay.
   const historyMeshes=createMeshes(historyVerts),meshes=createMeshes(verts);
   const cautionMesh=applyRenderPolicy(new T.Mesh(historyMeshes[0].geometry,this.own(historyMeshes[0].material.clone())),'risk');
   cautionMesh.material.color.set('#9ca3af');cautionMesh.raycast=()=>{};this.group.add(cautionMesh);
   const dots=[];
   for(const p of original)for(let i=0;i<p.o.length;i++){
    const a=p.o[i],b=p.o[(i+1)%p.o.length],length=Math.hypot(b[0]-a[0],b[1]-a[1]);
    for(let d=0;d<length;d+=2){const x=a[0]+(b[0]-a[0])*d/length,y=a[1]+(b[1]-a[1])*d/length;
     for(let k=0;k<8;k++){const u=k*Math.PI/4,v=(k+1)*Math.PI/4;dots.push(x,y,0,x+.10*Math.cos(u),y+.10*Math.sin(u),0,x+.10*Math.cos(v),y+.10*Math.sin(v),0);}
    }
   }
   const dotGeometry=this.own(new T.BufferGeometry());dotGeometry.setAttribute('position',new T.Float32BufferAttribute(dots,3));
   const rolloverDots=applyRenderPolicy(new T.Mesh(dotGeometry,this.own(new T.MeshBasicMaterial({color:'#f97316',side:T.DoubleSide,transparent:true,opacity:1,depthTest:false,depthWrite:false}))),'risk');
   rolloverDots.renderOrder=36;rolloverDots.name='FGI rollover dots';rolloverDots.raycast=()=>{};this.group.add(rolloverDots);
   this.rooms.push({id:room.room_id,floorId:floor.floor_id,members,meshes,historyMeshes,cautionMesh,rolloverDots});
  }
 }
 setData(frame){if(this.state!=='mounted')throw Error('Layer is not mounted');this.frame=frame;
  if(frame.building!==this.building){if(frame.building)this.build(frame.building);else this.clearGeometry();this.building=frame.building;}
  if(frame.resultMeta!==this.resultMeta)this.resultMeta=frame.resultMeta;
  this.updateVisibility();
 }
 tick(){this.rolloverRooms=[];const f=this.frame,r=f?.resultMeta;if(!r){this.counts={};this.activeRooms=[];this.cautionRooms=[];for(const v of this.views)v.group.visible=false;for(const row of this.rooms)[...row.meshes,...row.historyMeshes,row.cautionMesh,row.rolloverDots].forEach(m=>m.visible=false);return;}
  const series=f.series?.cells;if(!series)throw Error('Risk layer requires adapted cell series; raw playback is not supported');
  if(!r.index_by_cell)throw Error('Risk layer requires adapted saved indices');
  const {ribbon,caution}=f.risk.threshold;
  let i=0,hi=r.time_s.length-1;while(i<hi){const mid=Math.ceil((i+hi)/2);if(r.time_s[mid]<=f.t_s)i=mid;else hi=mid-1;}
  const history=f.risk.history===true;
  if(history&&!r.index_history_max)throw Error('Risk history requires whole-period maxima');
  const meetsIn=(data,id,type,threshold)=>f.risk.show[type]!==false&&Number.isFinite(data[id]?.[type]?.[i])&&data[id][type][i]>=threshold;
  const meets=(id,type,threshold)=>history?f.risk.show[type]!==false&&Number.isFinite(r.index_history_max[id]?.[type])&&r.index_history_max[id][type]>=threshold:meetsIn(r.index_by_cell,id,type,threshold);
  const roomRisk=new Set(),cautionRooms=new Set();this.counts=Object.fromEntries(types.map(k=>[k,0]));this.activeRooms=[];
  for(const row of this.rooms){const active=new Map(),current=new Set();
   for(const v of row.members){const s=series[v.id],h=Number.isFinite(s?.interface_m[i])?s.interface_m[i]:history?v.meta.height_m:null;if(!s||h===null)continue;
    for(const type of types){if(meets(v.id,type,ribbon))active.set(type,Math.min(active.get(type)??Infinity,h));if(meetsIn(r.index_by_cell,v.id,type,ribbon))current.add(type);}
   }
   const onFloor=f.floor.floor_id===null||f.floor.floor_id===row.floorId;
   if(active.size)roomRisk.add(row.id);
   const {height_m:height,z_m}=row.members[0].meta,base=Math.max(.16,Math.min(height-.5,...active.values()));
   row.meshes.forEach((m,j)=>{const visible=onFloor&&active.has(types[j])&&f.risk.show[types[j]]!==false,dashed=history&&!current.has(types[j]),hm=row.historyMeshes[j];
    m.visible=visible&&!dashed;hm.visible=visible&&history;hm.position.z=m.position.z=z_m+Math.min(height-.04,base+j*.14);if(visible)this.counts[types[j]]++;});
   const ids=row.members.map(v=>v.id),rollover=roomFgiRollover(r,ids,i,ribbon,history)===true,now=roomFgiRollover(r,ids,i,ribbon,false)===true;
   row.rolloverDots.visible=onFloor&&active.has('FGI')&&f.risk.show.FGI!==false&&rollover;
   row.rolloverDots.position.z=row.meshes[1].position.z+.015;row.rolloverDots.material.opacity=now?1:.55;
   if(row.rolloverDots.visible)this.rolloverRooms.push({room_id:row.id,current:now,historyOnly:!now});
   const attention=history&&onFloor&&!active.size&&f.risk.show.smoke!==false&&row.members.some(v=>types.some(type=>meets(v.id,type,caution)));
   row.cautionMesh.visible=attention;
   row.cautionMesh.position.z=z_m+Math.min(height-.04,Math.max(.16,Math.min(height-.5,...row.members.map(v=>series[v.id]?.interface_m[i]).filter(Number.isFinite))));
   if(attention)cautionRooms.add(row.id);
   if(onFloor&&active.size)this.activeRooms.push({room_id:row.id,types:[...active.keys()],historyOnly:[...active.keys()].filter(type=>history&&!current.has(type)),heights:row.meshes.map(m=>m.position.z)});
  }
  for(const v of this.views){const s=series[v.id];v.group.visible=(f.floor.floor_id===null||f.floor.floor_id===v.floorId)&&!!s;if(!s)continue;
   const height=v.meta.height_m,value=s.interface_m[i],h=Number.isFinite(value)?Math.max(0,Math.min(height,value)):null;
   const activeType=types.findIndex(type=>meets(v.id,type,ribbon)),isCaution=activeType<0&&f.risk.show.smoke!==false&&types.some(type=>meets(v.id,type,caution));
   const color=activeType>=0?colors[activeType]:isCaution?'#9ca3af':'';
   if(v.group.visible&&h!==null&&isCaution&&!roomRisk.has(v.roomId))cautionRooms.add(v.roomId);
   const selected=f.selection.cell_id===v.id||(!f.selection.cell_id&&f.selection.room_id===v.roomId);
   const hasInterface=f.layers.smoke&&!v.meta.single_zone&&s.legacy_optical.ODu[i]>0&&h!==null&&h>.05&&h<height-.05;
   v.interfaceLine.visible=hasInterface&&!color&&!roomRisk.has(v.roomId);v.interfaceLine.position.z=v.meta.z_m+(h??0);
   v.interfacePlane.visible=hasInterface&&selected&&!v.isCell;v.interfacePlane.position.z=v.meta.z_m+(h??0);
   v.line.position.z=v.meta.z_m+(h??0);v.line.visible=h!==null&&!!color&&!roomRisk.has(v.roomId)&&!(history&&isCaution);v.line.material.color.set(color||'#9ca3af');v.line.material.gapSize=r.boundary_by_cell[v.id]?.[i] ? .25 : 0;
   v.tint.material.color.set(color||'#fff');v.tint.material.opacity=color?.startsWith('#9c') ? .025 : color?.length ? .1 : 0;
  }
  this.cautionRooms=[...cautionRooms];this.counts.caution=cautionRooms.size;
 }
 summary(){const n=this.counts;return `외곽 위험 표시: FO ${n.FO||0}실 · FGI ${n.FGI||0}실(롤오버 상태 ${this.rolloverRooms?.length||0}실) · BD ${n.backdraft||0}실 (${this.frame?.risk.history?'현재 층/전 구간 최대':'현재 층/시점'}, 저장된 판정)`;}
 diagnostics(){return {buildCount:this.buildCount,rooms:this.rooms.length,cells:this.views.length,resources:this.resources.size,counts:this.counts,activeRooms:this.activeRooms||[],rolloverRooms:this.rolloverRooms||[],cautionRooms:this.cautionRooms||[]};}
 dispose(){this.clearGeometry();this.building=null;this.resultMeta=null;this.activeRooms=[];this.cautionRooms=[];super.dispose();}
}
