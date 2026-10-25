import assert from 'node:assert/strict';
import {gasVisualState} from '../viewer/gas_visual.js';
const basic={times:[375,380,385,390,395],power:[0,0,1000,500,0],room:'Hall',
 assumption:{room:'Hall',time_s:380}};
for(const time of [375,379,380])assert.equal(gasVisualState({...basic,time}).active,false);
assert.equal(gasVisualState({...basic,time:382.5}).q,500);
assert.equal(gasVisualState({...basic,time:385}).q,1000);
assert.equal(gasVisualState({...basic,time:395}).active,false);
assert.equal(gasVisualState({...basic,time:382,assumption:null}).active,false);
assert.equal(gasVisualState({...basic,time:382,room:'Another'}).active,false);
assert.equal(gasVisualState({...basic,time:385,power:[0,0,0,0,0]}).active,false);
assert.equal(gasVisualState({...basic,time:385,power:undefined}).active,false);
assert.equal(gasVisualState({...basic,time:385}).displayOnly,true);
console.log('Gas display gating passed: no early flame, no fuel-free flame, native bulk only.');
