import assert from 'node:assert/strict';
import {latestRoomCases,resultListRows} from '../web/panels/result_list.js';
const floors=[{name:'5F',rooms:[{id:'R16',names:['객실-10']}]},{name:'B3',rooms:[{id:'R6',names:[]}]}];
const result={result_id:'S08',status:'complete',engine:{kind:'lite'},scenario:{origin_room_id:'CAD_5F_R16'}};
const cases=[{id:'S07',label:'5F R16 · MC S07'},{id:'S08',label:'5F R16 · MC S08'},{id:'b',label:'B3 R6 · 저장 결과'}];
const rows=resultListRows(cases,result,floors);
assert.equal(rows.filter(r=>r.active).length,1);
assert.equal(rows[0].id,'S08');assert.match(rows[0].label,/객실-10.*간략.*S08/);
assert.equal(rows.find(r=>r.id==='b').label,'B3 R6 · 저장 결과');
assert.equal(resultListRows([],result,floors).length,1);
assert.equal(resultListRows([],null,floors).length,0);
assert.equal(resultListRows([...cases,cases[0]],result,floors).length,3);
const native=resultListRows(cases,{...result,result_id:'native',engine:{kind:'cfast'}},floors);
assert.equal(native[0].id,'native');assert.match(native[0].label,/CFAST/);
assert.equal(resultListRows(cases,{...result,status:'failed'},floors).some(r=>r.active),false);
console.log('PASS: active-only highlight, current first, CAD names, unnamed rooms, fallback, deduplication, CFAST, failed exclusion');

const both=resultListRows([{id:'lite-case',label:'5F R16',engine_kind:'pyrocast_lite'},{id:'native-case',label:'5F R16',engine_kind:'cfast_native'}],null,floors);
assert.deepEqual(both.map(r=>r.engineLabel),['간략','CFAST 원본']);
assert.equal(new Set(both.map(r=>r.id)).size,2,'same origin retains two independently selectable engines');
assert.equal(rows.find(r=>r.id==='b').engineLabel,'방식 미확인');
assert.equal(native[0].engineLabel,'CFAST 원본');
assert.equal(rows[0].engineLabel,'간략');
console.log('PASS: distinct engines for same room, saved metadata, unknown never assumed lite');

const runs=resultListRows([{id:'a',label:'5F R16 · MC S00',engine_kind:'pyrocast_lite',duration_s:60,saved_at_ms:1793866167503,run_id:'mc-one-123abc'},{id:'b',label:'5F R16 · MC S00',engine_kind:'pyrocast_lite',duration_s:3600,saved_at_ms:1793867167503,run_id:'mc-two-456def'}],null,floors);
assert.match(runs[0].detail,/1분/);assert.match(runs[1].detail,/60분/);assert.notEqual(runs[0].detail,runs[1].detail);assert.doesNotMatch(runs[1].detail,/456def/);assert.equal(runs[1].run_id,'mc-two-456def');
console.log('PASS: distinct duration, saved date; batch retained only as metadata for otherwise identical labels');

const selected=latestRoomCases([
 {id:'first',origin_room_id:'CAD_5F_R16',complete:true,saved_at_ms:5},
 {id:'running',origin_room_id:'CAD_5F_R16',complete:false,saved_at_ms:20},
 {id:'newest',origin_room_id:'CAD_5F_R16',complete:true,saved_at_ms:10},
 {id:'other-floor',origin_room_id:'CAD_7F_R16',complete:true,saved_at_ms:11},
 {id:'ambiguous',label:'5F R16',complete:true,saved_at_ms:99},
]);
assert.equal(selected.get('CAD_5F_R16').id,'newest');
assert.equal(selected.get('CAD_7F_R16').id,'other-floor');
assert.equal(selected.size,2,'Case labels cannot substitute for an exact saved origin');

const coverage=latestRoomCases([
 {id:'older',covered_room_ids:['CAD_5F_R1'],complete:true,saved_at_ms:5},
 {id:'newest',origin_room_id:'CAD_5F_R16',covered_room_ids:['CAD_5F_R1','CAD_5F_R16'],complete:true,saved_at_ms:10},
 {id:'unfinished',covered_room_ids:['CAD_5F_R1','CAD_6F_R1'],complete:false,saved_at_ms:20},
 {id:'legacy',origin_room_id:'CAD_7F_R1',complete:true},
], entry=>entry.covered_room_ids||[]);
assert.equal(coverage.get('CAD_5F_R1').id,'newest');
assert.equal(coverage.get('CAD_5F_R16').id,'newest');
assert.equal(coverage.size,2);
