import fs from 'node:fs';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {evidencedCoreTransport} from '../web/adapters/legacy_core.js';
import {parkmarineCoreEvidence as evidence} from '../web/adapters/parkmarine_core_evidence.js';
const raw=fs.readFileSync('data/parkmarine-hotel/building.json'),b=JSON.parse(raw),before=JSON.stringify(b),hash=crypto.createHash('sha256').update(raw).digest('hex');
assert.equal(hash,evidence.building_sha256);
const floors=b.floors.map(f=>({floor:f.name,z:f.z,h:f.h,cores:evidencedCoreTransport(b,f,hash)}));
const expected=[['stair','B3','PH',14],['elev','B2','PH',13],['elev','B2','10F',12],['stair','B1','10F',11],['elev','B1','PH',12]];
for(const [i,axis] of evidence.axes.entries()){
 const rows=floors.filter(f=>f.cores.some(c=>c.id===axis.id));
 assert.deepEqual([axis.kind,rows[0].floor,rows.at(-1).floor,rows.length],expected[i]);
 for(let j=0;j<rows.length;j++){
  const r=rows[j],core=r.cores.find(c=>c.id===axis.id),node=axis.nodes[j];
  assert.equal(core.region[0].o[0][0],node.x-node.w/2);
  assert.equal(core.region[0].o[0][1],node.y-node.h/2);
  if(j+1<rows.length){
   assert.equal(core.to_floor,rows[j+1].floor);assert(Math.abs(r.z+core.rise_m-rows[j+1].z)<1e-9);assert(Math.abs(r.z+r.h-rows[j+1].z)<1e-9);
   assert.equal(b.floors.findIndex(f=>f.name===rows[j+1].floor),b.floors.findIndex(f=>f.name===r.floor)+1);
   const next=axis.nodes[j+1];
   assert(Math.min(node.x+node.w/2,next.x+next.w/2)>Math.max(node.x-node.w/2,next.x-next.w/2));
   assert(Math.min(node.y+node.h/2,next.y+next.h/2)>Math.max(node.y-node.h/2,next.y-next.h/2));
  }
  else assert.equal(core.to_floor,undefined);
 }
}
for(const name of ['2F','3F','4F','9F','10F'])assert.equal(floors.find(f=>f.floor===name).cores.filter(c=>c.kind==='elev').length,3);
assert.equal(evidencedCoreTransport(b,b.floors[0],'wrong-hash'),null);
assert.equal(JSON.stringify(b),before);
console.log(JSON.stringify({floorSegments:floors.reduce((n,f)=>n+f.cores.length,0),axes:expected,gaps:0,buildingUnchanged:true}));
