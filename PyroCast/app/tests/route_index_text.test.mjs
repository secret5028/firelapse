import assert from 'node:assert/strict';
import {routeIndexText} from '../web/panels/route.js';
for(const value of [null,undefined,NaN,0,1e-8,.49])assert.equal(routeIndexText(value),'—');
for(const [value,text] of [[.5,'1'],[69.7,'70'],[140.2,'140']])assert.equal(routeIndexText(value),text);
console.log('PASS route index: unavailable and rounded zero use dash; nonzero indices retain integer display');
