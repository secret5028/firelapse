// Pure read adapters: no DOM, fetch, engine imports, defaults, or simulation.
const copy=x=>structuredClone(x);
const issue=(errors,code,ref,msg)=>errors.push({code,ref:String(ref),msg});
const unique=(rows,id,errors)=>{
 const count=new Map();for(const r of rows)count.set(r[id],(count.get(r[id])||0)+1);
 for(const [key,n] of count)if(typeof key!=='string'||n>1)issue(errors,'DUPLICATE_ID',key,'Missing or repeated ID excluded; no first-row preference');
 return rows.filter(r=>typeof r[id]==='string'&&count.get(r[id])===1);
};
const polygons=polys=>(polys||[]).map(p=>({polygon_m:copy(p.o),holes_m:copy(p.h||[])}));
const shapes=polys=>({polygon_m:copy(polys[0].polygon_m),holes_m:copy(polys[0].holes_m),polygons_m:polys});
const hashString=async text=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text))),b=>b.toString(16).padStart(2,'0')).join('');
function stable(x){if(Array.isArray(x))return x.map(stable);if(x&&typeof x==='object')return Object.fromEntries(Object.keys(x).sort().map(k=>[k,stable(x[k])]));return x;}
export const snapshotHash=x=>hashString(JSON.stringify(stable(x)));

export function adaptBuilding({scenario,playback,sourceHash}){
 const errors=[],floors=new Map(),byRoom=new Map();
 for(const r of unique(scenario.rooms,'id',errors)){
  const p=polygons(r.cad_polys);if(!p.length){issue(errors,'MISSING_GEOMETRY',r.id,'No actual CAD polygons; room excluded');continue;}
  const floor=r.cad_floor,z=r.z_m??r.origin_m?.[2],h=r.height_m??r.size_m?.[2];
  if(typeof floor!=='string'||!Number.isFinite(z)||!Number.isFinite(h)){issue(errors,'MISSING_GEOMETRY',r.id,'Floor/height missing');continue;}
  if(!floors.has(floor))floors.set(floor,{floor_id:floor,name:floor,elevation_m:z,height_m:h,rooms:[],openings:[]});
  const f=floors.get(floor);f.elevation_m=Math.min(f.elevation_m,z);f.height_m=Math.max(f.height_m,z+h-f.elevation_m);
  const core={elev:'elevator',stair:'stair',shaft:'shaft',lobby:'lobby',corridor:'corridor'}[r.core_kind]??null;
  const row={room_id:r.id,name:r.name||(r.cad_names||[]).join(' / ')||r.id,
   usage:typeof r.approved_fuel_class==='string'?r.approved_fuel_class:r.fuel_default?.usage??null,
   core_kind:core,...shapes(p),floor_z_m:z,ceiling_z_m:z+h,cells:[]};
  byRoom.set(r.id,row);f.rooms.push(row);
 }
 for(const c of unique(playback.rooms,'key',errors)){
  const room=byRoom.get(c.original_room??c.key),p=polygons(c.cad_polys);
  if(!room){issue(errors,'UNMAPPED_CELL',c.key,'Explicit original_room does not exist; cell excluded');continue;}
  if(!p.length){issue(errors,'MISSING_GEOMETRY',c.key,'No cell polygons');continue;}
  room.cells.push({cell_id:c.key,...shapes(p),legacy_display:{z_m:c.z_m,height_m:c.height_m,
   single_zone:!!playback.solvers[c.solver_id]?.single_zone}});
 }
 for(const v of unique(scenario.openings,'id',errors)){
  if(![v.a,v.b].every(id=>id==='OUTSIDE'||byRoom.has(id))){issue(errors,'UNMAPPED_OPENING',v.id,'Opening endpoint missing; opening excluded');continue;}
  const f=floors.get(v.cad_floor),center=v.cad_geometry?.center_m;
  if(!f||!center){issue(errors,'MISSING_GEOMETRY',v.id,'CAD center or floor missing; no approximate center inserted');continue;}
  let kind=v.type==='FLOOR'||v.type==='CEILING'?'vertical':v.kind?.includes('door')?'door':v.kind?.includes('window')?'window':v.kind==='open_passage'?'passage':null;
  if(!kind){issue(errors,'UNKNOWN_OPENING_KIND',v.id,String(v.kind));continue;}
  const user=v.door_class_confidence==='user';
  const cls=v.door_class==='fire'?(v.door_class_confidence==='inferred'?'fire_estimated':'fire_confirmed'):
   v.door_class==='ordinary'?'ordinary':v.door_class==='fixed'?'fixed':null;
  f.openings.push({opening_id:v.id,kind,door_class:cls,door_class_basis:v.door_class_reason??null,
   user_override:user,a:v.a,b:v.b,center_m:copy(center),width_m:v.width_m,sill_m:v.bottom_m,soffit_m:v.top_m,
   exterior:v.a==='OUTSIDE'||v.b==='OUTSIDE',initial_fraction:v.schedule?.[0]?.[1],source_kind:v.kind??v.type});
 }
 return {schema:'pyrocast.building/1',building_id:sourceHash,source_hash:sourceHash,
  units:{length:'m',origin:[0,0,0],up:'z'},floors:[...floors.values()],errors,scope:'provided CAD geometry; result coverage is defined by saved solver cells',
  geometry_notes:['polygon_m/holes_m are the first component; polygons_m preserves ALL components and holes',
   'Coordinates copied from saved CAD geometry; no nearest-room repair or geometry recomputation']};
}

export const SERIES_MAP={T_upper_C:'Tu',T_lower_C:'Tl',interface_m:'h',O2_upper_volfrac:'Ou',O2_lower_volfrac:'Ol',
 fuel_upper_massfrac:'Fu',HRR_actual_kW:'Qsolid_kW',HRR_doorjet_kW:'Qvent_kW',HRR_upperburn_kW:'Qbulk_kW'};
const unknown=n=>Array(n).fill(null);
function series(values,n,ref){if(values==null)return unknown(n);if(!Array.isArray(values)||values.length!==n)throw Error(`Series length mismatch: ${ref}`);
 for(const x of values)if(x!==null&&(typeof x!=='number'||!Number.isFinite(x)))throw Error(`Invalid numeric series: ${ref}`);return copy(values);}
const at=(values,i)=>values?.[i]??null;
const axis=x=>({temperature:'T',fuel:'F',oxygen:'O'}[x]??null);
function criterion(rec,i){const sc=rec?.scores;return {met:at(sc?.all_met??rec?.all_met,i),degree:at(sc?.degree,i),
 r_T:at(sc?.factors?.temperature,i),r_F:at(sc?.factors?.fuel,i),r_O:at(sc?.factors?.oxygen,i),
 bottleneck:axis(at(sc?.weakest,i)),dominant:axis(at(sc?.strongest,i)),status:rec?.status??null};}
// Whole saved interval, one maximum and its earliest sample time per phenomenon.
// Unknown-only series remain null. No integration or scalar room averages.
export function indexHistoryExtrema(indices,times=[]){
 const maximum={},peak_time_s={};
 for(const [id,types] of Object.entries(indices)){maximum[id]={};peak_time_s[id]={};
  for(const [type,values] of Object.entries(types)){let peak=null,time=null;
   values.forEach((value,i)=>{if(Number.isFinite(value)&&(peak===null||value>peak)){peak=value;time=times[i]??null;}});
   maximum[id][type]=peak;peak_time_s[id][type]=time;
  }
 }
 return {maximum,peak_time_s};
}
export function anyKnown(values){return values.includes(true)?true:values.includes(null)?null:false;}
function frame(s,i,cid){const f={smoke_stage:null,smoke_factors:[],source_cells:[cid],aggregation:'single'};
 for(const key of ['FO','FGI','backdraft','untenable'])f[key]=criterion(s.conditions?.[key],i);
 const r=s.conditions?.FGI?.rollover;f.FGI.rollover={active:at(r?.active,i),ignition:at(r?.ignition,i),excluded_origin:r?.excluded_origin??null};
 return f;
}

export async function adaptResult({playback:p,sourceResult=null,scenario,summary=null,building,resultId,sourceRefs={}}){
 const native=p.engine_kind==='cfast_native'&&p.native_mapping==='wando-c11-p1-v1';
 if(p.engine_kind!=='pyrocast_lite'&&!native)throw Error('Unsupported playback engine; native adapter requires its own verified mapping');
 const errors=[],notes=[],n=p.time_s.length;
 if(!n||p.time_s.some((t,i)=>!Number.isFinite(t)||(i>0&&t<=p.time_s[i-1])))throw Error('Time axis must be finite and strictly increasing');
 if(sourceResult&&JSON.stringify(sourceResult.t)!==JSON.stringify(p.time_s))throw Error('Sidecar result time axis mismatch');
 if(p.building_sha256!==building.source_hash||scenario.cad?.building_sha256!==building.source_hash)throw Error('Building hash mismatch');
 if(sourceResult&&p.provenance?.manifest_sha256!==sourceResult.r8_manifest_sha256)throw Error('Sidecar manifest mismatch');
 const cellRoom=new Map(),roomCells=new Map();
 for(const f of building.floors)for(const r of f.rooms){roomCells.set(r.room_id,r.cells.map(c=>c.cell_id));for(const c of r.cells)cellRoom.set(c.cell_id,r.room_id);}
 const meta=new Map(unique(p.rooms,'key',errors).map(c=>[c.key,c]));
 const originalResult=new Map((sourceResult?.rooms||[]).map(r=>[r.id,r]));
 const cells={},cellConditions={},indexByCell={},fgiRollover={},legacyColor={},boundaryByCell={},boundaries=new Set();
 const oxygenProxy=sourceResult?.physical_parameters?.oxygen_inventory_mode===true;
 for(const [cid,rid] of cellRoom){
  const c=meta.get(cid),s=c&&p.solvers[c.solver_id];
  if(!s){issue(errors,'UNMAPPED_CELL',cid,'Mapped cell has no solver values');continue;}
  const row={room_id:rid,aggregation:'single',aggregation_status:'direct',source_cells:[cid],O2_basis:oxygenProxy?'room_proxy':sourceResult?'layered':null,field_sources:{},legacy_optical:{ODu:series(s.ODu,n,cid+'.ODu'),ODl:series(s.ODl,n,cid+'.ODl')}};
  for(const [field,key] of Object.entries(SERIES_MAP)){row[field]=series(s[key],n,cid+'.'+key);row.field_sources[field]=s[key]==null?'unavailable':`playback.solvers.${c.solver_id}.${key}`;}
  const supply=originalResult.get(c.solver_id)?.supply_HRR_kW;
  row.HRR_supply_kW=series(supply,n,cid+'.supply');row.field_sources.HRR_supply_kW=supply?'saved result.rooms.supply_HRR_kW':'unavailable';cells[cid]=row;
  cellConditions[cid]=Object.fromEntries(p.time_s.map((_,i)=>[String(i),frame(s,i,cid)]));
  // Presentation scale only: retain saved degree and unknowns, without re-scoring factors.
  indexByCell[cid]=Object.fromEntries(['FO','FGI','backdraft'].map(key=>[key,p.time_s.map((_,i)=>{
   const degree=cellConditions[cid][i][key].degree;return Number.isFinite(degree)?degree*100:null;
  })]));
  const state=s.conditions?.FGI?.rollover,ignition=state?.ignition??unknown(n),eligible=indexByCell[cid].FGI.filter((value,j)=>ignition[j]===true&&Number.isFinite(value));
  fgiRollover[cid]={ignition:copy(ignition),excluded_origin:state?.excluded_origin??null,
   eligible_peak_index:state?.excluded_origin===false&&eligible.length?Math.max(...eligible):null,status:state?.status??'not_evaluated'};
  legacyColor[cid]={color:Array(n).fill(''),LOC_vol_fraction:null};
  // Read-only archive compatibility: old results keep their saved boundary geometry.
  const boundary=s.boundary??s.display_v8?.boundary;boundaryByCell[cid]=copy(boundary??unknown(n));if(boundary?.some(v=>v===true))boundaries.add(rid);
 }
 for(const c of p.rooms)if(!cellRoom.has(c.key))issue(errors,'UNMAPPED_CELL',c.key,'Result cell excluded because it has no building mapping');
 const rooms={},conditions={};
 for(const [rid,ids] of roomCells){const present=ids.filter(id=>cells[id]);if(!present.length)continue;
  if(present.length===1){rooms[rid]=copy(cells[present[0]]);conditions[rid]=copy(cellConditions[present[0]]);continue;}
  // No legacy continuous room-average policy exists. Do not invent one.
  rooms[rid]={...Object.fromEntries([...Object.keys(SERIES_MAP),'HRR_supply_kW'].map(k=>[k,unknown(n)])),
   room_id:rid,aggregation:'none',aggregation_status:'not_defined',source_cells:present,O2_basis:oxygenProxy?'room_proxy':sourceResult?'layered':null,
   field_sources:{},legacy_optical:{ODu:unknown(n),ODl:unknown(n)}};
  conditions[rid]={};for(let i=0;i<n;i++){
   const frames=present.map(id=>cellConditions[id][i]),stages=frames.map(f=>f.smoke_stage);
   const f={smoke_stage:stages.some(v=>v===null)?null:Math.max(...stages),smoke_factors:[...new Set(frames.flatMap(f=>f.smoke_factors))],source_cells:present,aggregation:'cell_any'};
   for(const key of ['FO','FGI','backdraft','untenable']){
    f[key]={...criterion(null,i),met:anyKnown(frames.map(f=>f[key].met)),status:'cell_union_no_scalar_score'};
   }
   f.FGI.rollover={active:anyKnown(frames.map(f=>f.FGI.rollover.active)),ignition:anyKnown(frames.map(f=>f.FGI.rollover.ignition)),excluded_origin:anyKnown(frames.map(f=>f.FGI.rollover.excluded_origin))};conditions[rid][i]=f;
  }
 }
 notes.push('Multi-cell room continuous series and scalar scores have no legacy aggregate: null, not a newly invented average/max. Cell series remain exact.');
 notes.push('conditions and indices use stored shared-condition values; removed display gates are empty schema compatibility fields.');
 const events=[];
 for(const e of p.events||[]){const rid=cellRoom.get(e.room),parent=cellRoom.get(e.parent)??null;
  if(!rid){issue(errors,'UNMAPPED_EVENT',e.room,'Event cell not mapped');continue;}
  for(const [key,kind] of [['condition_time_s','rule_trigger'],['supply_start_s','supply_start']])if(Number.isFinite(e[key]))events.push({t_s:e[key],kind,room_id:rid,cell_id:e.room,parent_room_id:parent,basis:e.trigger_basis??'saved_event'});
 }
 for(const f of p.fires||[])if(f.kind==='initial'&&cellRoom.has(f.cad_key))events.push({t_s:f.time_s,kind:'supply_start',room_id:cellRoom.get(f.cad_key),cell_id:f.cad_key,parent_room_id:null,basis:'saved initial fire schedule; not measured ignition'});
 const settings={scenario:copy(scenario),rule_settings:copy(sourceResult?.rule_settings??null),physical_parameters:copy(sourceResult?.physical_parameters??null)};
 const openingRisk=summary?.opening_risk;
 const risk=openingRisk?.status==='evaluated'?Object.fromEntries(Object.entries(openingRisk.rooms).map(([rid,intervals])=>[rid,intervals.map(v=>[v.start_sample_s,v.end_sample_s])])):null;
 const gaps=p.time_s.slice(1).map((t,i)=>t-p.time_s[i]),history=indexHistoryExtrema(indexByCell,p.time_s);
 return {schema:'pyrocast.result/1',result_id:resultId,engine:{kind:native?'cfast':'lite',version:native?'7.7.7':sourceResult?.lite_revision??sourceResult?.revision??null,sha256:p.provenance?.engine_sha256??null},
  scenario:{building_id:building.building_id,floor_id:new Set(p.rooms.map(r=>r.cad_floor)).size===1?p.rooms[0].cad_floor:null,
   origin_room_id:cellRoom.get(p.fire_key)??null,settings_snapshot:settings,settings_hash:await snapshotHash(settings),seed:sourceResult?.seed??null,
   opening_state:Object.fromEntries(scenario.openings.map(v=>[v.id,v.schedule?.[0]?.[1]??null]))},
  status:p.complete===true&&p.simulation_output_complete!==false?'complete':p.time_s.length?'partial':'failed',t_end_s:p.time_s.at(-1),dt_out_s:gaps.length&&gaps.every(g=>g===gaps[0])?gaps[0]:null,
  limits_text:copy(p.limits||[]),time_s:copy(p.time_s),rooms,cells,conditions,cell_conditions:cellConditions,index_by_cell:indexByCell,fgi_rollover_by_cell:fgiRollover,index_history_max:history.maximum,index_history_peak_s:history.peak_time_s,events,
  opening_risk:risk,opening_risk_status:openingRisk?.status??'not_provided',boundary_rooms:[...boundaries],boundary_by_cell:boundaryByCell,
  fallback_sensors:null,legacy_color:legacyColor,errors,notes,source_refs:copy(sourceRefs),aggregation_policy:'single: exact cell; multi: no scalar aggregate; conditions: cell OR with unknown preserved'};
}

export function adaptScreening({score,comparison=null,selection={},buildingId,floorId,mc=null}){
 return {schema:'pyrocast.screening/1',building_id:buildingId,floor_id:floorId,top_n:score.top_n,source_revision:score.revision??null,
  stage1:score.ranked.map(r=>({room_id:r.room,rank:r.rank1,score:r.score,factors:Object.fromEntries(Object.keys(r.raw).map(k=>[k,{raw:r.raw[k]??null,norm:r.normalized?.[k]??null}]))})),
  stage2:(comparison?.rows||[]).map(r=>({room_id:r.room,rank:r.rank2??null,worse_state:({open_except_confirmed:'open',closed:'closed'})[r.worst_state]??null,
   burning_rooms:r.burning_room_count??null,smoke_risk_rooms:r.smoke_risk_room_count??null,smoke_caution_rooms:r.smoke_caution_room_count??null,
   first_FO_s:r.first_FO_s??null,result_ids:{open:null,closed:null},tied_states:copy(r.tied_states||[]),status:r.complete?'complete':'partial'})),
  mc:mc?copy(mc):{origin_room_id:selection.mc_room??null,seed:null,samples:[],aggregate:null},errors:[]};
}

// A validator must be supplied by the boundary caller (Ajv in stage-1 tooling).
// No schema bypass/default success path; browser/store connection is stage 2.
export function validateContract(payload,validate){
 if(typeof validate!=='function')throw Error('A compiled JSON Schema validator is required');
 if(!validate(payload))throw Error(JSON.stringify(validate.errors));
 return payload;
}
