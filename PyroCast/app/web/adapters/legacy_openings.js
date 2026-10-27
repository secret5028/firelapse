// Read-only CAD-loader capability. No classification or opening-state inference.
export function readLegacyOpeningsSource({building,groups,sourceHash}){
 if(!/^[a-f0-9]{64}$/.test(sourceHash))throw Error('CAD source hash required');
 const floors=building.floors.map(floor=>{
  const matches=groups.filter(g=>g.name===floor.name);if(matches.length!==1)throw Error('Missing/duplicate CAD floor group: '+floor.name);
  return Object.freeze({id:floor.name,floor,group:matches[0]});
 });return Object.freeze({source_hash:sourceHash,floors:Object.freeze(floors)});
}
