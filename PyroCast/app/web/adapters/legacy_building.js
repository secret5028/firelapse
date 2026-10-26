// References are borrowed from the CAD loader, never from another display layer.
export function readLegacyBuildingSource({building,groups,sourceHash}){
 if(!/^[a-f0-9]{64}$/.test(sourceHash))throw Error('CAD source hash required');
 const floors=building.floors.map(f=>{
  const matches=groups.filter(g=>g.name===f.name);if(matches.length!==1)throw Error('Missing/duplicate CAD floor group: '+f.name);
  const group=matches[0],names=new Set([f.name+'_slab',f.name+'_ceiling',...f.bands.map(b=>f.name+'_'+b.kind),...f.rooms.map(r=>f.name+'_'+r.id)]);
  const objects=group.children.filter(o=>(o.isMesh||o.isLine)&&(names.has(o.name)||o.userData.cadOutline));
  return Object.freeze({id:f.name,group,objects:Object.freeze(objects)});
 });return Object.freeze({source_hash:sourceHash,floors:Object.freeze(floors)});
}
