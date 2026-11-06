import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';
import {readLegacyOpeningsSource} from '../web/adapters/legacy_openings.js';
import {elevatorDisplayFloor} from '../web/adapters/elevator_doors.js';
import {elevatorDoorEvidence} from '../web/adapters/elevator_door_evidence.js';
import {OpeningsLayer} from '../web/layers/openings.js';
const T=await import(pathToFileURL(process.cwd()+'/cad-project/work/cad-web/local-resources/cad-assets/three.module.js'));
const bytes=fs.readFileSync('data/parkmarine-hotel/building.json'),hash=createHash('sha256').update(bytes).digest('hex'),b=JSON.parse(bytes),before=JSON.stringify(b);
const groups=b.floors.map(f=>{const g=new T.Group();g.name=f.name;g.position.z=f.z;return g;});
const asset=readLegacyOpeningsSource({building:b,groups,sourceHash:hash});
const doors=asset.floors.flatMap(f=>f.floor.openings.filter(o=>o.kind==='door_elev'));
assert.equal(doors.length,37);assert.equal(elevatorDoorEvidence[0].unresolved.length,0);
for(const f of b.floors)assert.equal(elevatorDisplayFloor(f,'0'.repeat(64)),f);
const testFloor=asset.floors.find(f=>f.id==='2F').floor;
assert.equal(elevatorDisplayFloor(testFloor,hash).openings.length,testFloor.openings.length);
for(const d of doors.filter(d=>d.display_only)){assert.equal(d.display_span.length,2);assert(d.source.length===2);assert.equal(d.normal[1],-1);}
const layer=new OpeningsLayer(T,{geometryFor:()=>asset,camera:new T.PerspectiveCamera()});layer.mount(new T.Scene(),{subscribe:()=>()=>{}});
const frame={building:{source_hash:hash},floor:{floor_id:'2F'},resultMeta:null,t_s:0};layer.setData(frame);layer.setVisible(true);layer.tick();
const view=layer.views.find(v=>v.row.id==='2F'),lines=view.doors.children.filter(l=>l.userData.elevatorDoor);
assert.equal(lines.length,3);assert(lines.every(l=>l.visible&&l.children.some(c=>c.isLine&&!c.isLineSegments)));
layer.setPartVisible('door',false);layer.tick();assert(lines.every(l=>!l.visible));layer.setPartVisible('door',true);layer.tick();assert(lines.every(l=>l.visible));
for(const f of b.floors){layer.setData({...frame,floor:{floor_id:f.name}});layer.tick();assert.deepEqual(layer.views.filter(v=>v.doors.visible).map(v=>v.row.id),[f.name]);}
layer.dispose();assert.equal(layer.resources.size,0);assert.equal(JSON.stringify(b),before);
// Other buildings use their existing door_elev records unchanged, without a hotel hash.
const factory=JSON.parse(fs.readFileSync('cad-project/building.json'));
const fg=factory.floors.map(f=>{const g=new T.Group();g.name=f.name;return g;});const fa=readLegacyOpeningsSource({building:factory,groups:fg,sourceHash:'b'.repeat(64)});
const fl=new OpeningsLayer(T,{geometryFor:()=>fa,camera:new T.PerspectiveCamera()});fl.mount(new T.Scene(),{subscribe:()=>()=>{}});fl.setData({...frame,building:{source_hash:'b'.repeat(64)}});
const explicit=fa.floors.flatMap(f=>f.floor.openings.filter(o=>o.kind==='door_elev')).length;assert(explicit>0);
assert.equal(fl.views.flatMap(v=>v.doors.children.filter(l=>l.userData.elevatorDoor)).length,explicit);fl.dispose();
console.log(JSON.stringify({hotelDoors:37,otherBuildingDoors:explicit,sourceUnchanged:true,toggleAndFloorFilter:true}));
