import assert from 'node:assert/strict';
import {flameMaskAreaProfile,flameMaskedFootprint} from '../../simulation/viewer/legacy_real_view.js';
const bounds={x:0,y:0,w:10,d:20,ps:[{o:[[0,0],[10,0],[10,20],[0,20]],h:[]}]};
const image={width:512,height:512,data:new Uint8ClampedArray(512*512*4).fill(255)};
// An origin close to a wall must expand the enclosing circle to retain Q/HRRPUA inside.
const p=flameMaskAreaProfile(bounds,[.5,10],image);
for(const target of [5.64,54.18,150]){
 const f=flameMaskedFootprint(p,target,200);
 assert.equal(f.iterations,4);assert.ok(f.diameter>2*Math.sqrt(target/Math.PI));
 assert.ok(Math.abs(f.insideArea-target)/target<.02,JSON.stringify(f));
}
const full=flameMaskedFootprint(p,200,200);assert.equal(full.fullCell,true);assert.equal(full.insideArea,200);
assert.ok(full.diameter/2>=p.maxRadius+.3);
assert.equal(flameMaskedFootprint(p,0,200).diameter,0);
// Hole pixels are absent from the available fuel display area.
for(let y=128;y<384;y++)for(let x=128;x<384;x++)image.data[(y*512+x)*4]=0;
const hole=flameMaskAreaProfile(bounds,[.5,10],image);assert.equal(hole.availableArea,150);
assert.equal(flameMaskedFootprint(hole,200,200).insideArea,150);
console.log('Masked area: near-wall growth, four bisections, full cell, holes: PASS');
