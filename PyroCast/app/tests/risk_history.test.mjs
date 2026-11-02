import fs from 'node:fs';
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {RiskLayer} from '../web/layers/risk.js';
import {createStore} from '../web/state/store.js';
import {adaptBuilding,adaptResult,indexHistoryExtrema} from '../web/adapters/read.js';
const vendor='cad-project/work/cad-web/local-resources/cad-assets/three.module.js';
const THREE=await import(pathToFileURL(process.env.PYROCAST_THREE||[vendor,'simulation/results/github-publish-20261026/PyroCast/'+vendor].find(p=>fs.existsSync(p))).href);
const read=p=>JSON.parse(fs.readFileSync(p,'utf8').replace(/^\uFEFF/,''));
const dir='simulation/results/lite_v8_mc_R2_10_20261026/S09',playback=read(dir+'/playback.json'),scenario=read(dir+'/sample.json').scenario;
const building=adaptBuilding({scenario,playback,sourceHash:playback.building_sha256});
const result=await adaptResult({playback,scenario,building,resultId:'S09'}),store=createStore(),layer=new RiskLayer(THREE),scene=new THREE.Scene();

assert.equal(store.get('risk').history,true);
assert.deepEqual(indexHistoryExtrema({c:{FO:[null,40,120,null,70,150,150],FGI:[null,null]}},[0,10,20,30,40,50,60]),{maximum:{c:{FO:150,FGI:null}},peak_time_s:{c:{FO:50,FGI:null}}});
const types=['FO','FGI','backdraft','rollover'];let time=3600;
layer.mount(scene,store);
const update=()=>{layer.setData({building,resultMeta:result,series:{cells:result.cells},t_s:time,floor:{floor_id:'3F'},risk:store.get('risk'),layers:store.get('layers'),selection:store.get('selection')});layer.tick();};
update();const expected={};
for(const type of types){expected[type]=[...new Set(playback.rooms.filter(c=>playback.solvers[c.solver_id].conditions?.[type]?.scores?.degree?.some(v=>Number.isFinite(v)&&v*100>=100)).map(c=>c.original_room??c.key))].sort();
 assert.deepEqual(layer.activeRooms.filter(r=>r.types.includes(type)).map(r=>r.room_id).sort(),expected[type]);}
const actual=layer.diagnostics(),builds=layer.buildCount;
store.dispatch('risk/history',{enabled:false});update();const off=layer.diagnostics();assert.ok(layer.rooms.every(r=>r.historyMeshes.every(m=>!m.visible)));
store.dispatch('risk/history',{enabled:true});time=0;update();assert.deepEqual(layer.diagnostics().counts,actual.counts,'full-period maxima must be visible at time zero');
assert.equal(layer.rooms.filter(r=>r.cautionMesh.visible).length,5,'full-period caution must be dotted at time zero');
for(const row of layer.rooms.filter(r=>r.cautionMesh.visible)){assert.equal(row.cautionMesh.material.color.getHexString(),'9ca3af');assert.ok(row.cautionMesh.geometry.attributes.position.count>0);}
const r2=layer.rooms.find(r=>r.id==='CAD_3F_R2');assert.equal(r2.historyMeshes[0].visible,true);assert.equal(r2.historyMeshes[2].visible,true);assert.ok(r2.meshes.every(m=>!m.visible));
time=1420;update();assert.equal(r2.meshes[0].visible,true);assert.equal(r2.historyMeshes[0].visible,true);assert.equal(r2.historyMeshes[2].visible,true);
time=3600;update();assert.deepEqual(layer.diagnostics().counts,actual.counts);assert.equal(layer.buildCount,builds);
// Force one independent cell history: no current FO anywhere, a prior FO in one cell.
const i=result.time_s.length-1;for(const ind of Object.values(result.index_by_cell))for(const type of types)ind[type].fill(null);
const room=layer.rooms.find(r=>r.members.length>1),a=room.members[0],b=room.members[1];result.index_by_cell[a.id].FO[1]=130;
result.index_by_cell[a.id].FO[i]=50;result.index_history_max=indexHistoryExtrema(result.index_by_cell).maximum;update();
assert.deepEqual(layer.activeRooms[0].historyOnly,['FO']);assert.equal(room.historyMeshes[0].visible,true);assert.equal(room.meshes[0].visible,false);
assert.ok(room.historyMeshes[0].geometry.attributes.position.count>0);assert.equal(room.historyMeshes[0].renderOrder,35);assert.equal(room.historyMeshes[0].material.depthTest,false);
result.index_by_cell[b.id].FO[i]=101;result.index_history_max=indexHistoryExtrema(result.index_by_cell).maximum;update();assert.equal(room.meshes[0].visible,true);assert.equal(room.historyMeshes[0].visible,true,'current solid covers the retained history ribbon');
store.dispatch('risk/set',{type:'FO',visible:false});update();assert.equal(layer.counts.FO,0);
store.dispatch('risk/set',{type:'FO',visible:true});store.dispatch('risk/threshold',{ribbon:140});update();assert.equal(layer.counts.FO,0);
assert.equal(layer.buildCount,builds);layer.dispose();assert.equal(layer.resources.size,0);assert.equal(store.diagnostics().subscriptions,0);
const report={passed:true,expected,history_on:actual,history_off:off,checks:'scalar full-period maxima/earliest tie/null, time0 FO+BD dashed,1420 FO solid overlay, room cell OR, threshold/toggle, no rebuild, dispose0',simulation_runs:0};
fs.writeFileSync('simulation/results/ui_C1a_20261102/unit-verification.json',JSON.stringify(report,null,2));console.log(JSON.stringify({passed:true,expected,counts:actual.counts,current:off.counts}));
