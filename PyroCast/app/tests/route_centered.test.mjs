import assert from 'node:assert/strict';
import {centerRoomSegments,roundedPath} from '../web/route/centered.js';
import {contains,distance} from '../web/route/graph.js';
import {crossesObstacle,expandedObstacle} from '../web/route/obstacles.js';
const room={id:'corridor',point:[10,1,0],corridor:true,polys:[{o:[[0,0],[20,0],[20,2],[0,2]],h:[]}],obstacles:[]};
const parts=[{a:[0,1,0],b:[20,1,0],length:20,room:'corridor',floor:'1F'}];
let layout=centerRoomSegments(parts,new Map([['corridor',room]]),contains);assert.equal(layout.warnings.length,0);assert(layout.segments.every(s=>Math.abs(s.a[1]-1)<.26));
const l={...room,id:'L',point:[1,1,0],polys:[{o:[[0,0],[8,0],[8,2],[2,2],[2,8],[0,8]],h:[]}]};
layout=centerRoomSegments([{a:[7.9,1,0],b:[1,7.9,0],length:10,room:'L',floor:'1F'}],new Map([['L',l]]),contains);assert.equal(layout.warnings.length,0);assert(layout.segments.length>4);for(const s of layout.segments)for(let i=0;i<=10;i++){const p=s.a.map((v,k)=>v+(s.b[k]-v)*i/10);assert(contains(p,l.polys),'curve crossed concave corridor wall');}
const ordinary={...room,id:'room',corridor:false,point:[10,1,0]};layout=centerRoomSegments([{...parts[0],a:[0,1,0],b:[2,0,0],room:'room'}],new Map([['room',ordinary]]),contains);assert(layout.segments.some(s=>distance(s.a,ordinary.point)<.9));
const obstacle={center_m:[10,1],size_m:[1,.5],clearance_m:.1};const obstructed={...room,id:'blocked',obstacles:[obstacle]};layout=centerRoomSegments([{...parts[0],room:'blocked'}],new Map([['blocked',obstructed]]),contains);assert.equal(layout.warnings.length,0);assert(layout.segments.every(s=>!crossesObstacle(s.a,s.b,expandedObstacle(obstacle))));
assert.deepEqual(roundedPath([[0,0,0],[1,0,0],[1,1,0]],()=>false),[[0,0,0],[1,0,0],[1,1,0]]);
console.log('PASS centered corridor, concave turn containment, room center, obstacle clearance, unsafe-rounding fallback');
