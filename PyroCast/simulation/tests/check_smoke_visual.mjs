import assert from 'node:assert/strict';
import {smokeLayerVisibility} from '../viewer/smoke_visual.js';
const base={enabled:true,smokeEnabled:true,opticalDensity:2,thickness:1,riskColor:null};
assert.deepEqual(smokeLayerVisibility(base),{visible:true,outlineVisible:false});
assert.deepEqual(smokeLayerVisibility({...base,riskColor:'#b16cff'}),{visible:true,outlineVisible:true});
assert.deepEqual(smokeLayerVisibility({...base,smokeEnabled:false,riskColor:'#ee4055'}),{visible:false,outlineVisible:false});
assert.equal(smokeLayerVisibility({...base,opticalDensity:0,riskColor:'#b16cff'}).visible,false);
assert.equal(smokeLayerVisibility({...base,thickness:0}).visible,false);
console.log('Smoke visibility passed: all computed smoke independent of hazard flags; coloured boundary conditional.');
