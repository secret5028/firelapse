// One active immutable series payload, outside the observable metadata store.
function frozenCopy(value){const data=structuredClone(value);const visit=x=>{if(x&&typeof x==='object'){Object.values(x).forEach(visit);Object.freeze(x);}};visit(data);return data;}
export function createSeriesCache(){
 let key=null,data=null;
 return Object.freeze({replace(resultId,series){if(typeof resultId!=='string')throw Error('Result ID required');const next=frozenCopy(series);key=resultId;data=next;},
  get(resultId){return resultId===key?data:null;},clear(){key=null;data=null;},size(){return key===null?0:1;}});
}
