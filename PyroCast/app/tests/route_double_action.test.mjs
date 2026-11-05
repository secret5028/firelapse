import assert from 'node:assert/strict';
import fs from 'node:fs';
import {readRouteGraph,findRoute,footprintDistance} from '../web/route/graph.js';
const building=JSON.parse(fs.readFileSync('data/model-library/intech-cad/building.json','utf8'));
const original=JSON.stringify(building),g=readRouteGraph(building),route=findRoute(g,'CAD_1F_R3');
assert(g.defaultVehicle.every(Number.isFinite));assert(!route.error);assert(route.segments.length>0);
assert(route.segments.every(s=>[...s.a,...s.b,s.length].every(Number.isFinite)));
assert(footprintDistance(g.defaultVehicle,building.floors.flatMap(f=>f.slab))-Math.hypot(4,1.3)>=10-1e-8);
assert.equal(g.mainEntrance.id,'CAD_1F_D0');assert.equal(route.hoses,Math.ceil(route.length/15));
// Preserve physics input and source edge set; only vehicle direction changes.
assert.equal(JSON.stringify(building),original);assert.equal(g.edges.length,g.sourceEdgeCount);
for(const reverse of [false,true]){
 const b=structuredClone(building),door=b.floors[0].openings.find(o=>o.id==='D0');
 if(reverse)door.leaves.reverse();else door.leaves=[door.leaves[0],door.leaves[1]];
 const other=readRouteGraph(b);assert.deepEqual(other.defaultVehicle,g.defaultVehicle);
 assert(Math.abs(findRoute(other,'CAD_1F_R3').length-route.length)<1e-7);
}
console.log(JSON.stringify({passed:true,entry:g.mainEntrance.id,vehicle:g.defaultVehicle,length:route.length,hoses:route.hoses,segments:route.segments.length}));
