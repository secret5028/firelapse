// Browser presentation state only: never stores or changes simulation input.
export function viewStorageKey(path,hash){return `pyrocast:view:1:${path}:${hash}`;}
export function readSavedView(storage,key,hash){
 try{
  const v=JSON.parse(storage.getItem(key));
  if(v?.version!==1||v.hash!==hash||typeof v.case_id!=='string'||!v.case_id||v.case_id.length>200||!Number.isFinite(v.time_s)||v.time_s<0)return null;
  if(v.floor!==null&&typeof v.floor!=='string')return null;
  return {...v,tab:['building','result','display'].includes(v.tab)?v.tab:'result'};
 }catch{return null;}
}
export function writeSavedView(storage,key,value){try{storage.setItem(key,JSON.stringify({...value,version:1}));return true;}catch{return false;}}
export function restoredView(value,building,end){
 const floor=value.floor===null?null:building.floors.find(f=>f.floor_id===value.floor)?.floor_id??null;
 const room=building.floors.filter(f=>floor===null||f.floor_id===floor).flatMap(f=>f.rooms).find(r=>r.room_id===value.selection?.room_id);
 const cell=room?.cells.find(c=>c.cell_id===value.selection?.cell_id)?.cell_id??null;
 return {floor,time_s:Math.min(end,Math.max(0,value.time_s)),tab:value.tab,
  selection:{room_id:room?.room_id??null,cell_id:cell,source:'list'}};
}
