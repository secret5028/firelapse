import {centerRoomSegments} from './centered.js';
import {exteriorPath} from './exterior.js';
// Read existing CAD connectivity only. No proximity links or fire simulation.
import {avoidObstacles} from './obstacles.js';
export const distance=(a,b)=>Math.hypot(...a.map((x,i)=>x-b[i]));
const id=(f,r)=>`CAD_${f}_${r}`;
function ringContains(p,ring){let inside=false;for(let i=0,j=ring.length-1;i<ring.length;j=i++){
 const a=ring[i],b=ring[j];if((a[1]>p[1])!==(b[1]>p[1])&&p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0])inside=!inside;
}return inside;}
export const contains=(p,polys)=>polys.some(q=>ringContains(p,q.o)&&!(q.h||[]).some(h=>ringContains(p,h)));
// Distance to the complete footprint; used for display vehicle clearance only.
export function footprintDistance(p,polys){
 if(contains(p,polys))return 0;
 let best=Infinity;
 for(const poly of polys)for(const ring of [poly.o,...(poly.h||[])])for(let i=0;i<ring.length;i++){
  const a=ring[i],b=ring[(i+1)%ring.length],dx=b[0]-a[0],dy=b[1]-a[1],l=dx*dx+dy*dy;
  const t=l?Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/l)):0;
  best=Math.min(best,Math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy));
 }return best;
}
const middle=points=>[0,1].map(i=>points.reduce((s,p)=>s+p[i],0)/points.length);
// Double-action CAD doors repeat each hinge for inward/outward swing arcs.
// Source order is not a geometric span: first/last can be the same point.
function doorSpan(opening){
 const leaves=opening.leaves||[],hinges=leaves.map(l=>l.hinge).filter(p=>p?.length>=2&&p.slice(0,2).every(Number.isFinite));
 let pair=null,longest=1e-8;
 const consider=(a,b)=>{if(!a||!b)return;const d=Math.hypot(b[0]-a[0],b[1]-a[1]);if(Number.isFinite(d)&&d>longest){longest=d;pair=[a,b];}};
 for(let i=0;i<hinges.length;i++)for(let j=i+1;j<hinges.length;j++)consider(hinges[i],hinges[j]);
 if(!pair)for(const leaf of leaves)consider(leaf.hinge,leaf.closed);
 if(!pair){const ring=opening.geometry_polys?.[0]?.o||opening.polys?.[0]||[];for(let i=0;i<ring.length;i++)consider(ring[i],ring[(i+1)%ring.length]);}
 return pair;
}
function aperturePoint(v,z){
 const hinges=(v.leaves||[]).map(l=>l.hinge),closed=(v.leaves||[]).map(l=>l.closed);
 const xy=hinges.length>1?middle(hinges):hinges.length?middle([hinges[0],closed[0]]):middle((v.geometry_polys?.[0]?.o||v.polys?.[0]||[]));
 return [...xy,z];
}
export function readRouteGraph(building){
 const rooms=new Map(),edges=[],entrances=[],floors=new Map(building.floors.map(f=>[f.name,f]));
 for(const f of building.floors)for(const r of f.rooms){rooms.set(id(f.name,r.id),{id:id(f.name,r.id),floor:f.name,point:building.route_targets?.[id(f.name,r.id)]??[...r.c,f.z],polys:r.polys,
  corridor:/복도|홀|corridor|hall/i.test((r.names||[]).join(' ')),
  obstacles:(building.obstacles||[]).filter(o=>o.room_id===r.id&&o.floor===f.name),
  elevator:(r.tags||[]).some(t=>['elev','elev_inside'].includes(t))});}
 for(const f of building.floors)for(const source of f.simulation_graph?.connections||[]){
  const v=f.openings.find(v=>v.id===source.id),[a,b]=source.sides,edge={id:id(f.name,source.id),source,kind:'door',a:id(f.name,a),b:id(f.name,b),floor:f.name,eligible:false};
  edges.push(edge);
  if(!v||!(source.kind.startsWith('door')||source.kind==='open_passage')||source.kind==='door_elev'){edge.exclusion='not_person_door';continue;}
  edge.point=aperturePoint(v,f.z);
  if(!edge.point.every(Number.isFinite)){edge.exclusion='missing_geometry';continue;}
  if(source.boundary==='exterior'){
   const room=rooms.get(edge.a)||rooms.get(edge.b);if(!room||room.elevator){edge.exclusion='missing_access';continue;}
   entrances.push({id:edge.id,room:room.id,point:edge.point,area:source.dimensions?.area_m2||0,floor:f.name,opening:v});edge.exclusion='entry_only';continue;
  }
  edge.eligible=rooms.has(edge.a)&&rooms.has(edge.b)&&!rooms.get(edge.a).elevator&&!rooms.get(edge.b).elevator;
  if(!edge.eligible)edge.exclusion='missing_room_or_elevator';
 }
 const cores=new Map((building.core_nodes||[]).map(n=>[`${n.floor}/${n.core_id}`,n]));
 (building.vertical_connections||[]).forEach((source,i)=>{
  const edge={id:`CAD_V${i}`,source,kind:'stair',eligible:false};edges.push(edge);
  if(source.kind!=='stair'){edge.exclusion='elevator_or_shaft';return;}
  const a=cores.get(`${source.from_floor}/${source.from_core}`),b=cores.get(`${source.to_floor}/${source.to_core}`);
  if(a?.access_room_ids.length!==1||b?.access_room_ids.length!==1){edge.exclusion='unresolved_core_access';return;}
  Object.assign(edge,{a:id(a.floor,a.access_room_ids[0]),b:id(b.floor,b.access_room_ids[0]),fromPoint:[a.x,a.y,floors.get(a.floor).z],toPoint:[b.x,b.y,floors.get(b.floor).z],floor:a.floor,toFloor:b.floor});
  edge.rise=Math.abs(edge.toPoint[2]-edge.fromPoint[2]);edge.eligible=rooms.has(edge.a)&&rooms.has(edge.b)&&edge.rise>0;
  if(!edge.eligible)edge.exclusion='unresolved_core_access';
 });
 const ground=floors.get('1F');if(!ground)throw Error('1층 지면 미확인');
 const candidates=entrances.filter(e=>e.floor==='1F').sort((a,b)=>b.area-a.area||a.id.localeCompare(b.id));
 const main=building.route_entry_id?candidates.find(e=>e.id===building.route_entry_id):candidates[0];if(!main)throw Error('1층 외부 문 미확인');
 const [p,q]=doorSpan(main.opening)||[];
 if(!p||!q)throw Error('주출입문 법선 미확인');
 const len=Math.hypot(q[0]-p[0],q[1]-p[1]);const normal=[-(q[1]-p[1])/len,(q[0]-p[0])/len];
 const footprint=building.floors.flatMap(f=>f.slab?.length?f.slab:f.rooms.flatMap(r=>r.polys||[]));
 const pts=footprint.flatMap(p=>p.o),extent=Math.hypot(Math.max(...pts.map(p=>p[0]))-Math.min(...pts.map(p=>p[0])),Math.max(...pts.map(p=>p[1]))-Math.min(...pts.map(p=>p[1])));
 const insideRoom=rooms.get(main.room).point;
 const sign=normal[0]*(main.point[0]-insideRoom[0])+normal[1]*(main.point[1]-insideRoom[1])>=0?1:-1;
 const front=[normal[0]*sign,normal[1]*sign];
 let vehicle=null;
 // Bounding circle of the 8 x 2.6 m vehicle guarantees >=10 m body clearance at any yaw.
 for(let d=10+Math.hypot(4,1.3);d<=extent+30&&!vehicle;d+=.5){
  const point=[main.point[0]+normal[0]*d*sign,main.point[1]+normal[1]*d*sign,ground.z];
  if(footprintDistance(point,footprint)>=10+Math.hypot(4,1.3)-1e-8){vehicle=point;break;}
 }
 if(!vehicle)throw Error('건물 외곽 10m 이격 차량 위치 미확인');
 return {rooms,edges,entrances:candidates,ground,defaultVehicle:vehicle,front,mainEntrance:main,
  sourceEdgeCount:building.floors.reduce((n,f)=>n+(f.simulation_graph?.connections.length||0),0)+(building.vertical_connections?.length||0),
  basis:'existing CAD simulation_graph.connections + vertical_connections, before fire-specific filters'};
}
export function findRoute(graph,target,vehicle=graph.defaultVehicle,{hose_m=15,stair_factor=1.5}={}){
 if(!(hose_m>0)||!(stair_factor>=1)||![hose_m,stair_factor,...vehicle].every(Number.isFinite))throw Error('유효한 경로 설정을 입력하세요');
 if(contains(vehicle,graph.ground.slab))return {error:'차량은 건물 밖 지면에 놓으세요'};
 if(!graph.rooms.has(target))return {error:'선택 실의 연결 정보 없음'};

 const adj=new Map([...graph.rooms.keys()].map(k=>[k,[]]));
 function segment(a,b,floor,room,stair=false,length=distance(a,b)){return {a,b,floor,room,stair,length};}
 function detour(parts){const out=[];for(const s of parts){const room=graph.rooms.get(s.room);
  if(s.stair||!room?.obstacles?.length){out.push(s);continue;}
  const path=avoidObstacles(s.a,s.b,room.obstacles,p=>contains(p,room.polys));if(!path)return null;
  for(let i=1;i<path.length;i++)out.push(segment(path[i-1],path[i],s.floor,s.room));
 }return out;}
 for(const e of graph.edges.filter(e=>e.eligible)){
  const ra=graph.rooms.get(e.a),rb=graph.rooms.get(e.b);let parts;
  if(e.kind==='stair')parts=[segment(ra.point,e.fromPoint,ra.floor,ra.id),segment(e.fromPoint,e.toPoint,ra.floor,ra.id,true,e.rise*stair_factor),segment(e.toPoint,rb.point,rb.floor,rb.id)];
  else parts=[segment(ra.point,e.point,ra.floor,ra.id),segment(e.point,rb.point,rb.floor,rb.id)];
  parts=detour(parts);if(!parts)continue;
  const length=parts.reduce((n,p)=>n+p.length,0);adj.get(e.a).push({to:e.b,e,parts,length});adj.get(e.b).push({to:e.a,e,parts:[...parts].reverse().map(p=>({...p,a:p.b,b:p.a})),length});
 }
 // Seed every registered exterior entrance: nearest door is not necessarily
 // the shortest total route to the chosen room.
 const starts=new Map(),best=new Map(),previous=new Map(),queue=[];
 for(const entry of graph.entrances){
  const first=graph.rooms.get(entry.room),outside=exteriorPath(vehicle,entry.point,graph.ground.slab,contains);if(!outside)continue;
  const start=detour([...outside.slice(1).map((p,i)=>segment(outside[i],p,'1F',null)),segment(entry.point,first.point,'1F',entry.room)]);
  if(!start)continue;const cost=start.reduce((n,p)=>n+p.length,0);
  if(cost<(best.get(entry.room)??Infinity)){best.set(entry.room,cost);starts.set(entry.room,{entry,start});queue.push([cost,entry.room]);}
 }
 while(queue.length){queue.sort((a,b)=>a[0]-b[0]||a[1].localeCompare(b[1]));const [cost,at]=queue.shift();if(cost!==best.get(at))continue;if(at===target)break;
  for(const step of adj.get(at)){const next=cost+step.length;if(next<(best.get(step.to)??Infinity)){best.set(step.to,next);previous.set(step.to,{from:at,...step});queue.push([next,step.to]);}}
 }
 if(!best.has(target))return {error:'외부 문에서 선택 실까지 확인된 연결 없음'};
 const steps=[];let at=target;while(previous.has(at)){const step=previous.get(at);steps.push(step);at=step.from;}steps.reverse();const {entry,start}=starts.get(at);
 const layout=centerRoomSegments([...start,...steps.flatMap(s=>s.parts)].filter(s=>s.length>1e-8),graph.rooms,contains);
 const segments=layout.segments;let length=0;for(const s of segments){s.start=length;length+=s.length;s.end=length;}
 const ticks=[];for(let m=hose_m;m<=length;m+=hose_m){const s=segments.find(s=>m<=s.end);const r=(m-s.start)/s.length;ticks.push({number:m/hose_m,point:s.a.map((x,i)=>x+(s.b[i]-x)*r),floor:s.floor});}
 return {layout_warnings:layout.warnings,target,entry:entry.id,vehicle,segments,ticks,length,hoses:Math.ceil(length/hose_m),stairs:steps.filter(s=>s.e.kind==='stair').length,
  edges:steps.map(s=>({id:s.e.id,from:s.from,to:s.to,kind:s.e.kind,length:s.length,rise:s.e.rise??0,stair_length:s.e.kind==='stair'?s.e.rise*stair_factor:0})),
  graph_edges:graph.edges.length,source_edges:graph.sourceEdgeCount,traversable_edges:graph.edges.filter(e=>e.eligible).length,
  limits:'실 중앙·복도 폭 중앙 우선, 모서리 곡선 경로. '+(layout.warnings.length?'일부 구간은 확인된 기존 경로 유지. ':'')+([...graph.rooms.values()].some(r=>r.obstacles?.length)?'등록 장애물 평면 외곽 0.5 m를 피하는 경로 중심선. 미등록 적재물·실제 호스 처짐·문 여는 시간 미반영. 실제 진입 안전을 보증하지 않음.':'실 중심–문/계단 연결점을 따르는 배치 경로. 미등록 실내 장애물·적재물·실제 호스 처짐·문 여는 시간은 미반영. 실제 진입 안전을 보증하지 않음.')};
}
