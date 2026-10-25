import assert from 'node:assert/strict';
import {readFileSync,writeFileSync} from 'node:fs';
import {transportSignal,smokeTimeline,smokePresent} from '../viewer/smoke_transport.js';

assert.equal(transportSignal([1,0,0,0,1,20,1]).active,false,'Clean-air flow is not smoke');
assert.equal(transportSignal([0,0,0,.1,1,20,1]).active,false,'No mass flow means no visual transport');
assert.equal(transportSignal([1,0,0,.001,1,20,2]).active,true);
assert.equal(transportSignal([1,0,0,.001,1,20,Infinity]).active,false);
assert.equal(transportSignal([1,0,0,.001,1,20,0]).speed,0);
assert.equal(transportSignal([1,0,0,.001,1,20,100]).speed,8,'Visual speed is bounded, not a new simulation speed');
assert.equal(smokePresent({height_m:3},{h:3,upper:5,lower:0}),false,'Zero thickness must not create smoke');
assert.equal(smokePresent({height_m:3,single_zone:true},{h:3,upper:.2,lower:0}),true);

const p=new URL('../results/window_r8_20261022/floor_windows_30min/playback.json',import.meta.url);
const data=JSON.parse(readFileSync(p,'utf8')),before=data.final_input_sha256,rows=smokeTimeline(data);
assert.equal(rows.length,31);
assert.equal(rows.find(r=>r.room.key==='CAD_3F_R27').first_s,null,'No invented smoke in an unresolved isolated room');
const first=rows.filter(r=>r.first_s!==null).sort((a,b)=>a.first_s-b.first_s);
assert.equal(first[0].room.key,data.fire_key);
assert.equal(data.final_input_sha256,before);
const snapshot=time=>rows.filter(({room})=>{const s=data.solvers[room.solver_id],i=data.time_s.indexOf(time);return smokePresent(s,{h:s.h[i],upper:s.ODu[i],lower:s.ODl[i]});}).map(r=>r.room.key);
assert.equal(snapshot(0).length,0);
assert(snapshot(600).length>1);
const report={passed:true,rooms:rows.length,room_count_at_0:snapshot(0).length,room_count_at_600:snapshot(600).length,
 first_observations:first.map(r=>({room:r.room.key,time_s:r.first_s})),
 no_observation:rows.filter(r=>r.first_s===null).map(r=>r.room.key),
 native_input_sha256:before,simulation_rerun:false,transport:'native directional soot flow; visual trails only'};
writeFileSync(new URL('../results/window_r8_20261022/smoke-restoration-verification.json',import.meta.url),JSON.stringify(report,null,2));
console.log(JSON.stringify(report,null,2));
