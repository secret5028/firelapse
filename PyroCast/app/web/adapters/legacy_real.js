// Raw immutable playback capability, separate from the stage-1 result adapter.
export function readLegacyRealSource({building,groups,sourceHash,data,resultId}){
 if(!/^[a-f0-9]{64}$/.test(sourceHash)||typeof resultId!=='string')throw Error('Source hash/result ID required');
 if(groups.length!==building.floors.length||groups.some((g,i)=>g.name!==building.floors[i].name))throw Error('CAD floor group order mismatch');
 if(!Array.isArray(data?.rooms)||!Array.isArray(data.fires)||!data.solvers||!Array.isArray(data.time_s)||data.time_s.length<2)throw Error('Original playback required');
 return Object.freeze({source_hash:sourceHash,result_id:resultId,B:building,groups,data});
}
