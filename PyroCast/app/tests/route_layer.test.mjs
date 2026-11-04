import assert from 'node:assert/strict';
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
import {RouteLayer} from '../web/layers/route.js';
import {readRouteGraph} from '../web/route/graph.js';
import {createStore} from '../web/state/store.js';
const T=await import(pathToFileURL(process.argv[3]).href);
globalThis.document={createElement:()=>({getContext:()=>({beginPath(){},arc(){},fill(){},stroke(){},fillText(){}})})};
const graph=readRouteGraph(JSON.parse(fs.readFileSync(process.argv[2],'utf8'))),store=createStore(),scene=new T.Scene();
const vehicle=new T.Group(),geometry=new T.BoxGeometry(),material=new T.MeshBasicMaterial();vehicle.add(new T.Mesh(geometry,material));
let borrowedDisposed=0;for(const r of [geometry,material])r.addEventListener('dispose',()=>borrowedDisposed++);
let notices=0;const layer=new RouteLayer(T,{graph,vehicleSource:vehicle,targetFor:()=> 'CAD_3F_R2',onChange:()=>notices++});layer.mount(scene,store);
let frame={route:store.get('route'),floor:{floor_id:'3F'}};layer.setData(frame);
assert.ok(layer.items.every(x=>x.object.visible===(x.floor==='3F')));
const resources=[...layer.resources];layer.setData({...frame,t_s:1420});assert.equal(notices,1);assert.deepEqual([...layer.resources],resources);
for(let i=0;i<50;i++){
 const old=[...layer.resources];let disposed=0;for(const r of old)r.addEventListener('dispose',()=>disposed++);
 frame={route:{...frame.route,vehicle:[59+i/100,31,5.1]},floor:{floor_id:null}};layer.setData(frame);
 assert.equal(disposed,old.length,'replacement disposes owned geometry, labels and materials');
}
layer.setData({...frame,route:{...frame.route,vehicle_visible:false}});assert.ok(layer.items.filter(x=>!x.route).every(x=>!x.object.visible));
const building={floors:[{rooms:[{room_id:'CAD_3F_R2',cells:[{cell_id:'R2_C0'}]}]}]};
const resultMeta={time_s:[1420,3600],index_by_cell:{R2_C0:{FO:[120,0],FGI:[0,0],backdraft:[0,0],rollover:[0,0]}},index_history_max:{R2_C0:{FO:120,FGI:0,backdraft:0,rollover:0}}};
const riskResources=[...layer.resources];
for(const [t_s,history,color] of [[1420,false,'ef4444'],[3600,true,'ef4444'],[3600,false,'38bdf8']]){
 layer.setData({...frame,building,resultMeta,t_s,risk:{history}});
 assert.equal(layer.roomMaterials.get('CAD_3F_R2').color.getHexString(),color);
 assert.deepEqual([...layer.resources],riskResources,'time/history changes only materials, never geometry');
}
for(const order of [37,38]){const mesh=layer.items.find(x=>x.object.isMesh&&x.object.renderOrder===order).object;
 const p=mesh.geometry.getAttribute('position'),a=new T.Vector3().fromBufferAttribute(p,0),b=new T.Vector3().fromBufferAttribute(p,5);
 assert.ok(Math.abs(a.distanceTo(b)-(order===38?.18:.28))<1e-5);assert.equal(mesh.material.depthTest,true);assert.equal(mesh.material.depthWrite,false);assert.equal(mesh.material.transparent,true);assert.equal(mesh.material.opacity,1);
}
layer.dispose();assert.equal(layer.resources.size,0);assert.equal(scene.children.length,0);assert.equal(borrowedDisposed,0);
geometry.dispose();material.dispose();console.log('route layer: 50 rebuilds, owned resources released, borrowed vehicle preserved, floor filter and data identity pass');
