// Borrow extracted transport footprints and the CAD loader's shape conversion.
// Missing connectivity is not inferred; filtering remains in the display layer.
export function readLegacyCoreSource({building,groups,sourceHash,shapeFor}){
 if(!/^[a-f0-9]{64}$/.test(sourceHash)||typeof shapeFor!=='function')throw Error('CAD source hash and shape converter required');
 const floors=building.floors.map(floor=>{
  const matches=groups.filter(g=>g.name===floor.name);if(matches.length!==1)throw Error('Missing/duplicate CAD floor group: '+floor.name);
  return Object.freeze({id:floor.name,floor,group:matches[0]});
 });return Object.freeze({source_hash:sourceHash,floors:Object.freeze(floors),shapeFor});
}
