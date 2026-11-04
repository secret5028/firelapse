// Borrow extracted transport footprints and the CAD loader's shape conversion.
// Missing connectivity is not inferred; use recorded vertical links only.
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
  let region=room?.polys;
  if(!region?.length&&[n.x,n.y,n.w,n.h].every(Number.isFinite)&&n.w>0&&n.h>0){
   const x=n.x-n.w/2,y=n.y-n.h/2;region=[{o:[[x,y],[x+n.w,y],[x+n.w,y+n.h],[x,y+n.h]],h:[]}];
  }
  if(!region?.length)return [];
  return [{id:n.core_id,kind:n.kind,region,connected:true,meshes:[],source:'core_nodes + vertical_connections',room_id:n.room_id}];
 });
}
export function readLegacyCoreSource({building,groups,sourceHash,shapeFor}){
 if(!/^[a-f0-9]{64}$/.test(sourceHash)||typeof shapeFor!=='function')throw Error('CAD source hash and shape converter required');
 const floors=building.floors.map(floor=>{
  const matches=groups.filter(g=>g.name===floor.name);if(matches.length!==1)throw Error('Missing/duplicate CAD floor group: '+floor.name);
  const transport=coreTransport(building,floor);
  return Object.freeze({id:floor.name,floor:transport===floor.transport?floor:{...floor,transport},group:matches[0]});
 });return Object.freeze({source_hash:sourceHash,floors:Object.freeze(floors),shapeFor});
}
