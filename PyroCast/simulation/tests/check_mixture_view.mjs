import assert from 'node:assert/strict';
import {riskFor} from '../viewer/risk.js';
import {jetSignal} from '../viewer/ceiling_jets.js';
const times=[0,5],s={conditions:{rapid:{all_met:[true,false]},upper_gas:{all_met:[false,true]}},tags:{UPPER_GAS:[false,false]}};
assert.equal(riskFor(s,0,times).color,riskFor(s,0,times,'rapid').color);
assert.equal(riskFor(s,5,times).color,riskFor(s,5,times,'upper_gas').color,'Condition truth, not actual HRR, sets the border');
assert.equal(jetSignal(NaN),0);assert.equal(jetSignal(-1),0);assert.equal(jetSignal(12),8);
console.log('Condition-table parity, RAPID palette, zero/invalid jet visibility and visual speed cap passed.');
