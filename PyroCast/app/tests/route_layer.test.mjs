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
layer.dispose();assert.equal(layer.resources.size,0);assert.equal(scene.children.length,0);assert.equal(borrowedDisposed,0);
geometry.dispose();material.dispose();console.log('route layer: 50 rebuilds, owned resources released, borrowed vehicle preserved, floor filter and data identity pass');
