import assert from 'node:assert/strict';
import {riskFor} from '../viewer/risk.js';
const times=[0,5],state={tags:{RO:[true,true],VENT_FLAME:[true,true]},Qbulk_kW:[0,25]};
assert.equal(riskFor(state,0,times).color,null,'Vent-only combustion must not paint the room as upper-layer burning');
assert.ok(riskFor(state,5,times).keys.includes('UPPER_GAS'));
const unknown={conditions:{fo:{all_met:[null,true]}}};
assert.equal(riskFor(unknown,0,times,'fo').met,null);
assert.equal(riskFor(unknown,5,times,'fo').met,true);
console.log('Opening combustion and upper-layer risk colours are independent; unknown conditions remain unknown.');
