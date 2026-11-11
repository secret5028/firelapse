import assert from 'node:assert/strict';
import {adaptResult} from '../web/adapters/read.js';
import {fgiRollover} from '../web/adapters/fgi_rollover.js';

const building={building_id:'B',source_hash:'B',floors:[{rooms:[{room_id:'R',cells:[{cell_id:'C'}]}]}]};
const scenario={cad:{building_sha256:'B'},openings:[]};
const playback={engine_kind:'cfast_native',native_mapping:'fixed-r8-native-v3',condition_version:'physics_p0_v3',
 complete:true,building_sha256:'B',time_s:[0,10],fire_key:'C',rooms:[{key:'C',solver_id:'C',original_room:'R',cad_floor:'B3'}],
 solvers:{C:{conditions:{FGI:{gate:[false,false],scores:{degree:[null,null]},rollover:{active:[false,true]}},
 FO:{scores:{degree:[0,.5]}},backdraft:{scores:{degree:[null,1.5]}}}}},limits:['최소 누기 가정 적용: R, 총 0.02 m²']};
playback.solvers.C.floor_incident_kW_m2=[0.4,25];
const args={playback,scenario,building,resultId:'test'};
const result=await adaptResult(args);
assert.equal(result.cell_conditions.C[0].FGI.status,'not_applicable');
assert.equal(result.index_by_cell.C.backdraft[1],150);
assert.equal(result.cells.C.floor_incident_kW_m2[1],25);
for(const threshold of [50,100,200])assert.equal(fgiRollover(result,'C',1,threshold),true);
assert.equal(fgiRollover(result,'C',0,200),false);
assert.equal(fgiRollover(result,'C',0,200,true),true);
assert(!result.limits_text.some(s=>s.startsWith('구버전 지수')));
const old=await adaptResult({...args,playback:{...playback,condition_version:'physics_p0_v2'}});
assert(old.limits_text.some(s=>s.startsWith('구버전 지수')));
console.log('PASS: applicability, stored rollover independent of display threshold, legacy version notice');

// Merely configuring the exception policy must not claim a sizing rerun.
for(const [history,visible] of [[[],false],[[{area_m2:.1}],false],[[{area_m2:.1},{area_m2:.1}],false],[[{area_m2:.1},{area_m2:.2}],true]]){
 const checked=await adaptResult({...args,playback:{...playback,limits:['지하 압력 간략식: test','지하 환기 경로 가정: test'],basement_pressure:{history}}});
 assert.equal(checked.limits_text.some(s=>s.startsWith('지하 압력 간략식:')),visible);
 assert(checked.limits_text.some(s=>s.startsWith('지하 환기 경로 가정:')));
}
console.log('PASS: pressure resizing notice requires an actual area change');
