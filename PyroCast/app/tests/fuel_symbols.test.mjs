import assert from 'node:assert/strict';
import {fuelPositions,symbolSize,FuelQuantityLayer} from '../web/layers/fuel_quantity.js';
import {contains} from '../web/route/graph.js';
import {resolveFuel} from '../web/state/fuel_settings.js';
import {createStore} from '../web/state/store.js';
import {pathToFileURL} from 'node:url';
const poly=[{o:[[0,0],[8,0],[8,3],[3,3],[3,8],[0,8]],h:[[[.5,.5],[1.5,.5],[1.5,1.5],[.5,1.5]]]}];
for(const u of fuelPositions(poly)){const size=symbolSize(1500,u.clearance,3);for(const dx of [-size/2,size/2])for(const dy of [-size/2,size/2])assert(contains([u.p[0]+dx,u.p[1]+dy],poly));}
const T=await import(pathToFileURL(process.cwd()+'/cad-project/work/cad-web/local-resources/cad-assets/three.module.js'));
const data={revision:'1',classes:{hotel_room:{mean:500,rhrf:250},office:{mean:600,rhrf:300}},quantity_settings:{rooms:{CAD_5F_A:{usage_class:'office',multiplier:1}}},rooms:[{id:'CAD_5F_A',floor:'5F',editable:true,baseline_class:'hotel_room',baseline_load:500}],ai_pending:[]};
assert.equal(resolveFuel(data,{floors:{'5F':{usage_class:'hotel_room',multiplier:3}}},data.rooms[0]).load,600);
assert.equal(createStore().get('realView').fuelMarkers,true);
const layer=new FuelQuantityLayer(T,{floors:[{name:'5F',z:12,h:3,rooms:[{id:'A',polys:poly}]}]}),store=createStore();layer.mount(new T.Scene(),store);
const frame={building:{floors:[]},fuelSettings:{data,draft:{}},floor:{floor_id:'5F'},realView:{fuelMarkers:true},layers:{selection:true},selection:{room_id:'CAD_5F_A'}};layer.setData(frame);
assert.equal(layer.getPickPlanes().length,1);assert.equal(layer.getPickPlanes()[0].layers.mask,2**31);assert.equal(layer.picks[0].line.visible,true);
const ray=new T.Raycaster(new T.Vector3(2,2,20),new T.Vector3(0,0,-1));ray.layers.set(31);layer.group.updateMatrixWorld(true);assert.equal(ray.intersectObjects(layer.getPickPlanes(),false)[0].object.userData.roomId,'CAD_5F_A');
layer.setData({...frame,fuelSettings:{data:{...data,ai_pending:['CAD_5F_A'],quantity_settings:{}},draft:{}}});assert.equal(layer.floors[0].mesh.visible,true);assert(layer.floors[0].mesh.instanceMatrix.array[0]>0);
layer.setData({...frame,floor:{floor_id:'6F'}});assert.equal(layer.getPickPlanes().length,0);layer.dispose();assert.equal(layer.resources.size,0);
console.log('Fuel symbols: default ON, pending baseline visible, room override preserved, geometry/picking/dispose PASS');
