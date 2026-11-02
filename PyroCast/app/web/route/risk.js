import {RISK_COLORS} from '../scene/render_order.js';
const types=['FO','FGI','backdraft','rollover'];
const labels={FO:'FO',FGI:'FGI',backdraft:'백드래프트',rollover:'롤오버'};
export const ROUTE_CLEAR='#38bdf8';
export function routeSampleIndex(result,t){
 const times=result?.time_s;if(!times?.length||t<times[0])return -1;
 let lo=0,hi=times.length-1;while(lo<hi){const mid=Math.ceil((lo+hi)/2);if(times[mid]<=t)lo=mid;else hi=mid-1;}return lo;
}
// Display-only maximum over saved member-cell indices. No scalar room physics aggregate.
// Fixed 100/70 C-4 thresholds; independent of risk-border visibility/threshold controls.
export function routeRiskRows(route,{building,resultMeta,t_s,risk,route:settings}){
 const i=routeSampleIndex(resultMeta,t_s),history=risk?.history===true;
 const indices=history?resultMeta?.index_history_max:resultMeta?.index_by_cell;
 const rooms=new Map((building?.floors||[]).flatMap(f=>f.rooms).map(r=>[r.room_id,r]));
 const cache=new Map(),rows=[];
 function score(id){
  if(cache.has(id))return cache.get(id);
  let maximum=null,type=null,source_cell=null,missing=false;
  const cells=rooms.get(id)?.cells||[];
  for(const c of cells)for(const key of types){const value=history?indices?.[c.cell_id]?.[key]:i<0?null:indices?.[c.cell_id]?.[key]?.[i];
   if(!Number.isFinite(value)){missing=true;continue;}
   // Stable ties: first member and FO/FGI/backdraft/rollover order.
   if(maximum===null||value>maximum){maximum=value;type=key;source_cell=c.cell_id;}
  }
  const row={room:id,label:id?id.replace(/^CAD_/,'').replaceAll('_',' '):'외부',index:maximum,type,source_cell,
   phenomenon:maximum===null?(id?'미평가':'외부'):labels[type],partial:missing&&maximum!==null,
   color:maximum>=100?RISK_COLORS[type]:maximum>=70?RISK_COLORS.smoke:ROUTE_CLEAR};
  cache.set(id,row);return row;
 }
 for(const s of route.segments||[]){const last=rows.at(-1);
  if(last&&last.room===s.room){last.end_m=s.end;last.stairs+=s.stair?1:0;}
  else rows.push({...score(s.room),order:rows.length+1,start_m:s.start,end_m:s.end,stairs:s.stair?1:0});
 }
 for(const row of rows){row.hose_first=Math.floor((row.start_m+1e-8)/settings.hose_m)+1;row.hose_last=Math.max(row.hose_first,Math.ceil((row.end_m-1e-8)/settings.hose_m));}
 return {rows,sample_s:i<0?null:resultMeta.time_s[i],history};
}
