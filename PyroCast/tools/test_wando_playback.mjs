import {readFileSync,mkdirSync,writeFileSync} from 'node:fs';
import assert from 'node:assert/strict';
import {adaptBuilding,adaptResult} from '../app/web/adapters/read.js';
import {readRouteGraph,findRoute} from '../app/web/route/graph.js';
import * as T from '../simulation/results/github-publish-20261026/PyroCast/cad-project/work/cad-web/local-resources/cad-assets/three.module.js';
import {OpeningsLayer} from '../app/web/layers/openings.js';
import {createStore} from '../app/web/state/store.js';
const read=p=>JSON.parse(readFileSync(p,'utf8'));
const b=read('data/wando-coldstore/operating-building.json'),p=read('data/wando-coldstore/P1-playback.json');
const scenario={rooms:p.rooms.map(r=>({id:r.key,cad_floor:r.cad_floor,cad_polys:r.cad_polys,z_m:r.z_m,height_m:r.height_m})),openings:[],cad:{building_sha256:p.building_sha256}};
const building=adaptBuilding({scenario,playback:p,sourceHash:p.building_sha256});
const result=await adaptResult({scenario,playback:p,building,resultId:'wando-P1'});
assert.deepEqual(result.errors,[]);assert.equal(result.engine.kind,'cfast');assert.equal(result.t_end_s,3595);assert.equal(result.dt_out_s,5);assert.equal(result.status,'partial');
const src=read('simulation/results/wando_C11_P1_20261102/timeseries.json');
for(const [native,id] of [['ROOM','CAD_1F_R5'],['CAVITY','CAD_1F_CAVITY']]){
 assert.deepEqual(result.cells[id].T_upper_C,src[native].T_upper_C);
 assert.deepEqual(result.cells[id].HRR_actual_kW,src[native].source_HRR_kW);
 for(const [old,key] of [['FGI','FGI'],['BD','backdraft'],['rollover','rollover']])assert.deepEqual(result.index_by_cell[id][key],src[native][old]);
 const rec=p.solvers[native].conditions.FO, old=rec.legacy_combustion_support_scores;
 const expected=src[native].source_HRR_kW.map((q,i)=>Math.min(old.factors.temperature[i],old.factors.oxygen[i],(q+src[native].door_jet_kW[i])/rec.score_basis.Q_required_kW[i])*100);
 assert.deepEqual(result.index_by_cell[id].FO,expected);
 assert.deepEqual(rec.scores.factors.temperature,old.factors.temperature);
 assert.deepEqual(rec.scores.factors.oxygen,old.factors.oxygen);
 assert.deepEqual(p.solvers[native].conditions.FO.legacy_combustion_support_scores.degree.map(v=>v*100),src[native].FO);
 assert.equal(rec.scores.revision,'fo_own_plus_received_door_jet_v1');
}
assert.ok(Math.abs(result.index_history_max.CAD_1F_R5.FO-42.243227012333335)<1e-8);
assert.equal(result.index_history_peak_s.CAD_1F_R5.FO,1325);
assert.equal(result.cell_conditions.CAD_1F_R5[p.time_s.indexOf(2100)].FO.bottleneck,'F');
const graph=readRouteGraph(b),route=findRoute(graph,p.route_target_room_id);
assert.equal(route.entry,'CAD_1F_ENTRY_R5');assert.deepEqual(route.vehicle,[49.375,-5,0]);
assert.deepEqual(route.segments.at(-1).b,[46.75,17.95,0]);assert.equal(route.hoses,2);assert.equal(route.stairs,0);
const schedule=b.floors[0].openings.find(o=>o.id==='CUT').display_schedule;
const fractions=[1315,1320,1795,1800,2100].map(t=>schedule.filter(([s])=>s<=t).at(-1)[1]);
assert.deepEqual(fractions,[0,.5,.5,1,1]);
const store=createStore(),scene=new T.Scene(),camera=new T.PerspectiveCamera(),group=new T.Group();
const asset={source_hash:p.building_sha256,floors:[{id:'1F',floor:b.floors[0],group}]};
const layer=new OpeningsLayer(T,{camera,geometryFor:()=>asset});layer.mount(scene,store);
const geometry=[];for(const t of [1315,1320,1795,1800,2100]){layer.setData({building,resultMeta:result,t_s:t,floor:{floor_id:'1F'}});layer.tick();const cut=layer.group.getObjectByName('scheduled-opening-CUT');geometry.push({t,visible:cut.visible,fraction:cut.userData.displayFraction,width_m:cut.geometry.parameters.width*cut.scale.x});}
assert.equal(geometry[0].visible,false);assert.equal(geometry[1].width_m,1);assert.equal(geometry[3].width_m,2);assert.equal(layer.buildCount,1);layer.dispose();assert.equal(store.diagnostics().subscriptions,0);
const evidence={samples:p.time_s.length,end_s:result.t_end_s,adapter_errors:result.errors,
 source_temperature_hrr_other_indices_exact:true,FO_three_factor_received_jet_exact:true,legacy_FO_preserved:true,route,cut:{times:[1315,1320,1795,1800,2100],fractions,geometry,builds:1,subscriptions_after_dispose:0},
 conditions:[1320,2100,3595].map(t=>({time_s:t,room:'R5',...Object.fromEntries(Object.entries(result.index_by_cell.CAD_1F_R5).map(([k,a])=>[k,a[p.time_s.indexOf(t)]]))})),
 simulation_runs:0};
mkdirSync('simulation/results/fo_received_jet_20261103',{recursive:true});writeFileSync('simulation/results/fo_received_jet_20261103/verification.json',JSON.stringify(evidence,null,2));console.log(JSON.stringify(evidence,null,2));
