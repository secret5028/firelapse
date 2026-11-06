import assert from 'node:assert/strict';
import fs from 'node:fs';
import {buildingTable,doorCategory,openingCounts} from '../web/panels/building.js';
import {attentionRanking} from '../web/adapters/attention.js';
// Isolated ranking fixture; production saved attention changes after each calculation.
const folder='simulation/results/ui_refactor_stage4_item5_20261028/';
const payload=JSON.parse(fs.readFileSync(folder+'screening-fixture.json','utf8')),doors=JSON.parse(fs.readFileSync(folder+'doors-fixture.json','utf8'));
const table=buildingTable(payload.score),counts=openingCounts(doors.rows,payload.score.opening_states);
assert.equal(counts.confirmed+counts.inferred+counts.ordinary+counts.unknown,doors.rows.length);assert.equal(counts.window,43);
assert.equal(table.find(r=>r.id==='CAD_3F_R2').load,1800);assert(table.some(r=>r.id==='CAD_3F_R14'));assert.equal(doorCategory({door_class:'fire',confidence:'user'}),'confirmed');
const savedAttention={records:payload.comparison.rows.flatMap(row=>row.state_results.map(c=>({identity:[c.room,c.state,c.result_folder,c.times?.total_s,c.burning_room_count,c.first_FO_s,c.safe_end_s],attention_room_count:({'CAD_3F_R3':2,'CAD_3F_R2':1,'CAD_3F_R1':0})[row.room]??0,unknown_rooms:[],complete:true})))};
const before=JSON.stringify(payload),ranked=attentionRanking(payload.comparison,savedAttention);assert.equal(JSON.stringify(payload),before);
assert.equal(ranked.find(r=>r.room==='CAD_3F_R3').attention_room_count,2);assert.equal(ranked.find(r=>r.room==='CAD_3F_R2').attention_room_count,1);assert.equal(ranked.find(r=>r.room==='CAD_3F_R1').attention_room_count,0);
const absent=attentionRanking(payload.comparison,{records:[]});assert(absent.every(r=>r.rank2===null&&r.attention_room_count===null));
const stale=structuredClone(payload.comparison);stale.rows[0].state_results[0].times.total_s+=1;assert.equal(attentionRanking(stale,savedAttention).find(r=>r.room===stale.rows[0].room).rank2,null);
const report={passed:true,counts,room_rows:table.length,ranking:ranked.map(r=>({room:r.room,before_rank:payload.comparison.rows.find(x=>x.room===r.room).rank2,old_smoke_count:payload.comparison.rows.find(x=>x.room===r.room).smoke_risk_room_count,rank:r.rank2,burning:r.burning_room_count,attention:r.attention_room_count,first_FO_s:r.first_FO_s})),unmatched_is_unknown:true};
fs.writeFileSync(folder+'unit.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));
