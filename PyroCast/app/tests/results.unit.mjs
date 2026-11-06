import assert from 'node:assert/strict';
import fs from 'node:fs';
import {summarizeMCPlayback,selectedScores,resultTypes,resultNumber} from '../web/panels/results.js';
const fixture={complete:true,time_s:[0,10],rooms:[{key:'a',solver_id:'a',original_room:'R1'},{key:'b',solver_id:'b',original_room:'R1'},{key:'c',solver_id:'c',original_room:'R2'}],solvers:{}};
for(const id of ['a','b','c'])fixture.solvers[id]={conditions:Object.fromEntries(resultTypes.map(([k])=>[k,{scores:{degree:id==='c'?[null,.9]:[.5,1.2]}}]))};
const grouped=summarizeMCPlayback(fixture);assert.equal(grouped.FO.rooms,1);assert.equal(grouped.FO.peak,120);assert.equal(grouped.FO.unknown,true);assert.throws(()=>summarizeMCPlayback({...fixture,complete:false}));
const scores=selectedScores({cell_conditions:{a:{0:{FO:{bottleneck:'O',r_O:1.2}}}},index_by_cell:{a:{FO:[120],FGI:[null]}}},'a',0);assert.equal(scores[0].factor,120);assert.equal(scores[0].bottleneck,'산소');assert.equal(scores[1].value,null);
if (fs.existsSync('simulation/results/lite_v8_mc_R2_10_20261026/S00/playback.json')) {
const reports=[];for(let i=0;i<10;i++){const id='S'+String(i).padStart(2,'0'),p=JSON.parse(fs.readFileSync(`simulation/results/lite_v8_mc_R2_10_20261026/${id}/playback.json`,'utf8'));reports.push({id,summary:summarizeMCPlayback(p)});}
const max=Object.fromEntries(resultTypes.map(([k])=>[k,Math.max(...reports.map(r=>r.summary[k].rooms))]));console.log(JSON.stringify({passed:true,checks:'cell dedup, null preservation, incomplete rejection, saved bottleneck, ten saved samples',max,rows:reports}));

} else console.log('SKIP: evidence folder missing');

// Rounding must not display a negative zero; retain genuine negatives and missing data.
assert.equal(resultNumber(-1e-8), '0');assert.equal(resultNumber(-.00001,1),'0.0');assert.equal(resultNumber(-.16,1),'-0.2');assert.equal(resultNumber(null),'—');
