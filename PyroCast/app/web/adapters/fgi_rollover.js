// The border threshold is display state: never bake it into a separate index.
export function fgiRollover(result,cell,index,threshold=100,history=false){
 const r=result?.fgi_rollover_by_cell?.[cell];
 if(!r)return null;
 if(r.excluded_origin===true)return false;
 if(r.excluded_origin!==false)return null;
 if(history)return Number.isFinite(r.eligible_peak_index)?r.eligible_peak_index>=threshold:r.status==='evaluated'?false:null;
 const ignition=r.ignition[index],score=result.index_by_cell?.[cell]?.FGI?.[index];
 if(ignition===false)return false;
 return ignition===true&&Number.isFinite(score)?score>=threshold:null;
}
export function roomFgiRollover(result,cells,index,threshold=100,history=false){
 const values=cells.map(c=>fgiRollover(result,typeof c==='string'?c:c.cell_id,index,threshold,history));
 return values.includes(true)?true:values.includes(null)?null:false;
}
