import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {adaptBuilding,adaptResult} from '../web/adapters/read.js';
import {resultCoverage,resultNumber,selectedScores} from '../web/panels/results.js';
import {SelectionLayer} from '../web/layers/selection.js';
import {createStore} from '../web/state/store.js';
const polys=[{o:[[0,0],[4,0],[4,4],[0,4]],h:[]}];
const scenario={cad:{building_sha256:'test'},openings:[],rooms:[
 {id:'CAD_5F_R16',name:'객실',cad_floor:'5F',cad_polys:polys,z_m:15,height_m:2.4},
 {id:'CAD_2F_R1',name:'홀',cad_floor:'2F',cad_polys:polys,z_m:3,height_m:3}]};
const playback={engine_kind:'pyrocast_lite',building_sha256:'test',complete:true,time_s:[0,10],fire_key:'CAD_5F_R16',rooms:[
 {key:'CAD_5F_R16',solver_id:'r',original_room:'CAD_5F_R16',cad_floor:'5F',cad_polys:polys,z_m:15,height_m:2.4}],
 solvers:{r:{Tu:[20,100],conditions:{FO:{scores:{degree:[0,1.17]}},FGI:{scores:{degree:[0,0]}}}}}};
const building=adaptBuilding({scenario,playback,sourceHash:'test'});
const result=await adaptResult({playback,scenario,building,resultId:'saved'});
assert.equal(result.scenario.floor_id,'5F');
const room=building.floors.find(f=>f.floor_id==='2F').rooms[0];
assert.equal(room.cells.length,0);assert.equal(result.rooms[room.room_id],undefined);
assert.equal(resultCoverage(building,result,room).status,'미평가');
assert.equal(resultCoverage(building,result,room).label,'간략 결과 5F · 화점 5F R16');
assert.equal(resultCoverage(building,result,building.floors[0].rooms[0]).status,'계산됨');
assert.equal(resultNumber(selectedScores(result,'CAD_5F_R16',0)[1].value),'0');
assert.equal(resultNumber(selectedScores(result,'CAD_2F_R1',0)[1].value),'—');
assert.equal(resultNumber(selectedScores(result,'CAD_5F_R16',0)[2].value),'—');
const T=await import(pathToFileURL(process.argv[2]).href),layer=new SelectionLayer(T),store=createStore({validators:{result:v=>v.schema==='pyrocast.result/1'&&!v.errors.length}});
const seq=store.dispatch('result/load');store.dispatch('result/receive',{seq,result});
assert.equal(resultCoverage(building,store.get('result'),room).status,'미평가');
assert.equal(resultCoverage(building,store.get('result'),building.floors[0].rooms[0]).status,'계산됨');
layer.mount(new T.Scene(),store);layer.setData({building,resultMeta:result,floor:{floor_id:'2F'},selection:{room_id:room.room_id,cell_id:null}});
assert.equal(layer.getPickPlanes().length,1);assert.equal(layer.getPickPlanes()[0].userData.roomId,room.room_id);
assert.equal(layer.getPickPlanes()[0].userData.liteRoom,null);
assert.equal(layer.views.filter(v=>v.group.visible&&v.ribbon.visible).length,1);
assert.equal(room.cells.length,0,'Picking must not create result cells');
layer.dispose();assert.equal(layer.resources.size,0);
console.log('PASS: CAD-only picking, saved scope, missing vs genuine zero, disposal');
