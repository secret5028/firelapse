import fs from 'node:fs';
import assert from 'node:assert/strict';
import {groundReferenceSpec} from '../web/scene/ground_reference.js';
const hotel=JSON.parse(fs.readFileSync('data/parkmarine-hotel/building.json','utf8'));
const spec=groundReferenceSpec(hotel);
assert.equal(spec.floor,'1F');assert.equal(spec.z,15.7);assert.notEqual(spec.z,hotel.floors[0].z);
assert(spec.size>0&&spec.divisions>0);
assert.equal(groundReferenceSpec({floors:[{name:'B1',z:0,slab:[]}]}),null);
console.log(JSON.stringify(spec));
