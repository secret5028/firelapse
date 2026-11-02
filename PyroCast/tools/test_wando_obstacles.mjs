import fs from 'node:fs';
import assert from 'node:assert/strict';
import {readRouteGraph,findRoute} from '../app/web/route/graph.js';
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const b=read('data/wando-coldstore/operating-building.json'),t=read('data/wando-coldstore/tactical.json');
const before=JSON.stringify(b),route=findRoute(readRouteGraph(b),'CAD_1F_R5');
assert.equal(b.obstacles.length,3);assert.equal(t.people.length,5);assert.equal(t.vehicle_symbols,false);
assert.deepEqual([...t.people.map(p=>p.number)].sort(),[1,2,3,4,5]);
assert.equal(route.hoses,2);assert.equal(route.graph_edges,8);assert.equal(route.stairs,0);
const plain=structuredClone(b);delete plain.obstacles;const old=findRoute(readRouteGraph(plain),'CAD_1F_R5');
assert.ok(Math.abs(old.length-23.140924039309574)<1e-9);assert.ok(route.length>old.length);
const minDistances={};
// Independent distance-to-unexpanded-box audit, sampling each returned segment.
for(const o of b.obstacles){let min=Infinity;for(const s of route.segments)if(s.room==='CAD_1F_R5')for(let i=0;i<=1000;i++){
 const p=s.a.map((v,k)=>v+(s.b[k]-v)*i/1000),dx=Math.max(0,Math.abs(p[0]-o.center_m[0])-o.size_m[0]/2),dy=Math.max(0,Math.abs(p[1]-o.center_m[1])-o.size_m[1]/2);
 min=Math.min(min,Math.hypot(dx,dy));
}minDistances[o.id]=min;assert.ok(min>=.5-1e-6,o.id+' clearance');}
const blocked=structuredClone(b);blocked.obstacles=[{id:'BARRIER',room_id:'R5',floor:'1F',center_m:[49.375,9,0],size_m:[8.75,1,2],clearance_m:.5}];
assert.ok(findRoute(readRouteGraph(blocked),'CAD_1F_R5').error,'no crossing a full-width barrier');
assert.equal(JSON.stringify(b),before,'graph does not mutate source');
const previous=read('simulation/results/github-publish-20261026/PyroCast/data/wando-coldstore/P1-playback.json'),current=read('data/wando-coldstore/P1-playback.json');
for(const key of ['solvers','fires','time_s','opening_states','provenance'])assert.deepEqual(current[key],previous[key],key+' unchanged');
const result={route,previous_length_m:old.length,minimum_clearances_m:minDistances,all_P1_physics_equal:true,blocked_case_rejected:true,vehicle_symbols:false,people:t.people,obstacles:b.obstacles};
fs.mkdirSync('simulation/results/wando_C11_r3_UI_20261102',{recursive:true});fs.writeFileSync('simulation/results/wando_C11_r3_UI_20261102/verification.json',JSON.stringify(result,null,2));
console.log(JSON.stringify({length:route.length,hoses:route.hoses,clearances:minDistances,blocked:true,physics_unchanged:true}));
