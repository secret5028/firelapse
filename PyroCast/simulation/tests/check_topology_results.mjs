import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {smokeTimeline} from '../viewer/smoke_transport.js';

const read=name=>JSON.parse(readFileSync(new URL(`../results/topology_audit_20261022/${name}_corrected_30min/playback.json`,import.meta.url),'utf8'));
const floor=read('floor'),vertical=read('vertical');
for(const data of [floor,vertical]){
 assert.equal(data.complete,true);assert.equal(data.time_s.at(-1),1800);
 assert.equal(data.topology_corrections.length,9);
 for(const id of ['D1','D3'])assert.equal(data.openings.find(v=>v.id===`CAD_3F_${id}`).schedule[0][1],1);
 for(const id of ['W25','W26','W27','W28','W29','W30']){
  const v=data.openings.find(v=>v.id===`CAD_3F_${id}`);
  assert.equal(v.kind,'door_service');assert.equal(v.window_state,null);
 }
 for(const v of data.openings.filter(v=>v.kind==='open_passage'))assert(v.fraction.every(f=>f===1));
}
assert.equal(smokeTimeline(floor).filter(r=>r.first_s!==null).length,24);
assert.equal(floor.openings.filter(v=>v.type==='FLOOR').length,0);
assert.equal(vertical.scope,'single_floor_with_cores');assert.equal(vertical.rooms.length,82);
assert.equal(vertical.openings.filter(v=>v.type==='FLOOR').length,35);
assert(vertical.solid_groups.every(g=>g.cad_key.startsWith('CAD_3F_')),'Remote solid inventory must remain unevaluated');
const rows=smokeTimeline(vertical);
for(const f of ['4F','5F','6F','7F','PH'])assert(rows.some(r=>r.room.cad_floor===f&&r.first_s!==null),`No smoke observed on ${f}`);
assert(vertical.openings.some(v=>v.type==='FLOOR'&&[...v.ab,...v.ba].some(flow=>flow[3]>1e-10)),'Native floor flow must carry soot');
console.log('Verified: 9 CAD corrections, 24 smoky fire-floor rooms, 82 coupled compartments, native vertical soot transport.');
