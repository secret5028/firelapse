import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import fs from 'node:fs';
import {wallOpeningVolumes,outsideOpeningIntervals,trimWallLineGeometry} from '../web/layers/wall_opening_lines.js';
import {BuildingLayer} from '../web/layers/building.js';
import {readLegacyBuildingSource} from '../web/adapters/legacy_building.js';
const T=await import(pathToFileURL(process.cwd()+'/simulation/results/github-publish-20261026/PyroCast/cad-project/work/cad-web/local-resources/cad-assets/three.module.js'));
const floor={name:'2F',door_h:2.1,openings:[{id:'D',kind:'door',leaves:[{hinge:[2,0],closed:[4,0]}]}]};
const cuts=wallOpeningVolumes(floor),kept=outsideOpeningIntervals([0,0,1],[6,0,1],cuts);
assert.equal(kept.length,2);assert(Math.abs(kept[0][1]*6-2.005)<1e-8);assert(Math.abs(kept[1][0]*6-3.995)<1e-8);
assert.deepEqual(outsideOpeningIntervals([0,1,1],[6,1,1],cuts),[[0,1]]); // nearby parallel wall
assert.deepEqual(outsideOpeningIntervals([2,0,0],[2,0,2.1],cuts),[[0,1]]); // jamb
assert.deepEqual(outsideOpeningIntervals([0,0,2.1],[6,0,2.1],cuts),[[0,1]]); // lintel
const win={name:'1F',openings:[{id:'W',kind:'window',sill:1,head:2,polys:[[[2,-.1],[4,-.1],[4,.1],[2,.1]]]}]};
assert.equal(outsideOpeningIntervals([0,0,1.5],[6,0,1.5],wallOpeningVolumes(win)).length,2);
assert.deepEqual(outsideOpeningIntervals([0,0,.5],[6,0,.5],wallOpeningVolumes(win)),[[0,1]]);
const diagonal={name:'3F',openings:[{id:'D',kind:'door',leaves:[{hinge:[0,0],closed:[2,2]}]}]};
assert.equal(outsideOpeningIntervals([1,1,0],[1,1,3],wallOpeningVolumes(diagonal)).length,1);
const scheduled=structuredClone(floor);scheduled.openings[0].display_schedule=[[0,0],[10,.5],[20,1]];
assert.equal(wallOpeningVolumes(scheduled,0).length,0);assert.equal(outsideOpeningIntervals([2.1,0,0],[2.1,0,3],wallOpeningVolumes(scheduled,10)).length,1);
assert.equal(outsideOpeningIntervals([2.1,0,0],[2.1,0,3],wallOpeningVolumes(scheduled,20))[0][0]>.6,true);
const group=new T.Group();group.name='2F';group.position.set(3,4,9);group.rotation.z=.4;
const source=new T.LineSegments(new T.BufferGeometry().setFromPoints([new T.Vector3(0,0,1),new T.Vector3(6,0,1)]),new T.LineBasicMaterial({transparent:true,opacity:.42}));source.name='2F_edge';group.add(source);
const original=Array.from(source.geometry.attributes.position.array),result=trimWallLineGeometry(T,source,group,cuts);assert.equal(result.attributes.position.count,4);assert.deepEqual(Array.from(source.geometry.attributes.position.array),original);result.dispose();
const asset=readLegacyBuildingSource({building:{floors:[scheduled]},groups:[group],sourceHash:'a'.repeat(64)});let disposed=0;
const layer=new BuildingLayer(T,{geometryFor:()=>asset});layer.mount(new T.Scene(),{subscribe:()=>()=>{}});
const frame={building:{source_hash:asset.source_hash},floor:{floor_id:'2F'},resultMeta:null,t_s:0};layer.setData(frame);assert.equal(layer.resources.size,0);
layer.setData({...frame,t_s:10});const half=layer.sourceObjects.get(source).geometry;half.addEventListener('dispose',()=>disposed++);
layer.setData({...frame,t_s:11});assert.equal(layer.sourceObjects.get(source).geometry,half);layer.setData({...frame,t_s:20});assert.equal(disposed,1);assert.equal(layer.sourceObjects.get(source).material,source.material);layer.dispose();assert.equal(source.material.opacity,.42);
const cad=JSON.parse(fs.readFileSync('simulation/results/github-publish-20261026/PyroCast/cad-project/building.json','utf8'));
console.log(JSON.stringify({door:true,window:true,diagonal:true,transformed_floor:true,frames_preserved:true,schedule:true,no_rebuild_same_fraction:true,source_unchanged:true,other_building_cuts:cad.floors.map(f=>({floor:f.name,count:wallOpeningVolumes(f).length}))}));
