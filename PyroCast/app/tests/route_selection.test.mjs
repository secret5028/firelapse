import {vehicleFitsGround} from '../web/scene/vehicle_placement.js';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {readRouteGraph,findRoute,contains} from '../web/route/graph.js';
import {exteriorPath} from '../web/route/exterior.js';
const b=JSON.parse(fs.readFileSync('data/parkmarine-hotel/building.json','utf8')),before=JSON.stringify(b),g=readRouteGraph(b);
assert.equal(g.edges.length,g.sourceEdgeCount);
assert.equal(g.mainEntrance.id,'CAD_1F_D18');assert.equal(g.mainEntrance.opening.leaves.length,0);
const target='CAD_5F_R16',r=findRoute(g,target);assert(!r.error);assert.equal(r.stairs,4);
const moved=findRoute(g,target,[-8,45,g.ground.z]);assert(!moved.error);assert.notEqual(moved.entry,r.entry);assert.notEqual(moved.length,r.length);
const choices=g.entrances.map(e=>findRoute({...g,entrances:[e]},target,[-8,45,g.ground.z])).filter(r=>!r.error);
assert(Math.abs(moved.length-Math.min(...choices.map(r=>r.length)))<1e-8,'shortest across all exterior entrances');
const other=findRoute(g,'CAD_5F_R6');assert(!other.error);assert.equal(other.target,'CAD_5F_R6');assert.notDeepEqual(other.edges,r.edges);
assert(findRoute(g,'absent').error);assert.equal(JSON.stringify(b),before);
const polys=[{o:[[0,0],[10,0],[10,10],[0,10]],h:[]}];
const outside=exteriorPath([-2,5,0],[10,5,0],polys,contains);assert(outside.length>=4);assert(outside.some(p=>p[1]===0||p[1]===10));
console.log(JSON.stringify({passed:true,default:{entry:r.entry,length:r.length,hoses:r.hoses,stairs:r.stairs},moved:{entry:moved.entry,length:moved.length,hoses:moved.hoses},sourceEdges:g.sourceEdgeCount,alternateRoom:other.target}));

const grid={min:{x:-20,y:-20},max:{x:20,y:20}};
assert(vehicleFitsGround([-10,5,0],grid,polys));
assert(!vehicleFitsGround([0,5,0],grid,polys),'truck crosses building');
assert(!vehicleFitsGround([-19,5,0],grid,polys),'centre inside grid but truck extends beyond');
assert(!vehicleFitsGround([-30,5,0],grid,polys),'outside grid');
assert(!vehicleFitsGround([-10,5,0],null,polys),'no grid means no placement');
console.log('vehicle placement: outside-only, whole footprint within displayed grid PASS');

assert(vehicleFitsGround([-2,5,0],grid,polys,Math.PI/2),"rotation fits narrow clearance");
assert(!vehicleFitsGround([-2,5,0],grid,polys,0),"unrotated body intersects wall");
assert(!vehicleFitsGround([-10,18,0],grid,polys,Math.PI/2),"rotated body exceeds grid");
