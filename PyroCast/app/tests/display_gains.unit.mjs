import assert from 'node:assert/strict';
import {createStore} from '../web/state/store.js';
const store=createStore();
assert.equal(store.get('realView').smokeOpacity,.7);
assert.equal(store.get('realView').smokeGain,1);
assert.equal(store.get('realView').flameGain,1);
for(const [smokeGain,flameGain] of [[.3,.5],[1.5,2],[1,1]]){
 store.dispatch('realView/set',{smokeGain,flameGain});
 assert.equal(store.get('realView').smokeGain,smokeGain);
 assert.equal(store.get('realView').flameGain,flameGain);
 assert.equal(store.get('realView').smokeOpacity,.7);
}
for(const invalid of [{smokeGain:.29},{smokeGain:1.51},{flameGain:.49},{flameGain:2.01},{flameGain:NaN}])assert.throws(()=>store.dispatch('realView/set',invalid));
console.log('PASS display gain defaults, ranges, unchanged base opacity');
