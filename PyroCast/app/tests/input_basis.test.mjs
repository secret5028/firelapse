import assert from 'node:assert/strict';
import {inputBasisLines} from '../web/panels/results.js';
const basis={ventilation:'기계 급배기 미입력',growth_kW_s2:1000/300**2,growth_basis:'용도별 기준',
 review_rooms:[{room:'R1',detail:'혼합 용도'},{room:'R2',detail:'출처 미확인'}]};
assert.deepEqual(inputBasisLines(null,'R1'),[]);
assert(inputBasisLines(basis,'R1').some(s=>s.includes('300초')));
assert(inputBasisLines(basis,'R1').some(s=>s.includes('선택 실 입력 확인 · 혼합 용도')));
assert(!inputBasisLines(basis,'R1').some(s=>s.startsWith('선택 실')&&s.includes('출처')));
assert(inputBasisLines(basis,'R2').some(s=>s.includes('2개 실')));
assert.equal(basis.review_rooms.length,2);
console.log('input basis display: passed');
