import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {wallCornerSegments} from '../web/layers/wall_corners.js';
import {wallOpeningVolumes,outsideWallOpeningIntervals} from '../web/layers/wall_opening_lines.js';
import {BuildingLayer} from '../web/layers/building.js';
import {readLegacyBuildingSource} from '../web/adapters/legacy_building.js';
const T=await import(pathToFileURL(process.cwd()+'/simulation/results/github-publish-20261026/PyroCast/cad-project/work/cad-web/local-resources/cad-assets/three.module.js'));
const group=new T.Group(),objects=[];group.name='1F';group.position.set(5,8,10);group.rotation.z=.3;
function wall(x,z,w,h){const m=new T.Mesh(new T.BoxGeometry(w,.2,h),new T.MeshBasicMaterial({color:'#93acb5',transparent:true,opacity:.2}));m.name='1F_wall';m.position.set(x,0,z);group.add(m);objects.push(m);return m;}
wall(1,1.5,2,3);wall(3,1.5,2,3); // adjoining pieces: no x=2 internal verticals
const floor={id:'1F',group,objects},points=wallCornerSegments(T,floor,[]),segments=[];for(let i=0;i<points.length;i+=6)segments.push(points.slice(i,i+6));
assert(segments.length>0);assert(!segments.some(p=>Math.abs(p[0]-2)<1e-5&&Math.abs(p[3]-2)<1e-5&&Math.abs(p[2]-p[5])>.1));
const door={name:'1F',door_h:2,openings:[{id:'D',kind:'door',leaves:[{hinge:[0,0],closed:[1,0]}],polys:[[[0,-.1],[1,-.1],[1,.1],[0,.1]]]}]};
assert.deepEqual(outsideWallOpeningIntervals([.5,0,2],[.5,0,3],wallOpeningVolumes(door)),[]);
const clipped=wallCornerSegments(T,floor,wallOpeningVolumes(door));for(let i=0;i<clipped.length;i+=6){const p=clipped.slice(i,i+6);if(Math.abs(p[0])<1e-5&&Math.abs(p[3])<1e-5&&Math.abs(p[2]-p[5])>.1)assert(Math.max(p[2],p[5])<=2.00001);}
const asset=readLegacyBuildingSource({building:{floors:[door]},groups:[group],sourceHash:'a'.repeat(64)}),scene=new T.Scene(),layer=new BuildingLayer(T,{geometryFor:()=>asset});layer.mount(scene,{subscribe:()=>()=>{}});const frame={building:{source_hash:asset.source_hash},resultMeta:null,t_s:0,floor:{floor_id:'1F'}};layer.setData(frame);
assert(layer.cornerLines.length);assert.equal(layer.cornerLines[0].material.depthTest,true);assert.equal(layer.cornerLines[0].material.depthWrite,false);assert.equal(layer.cornerLines[0].material.linewidth,1);assert.equal(objects[0].material.opacity,.2);
const first=layer.cornerLines[0];layer.setData({...frame,t_s:1});assert.equal(first,layer.cornerLines[0]);let disposed=0;for(const r of layer.cornerResources)r.addEventListener('dispose',()=>disposed++);layer.dispose();assert.equal(disposed,2);assert.equal(layer.cornerResources.size,0);
console.log('PASS wall union seams / transformed floor / jamb extensions / thin depth-tested lines / wall transparency unchanged / cached geometry / resource disposal');
