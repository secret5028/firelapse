import assert from 'node:assert/strict';
import {calculationStatus} from '../web/panels/explore.js';
const base={floor:'5F',origin:'R16',job:{available:true}};
assert.equal(calculationStatus(base),'계산 전');
assert.equal(calculationStatus({...base,floor:null}),'층 선택 필요');
assert.equal(calculationStatus({...base,dirty:true}),'가연물 변경 저장 필요');
assert.equal(calculationStatus({...base,pending:true}),'요청 중');
assert.equal(calculationStatus({...base,job:{running:true,completed:1,total:10}}),'계산 중 1/10');
const done={...base,job:{room:'R16',state:'completed'}};
assert.equal(calculationStatus(done),'저장 결과 있음','Old result must not certify current inputs');
assert.equal(calculationStatus({...done,verified:true}),'계산 완료');
assert.equal(calculationStatus({...done,changed:true}),'재계산 필요');
assert.equal(calculationStatus({...done,origin:'R3'}),'계산 전','Other origin is not complete');
assert.equal(calculationStatus({...done,job:{...done.job,failed_or_incomplete:1}}),'일부 미완료');
assert.equal(calculationStatus({...done,job:{room:'R16',state:'failed'}}),'계산 실패');
console.log('PASS: calculation states, partial failure, stale settings and unrelated saved origins');

assert.equal(calculationStatus({...done,job:{...done.job,total:2,failed_or_incomplete:2}}),'계산 실패 · 완주 0/2');
