import {elevatorDisplayFloor,nearElevator} from './elevator_doors.js';
import {coreTransport,evidencedCoreTransport} from './legacy_core.js';
// Read-only CAD-loader capability. CAD door supplements are display-only.
export function readLegacyOpeningsSource({building,groups,sourceHash}){
 if(!/^[a-f0-9]{64}$/.test(sourceHash))throw Error('CAD source hash required');
 const floors=building.floors.map(floor=>{
  const matches=groups.filter(g=>g.name===floor.name);if(matches.length!==1)throw Error('Missing/duplicate CAD floor group: '+floor.name);
  const cores=evidencedCoreTransport(building,floor,sourceHash)??coreTransport(building,floor);
  // Old gap classifiers also labelled unrelated wall gaps door_elev. Only show
  // these as elevator doors when associated with an actual recorded shaft.
  const openings=(floor.openings||[]).filter(o=>o.kind!=='door_elev'||nearElevator(o,cores));
  const source=openings.length===(floor.openings||[]).length?floor:{...floor,openings};
  return Object.freeze({id:floor.name,floor:elevatorDisplayFloor(source,sourceHash),group:matches[0]});
 });return Object.freeze({source_hash:sourceHash,floors:Object.freeze(floors)});
}
