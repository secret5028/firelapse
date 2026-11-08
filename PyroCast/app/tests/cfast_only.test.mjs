import assert from 'node:assert/strict';
import {mcEstimate,nativeProgress,calculationStatus} from '../web/panels/explore.js';
assert.equal(mcEstimate({wall_s:120,completed:2,engine_kind:'pyrocast_lite'},10),null);
assert.equal(mcEstimate({wall_s:120,completed:2,engine_kind:'cfast_native'},10),600);
assert.equal(nativeProgress({last_native_time_s:1420,requested_horizon_s:3600}),'해석 23:40 / 60:00');
assert.equal(nativeProgress({last_native_time_s:null,requested_horizon_s:3600}),'');
assert.match(calculationStatus({job:{running:true,completed:1,total:3,native_progress:{last_native_time_s:1420,requested_horizon_s:3600}}}),/23:40/);
assert.match(calculationStatus({floor:'B3',origin:'R6',job:{state:'completed',room:'R6',total:2,excluded_physically_invalid:2}}),/적용 가능한 표본 없음/);
console.log('PASS: CFAST-only MC estimate and native progress display');
