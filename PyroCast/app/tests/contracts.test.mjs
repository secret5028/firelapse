// Saved-data validation only. Never imports or launches a simulation engine.
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import {gzipSync} from 'node:zlib';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {adaptBuilding,adaptResult,adaptScreening,SERIES_MAP,validateContract,anyKnown} from '../web/adapters/read.js';
const require=createRequire(import.meta.url);
let Ajv;try{Ajv=require('ajv/dist/2020').default;}catch(e){if(!process.env.PYROCAST_AJV)throw e;Ajv=require(process.env.PYROCAST_AJV).default;}
const root=fileURLToPath(new URL('../../',import.meta.url));
const out=path.resolve(root,process.env.PYROCAST_CONTRACTS_OUT||'simulation/results/ui_refactor_stage1_20261026');fs.mkdirSync(out,{recursive:true});
const hash=b=>createHash('sha256').update(b).digest('hex');
const hashes={};
function read(rel){const buf=fs.readFileSync(path.join(root,rel));hashes[rel]=hash(buf);return JSON.parse(buf.toString('utf8').replace(/^\uFEFF/,''));}
const ajv=new Ajv({allErrors:true,strict:true,strictNumbers:true});
const validators=Object.fromEntries(['building','result','screening'].map(k=>[k,ajv.compile(read(`app/contracts/${k}-1.schema.json`))]));
function save(name,value){fs.writeFileSync(path.join(out,name+'.json.gz'),gzipSync(JSON.stringify(value)));}
const report={created:new Date().toISOString(),simulation_runs:0,cases:[],checks:[],sources:hashes};
let sharedBuildingId=null;
for(const id of ['S06','S09','stage4']){
 const dir=id==='stage4'?'simulation/results/lite_v8_stage4_R2_20261026':`simulation/results/lite_v8_mc_R2_10_20261026/${id}`;
 const p=read(dir+'/playback.json'),raw=read(dir+'/result.json');
 const input=read(dir+(id==='stage4'?'/input.json':'/sample.json'));
 const scenario=id==='stage4'?input:input.scenario;
 const summary=id==='stage4'?null:read(dir+'/summary.json');
 const before=hash(JSON.stringify([p,raw,scenario]));
 const building=adaptBuilding({scenario,playback:p,sourceHash:p.building_sha256});
 if(sharedBuildingId!==null)assert.equal(building.building_id,sharedBuildingId);
 sharedBuildingId=building.building_id;
 validateContract(building,validators.building);assert.deepEqual(building.errors,[]);
 const args={playback:p,sourceResult:raw,scenario,summary,building,resultId:id,sourceRefs:{playback:dir+'/playback.json',result:dir+'/result.json'}};
 const result=await adaptResult(args);validateContract(result,validators.result);assert.deepEqual(result.errors,[]);
 assert.equal(hash(JSON.stringify([p,raw,scenario])),before,'adapter must not mutate sources');
 let values=0,conditions=0,multipolygons=0;
 for(const c of p.rooms){const r=result.cells[c.key],s=p.solvers[c.solver_id];
  for(const [key,old] of Object.entries(SERIES_MAP)){assert.deepEqual(r[key],s[old]??Array(p.time_s.length).fill(null));values+=r[key].length;}
  assert.deepEqual(r.HRR_supply_kW,raw.rooms.find(x=>x.id===c.solver_id)?.supply_HRR_kW??Array(p.time_s.length).fill(null));
  values+=r.HRR_supply_kW.length;
  const geom=building.floors.flatMap(f=>f.rooms).flatMap(r=>r.cells).find(x=>x.cell_id===c.key);
  assert.deepEqual(geom.polygons_m,c.cad_polys.map(x=>({polygon_m:x.o,holes_m:x.h||[]})));
  assert.deepEqual(geom.legacy_display,{z_m:c.z_m,height_m:c.height_m,single_zone:!!s.single_zone});
  if(geom.polygons_m.length>1)multipolygons++;
  for(const key of ['FO','FGI','backdraft','rollover','untenable'])for(let i=0;i<p.time_s.length;i++){
   const src=s.conditions?.[key],dest=result.cell_conditions[c.key][i][key];
   assert.equal(dest.met,(src?.scores?.all_met??src?.all_met)?.[i]??null);assert.equal(dest.degree,src?.scores?.degree?.[i]??null);conditions+=2;
   if(key!=='untenable')assert.equal(result.index_by_cell[c.key][key][i],Number.isFinite(dest.degree)?dest.degree*100:null);
   for(const [newKey,oldKey] of [['r_T','temperature'],['r_F','fuel'],['r_O','oxygen']]){assert.equal(dest[newKey],src?.scores?.factors?.[oldKey]?.[i]??null);conditions++;}
  }
 }
 assert.equal(result.scenario.seed,raw.seed??null);
 assert.deepEqual(result.time_s,p.time_s);assert.deepEqual(result.scenario.settings_snapshot.scenario,scenario);
 const multi=Object.values(result.rooms).filter(r=>r.source_cells.length>1);
 for(const r of Object.values(result.rooms)){
  if(r.source_cells.length===1){assert.deepEqual(r,result.cells[r.source_cells[0]]);continue;}
  assert.equal(r.aggregation,'none');
  for(const key of [...Object.keys(SERIES_MAP),'HRR_supply_kW'])assert(r[key].every(v=>v===null));
  for(let i=0;i<p.time_s.length;i++)for(const k of ['FO','FGI','backdraft','rollover','untenable'])
   assert.equal(result.conditions[r.room_id][i][k].met,anyKnown(r.source_cells.map(cid=>result.cell_conditions[cid][i][k].met)));
 }
 // Exercise failure paths without another engine run or copying large input blobs.
 await assert.rejects(adaptResult({...args,playback:{...p,engine_kind:'unknown'}}),/Unsupported/);
 await assert.rejects(adaptResult({...args,sourceResult:{...raw,t:[0,1]}}),/time axis mismatch/);
 await assert.rejects(adaptResult({...args,sourceResult:{...raw,r8_manifest_sha256:'wrong'}}),/manifest mismatch/);
 const bad=adaptBuilding({scenario:{...scenario,rooms:[...scenario.rooms,scenario.rooms[0]]},playback:p,sourceHash:p.building_sha256});
 assert(bad.errors.some(e=>e.code==='DUPLICATE_ID'));assert(!bad.floors.flatMap(f=>f.rooms).some(r=>r.room_id===scenario.rooms[0].id));
 const cid=p.rooms[0].key,sid=p.rooms[0].solver_id;
 const missing=await adaptResult({...args,sourceResult:null,playback:{...p,solvers:{...p.solvers,[sid]:{...p.solvers[sid],Tu:null}}}});
 assert(missing.cells[cid].T_upper_C.every(x=>x===null));assert.equal(missing.cells[cid].O2_basis,null);assert(missing.cells[cid].HRR_supply_kW.every(x=>x===null));
 const proxy=await adaptResult({...args,sourceResult:{...raw,physical_parameters:{...raw.physical_parameters,oxygen_inventory_mode:true}}});
 assert.equal(proxy.cells[cid].O2_basis,'room_proxy');
 save(id+'-building',building);save(id+'-result',result);
 report.cases.push({id,status:result.status,rooms:Object.keys(result.rooms).length,cells:Object.keys(result.cells).length,openings:building.floors.reduce((s,f)=>s+f.openings.length,0),samples:result.time_s.length,exact_series_values:values,exact_condition_values:conditions,series_max_difference:0,multi_component_cells:multipolygons,unaggregated_rooms:multi.map(r=>r.room_id),errors:result.errors});
 console.log(JSON.stringify(report.cases.at(-1)));
}
const score=read('simulation/results/lite_v8_approved_n8_20261025/score.json');
const comparison=read('simulation/results/lite_v8_approved_n8_20261025/comparison.json');
const selection=read('simulation/config/lite-screening-selection.json');
const screening=adaptScreening({score,comparison,selection,buildingId:sharedBuildingId,floorId:'3F'});
validateContract(screening,validators.screening);
assert.deepEqual(screening.stage1.map(x=>[x.room_id,x.rank,x.score]),score.ranked.map(x=>[x.room,x.rank1,x.score]));
assert.deepEqual(screening.stage2.map(x=>[x.room_id,x.rank]),comparison.rows.map(x=>[x.room,x.rank2??null]));
assert.throws(()=>validateContract(screening),/validator/);
assert.throws(()=>validateContract({...screening,surprise:1},validators.screening));
assert.equal(anyKnown([false,null]),null);assert.equal(anyKnown([true,null]),true);assert.equal(anyKnown([false,false]),false);
save('screening',screening);
for(const [rel,expected] of Object.entries(hashes))assert.equal(hash(fs.readFileSync(path.join(root,rel))),expected,`Saved input modified: ${rel}`);
report.checks=['all 3 schemas valid','3 building/result snapshots valid','exact cell series and saved condition flags','geometry components/holes preserved','no source mutation','unknown/missing values stay null','room proxy basis explicit','duplicate IDs excluded with error','unknown engines and mismatched sidecars rejected','saved screening ranks preserved','extra schema fields rejected','source file hashes unchanged'];
fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify(report,null,2));
console.log('PASS '+report.checks.length+' check groups; no simulation executed');
