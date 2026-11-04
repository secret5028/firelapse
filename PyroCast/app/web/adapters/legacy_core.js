// Borrow extracted transport footprints and the CAD loader's shape conversion.
// Missing connectivity is not inferred; use recorded vertical links only.
import {parkmarineCoreEvidence} from './parkmarine_core_evidence.js';
// Display footprints are independent of room/simulation-graph classification.
// A matching building hash is mandatory; never stretch an axis beyond its CAD floors.
export function evidencedCoreTransport(building,floor,sourceHash,evidence=parkmarineCoreEvidence){
 if(sourceHash!==evidence.building_sha256)return null;
 return evidence.axes.flatMap(axis=>{
  const index=axis.nodes.findIndex(n=>n.floor===floor.name);if(index<0)return [];
  const n=axis.nodes[index],next=axis.nodes[index+1],target=building.floors.find(f=>f.name===next?.floor);
  const x=n.x-n.w/2,y=n.y-n.h/2;
  return [{id:axis.id,kind:axis.kind,region:[{o:[[x,y],[x+n.w,y],[x+n.w,y+n.h],[x,y+n.h]],h:[]}],
   connected:axis.nodes.length>1,to_floor:target?.name,rise_m:target?target.z-floor.z:0,meshes:[],
   assumption:'simplified_return_stair_display_only',direction_source:'short_axis_default',
   source:'per-floor CAD core footprint',source_core_index:n.source_core_index}];
 });
}
export function coreTransport(building,floor){
 if(floor.transport?.length)return floor.transport;
 const linked=new Set();
 for(const v of building.vertical_connections||[]){
  if(!['stair','elev'].includes(v.kind))continue;
  if(v.from_floor===floor.name)linked.add(v.from_core);
  if(v.to_floor===floor.name)linked.add(v.to_core);
 }
 return (building.core_nodes||[]).filter(n=>n.floor===floor.name&&linked.has(n.core_id)&&['stair','elev'].includes(n.kind)).flatMap(n=>{
  const room=floor.rooms?.find(r=>r.id===n.room_id);
  // An inherited elev_inside tag can contradict the explicit CAD label DA.
  // Suppress the misleading elevator visual, without changing simulation links.
  const names=room?.names||[];
  if(n.kind==='elev'&&names.some(s=>/^D\.?\s*A\.?$/i.test(s.trim()))&&!names.some(s=>/ELEV|승강기|엘리베이터/i.test(s)))return [];
  let region=room?.polys;
  if(!region?.length&&[n.x,n.y,n.w,n.h].every(Number.isFinite)&&n.w>0&&n.h>0){
   const x=n.x-n.w/2,y=n.y-n.h/2;region=[{o:[[x,y],[x+n.w,y],[x+n.w,y+n.h],[x,y+n.h]],h:[]}];
  }
  if(!region?.length)return [];
  const link=(building.vertical_connections||[]).find(v=>v.kind===n.kind&&v.from_floor===floor.name&&v.from_core===n.core_id);
  const target=building.floors.find(f=>f.name===link?.to_floor);
  return [{id:n.core_id,kind:n.kind,region,connected:true,meshes:[],source:'core_nodes + vertical_connections',room_id:n.room_id,
   to_floor:target?.name,rise_m:target?target.z-floor.z:0,
   assumption:'simplified_return_stair_display_only',direction_source:'short_axis_default'}];
 });
}
export function readLegacyCoreSource({building,groups,sourceHash,shapeFor}){
 if(!/^[a-f0-9]{64}$/.test(sourceHash)||typeof shapeFor!=='function')throw Error('CAD source hash and shape converter required');
 const floors=building.floors.map(floor=>{
  const matches=groups.filter(g=>g.name===floor.name);if(matches.length!==1)throw Error('Missing/duplicate CAD floor group: '+floor.name);
  const transport=evidencedCoreTransport(building,floor,sourceHash)??coreTransport(building,floor);
  return Object.freeze({id:floor.name,floor:transport===floor.transport?floor:{...floor,transport},group:matches[0]});
 });return Object.freeze({source_hash:sourceHash,floors:Object.freeze(floors),shapeFor});
}
