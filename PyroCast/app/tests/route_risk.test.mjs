import assert from 'node:assert/strict';
import {routeRiskRows,routeSampleIndex} from '../web/route/risk.js';
import {cumulativeIndexHistory} from '../web/adapters/read.js';
const cell=(FO,FGI,backdraft,rollover)=>({FO,FGI,backdraft,rollover});
const building={floors:[{rooms:[{room_id:'R2',cells:[{cell_id:'C0'},{cell_id:'C1'}]},{room_id:'R3',cells:[{cell_id:'C2'}]}]}]};
const index_by_cell={C0:cell([0,120,0],[0,110,0],[0,30,0],[0,20,0]),C1:cell([0,10,0],[0,140,0],[0,30,0],[0,20,0]),C2:cell([0,75,0],[null,null,null],[0,50,0],[0,99,0])};
const resultMeta={time_s:[0,10,20],index_by_cell,index_history_max:cumulativeIndexHistory(index_by_cell)};
const route={segments:[{room:null,start:0,end:5},{room:'R1',start:5,end:15},{room:'R2',start:15,end:20},{room:'R2',start:20,end:30},{room:'R3',start:30,end:40}]};
const frame={building,resultMeta,t_s:10,risk:{history:false,show:{FGI:false},threshold:{ribbon:200,caution:150}},route:{hose_m:15}};
const before=JSON.stringify(resultMeta),rows=routeRiskRows(route,frame).rows;
assert.equal(rows.length,4);assert.equal(rows[0].phenomenon,'외부');assert.equal(rows[1].phenomenon,'미평가');assert.equal(rows[1].index,null);
assert.equal(rows[2].index,140);assert.equal(rows[2].type,'FGI');assert.equal(rows[2].color,'#a855f7');assert.equal(rows[2].end_m,30);
assert.equal(rows[2].hose_first,2);assert.equal(rows[2].hose_last,2);assert.equal(rows[3].color,'#9ca3af');assert.equal(rows[3].partial,true);
assert.equal(routeRiskRows(route,{...frame,t_s:20}).rows[2].color,'#38bdf8');
assert.equal(routeRiskRows(route,{...frame,t_s:20,risk:{history:true}}).rows[2].color,'#a855f7');
assert.equal(routeRiskRows(route,{...frame,t_s:0,risk:{history:true}}).rows[2].index,0,'seeking back does not retain future danger');
assert.equal(routeSampleIndex(resultMeta,19),1);assert.equal(routeSampleIndex(resultMeta,-1),-1);
assert.equal(routeRiskRows(route,{...frame,t_s:-1}).rows[2].index,null);
for(const [value,color] of [[69.99,'#38bdf8'],[70,'#9ca3af'],[99.99,'#9ca3af'],[100,'#f97316']]){
 const changed=structuredClone(resultMeta);changed.index_by_cell.C2=cell([0,0,0],[0,0,0],[0,0,0],[0,value,0]);
 assert.equal(routeRiskRows(route,{...frame,resultMeta:changed}).rows[3].color,color);
}
assert.equal(JSON.stringify(resultMeta),before,'saved indices not modified');
console.log('PASS route risk: member maximum, fixed gates, missing data, ties, cumulative history, reverse seek, hose boundaries, no mutation');
