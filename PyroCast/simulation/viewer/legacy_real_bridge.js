import {createLegacyRealistic,displayConfig} from './legacy_real_view.js';
import {riskFor} from './risk.js';

import {gasVisualState} from './gas_visual.js';

// Read the same source JSON used by screening; never duplicate its class values.
export async function readFlameFuelTable(fetcher=fetch){
 const response=await fetcher('/cfbt/lite/fire-load-table',{cache:'no-store'});
 if(!response.ok)throw Error('연료 용도표 읽기 실패: HTTP '+response.status);
 const table=await response.json();
 if(!table.classes||typeof table.classes!=='object')throw Error('연료 용도표 classes 누락');
 return table;
}
const flameFuelTable=typeof window==='undefined'?null:await readFlameFuelTable();
export function flameFuelForRoom(room,table=flameFuelTable){
 const classes=table?.classes??{},key=room.approved_fuel_class??room.fuel_default?.usage;
 const label=(room.display_name??'').replace(/ \(승인 용도\)$/u,'');
 const entry=classes[key]??Object.values(classes).find(v=>v.label===label);
 const value=entry?.rhrf,valid=Number.isFinite(value)&&value>0;
 return {hrrpua_kW_m2:valid?value:500,hrrpua_basis:valid?'fire_load_table.json: '+entry.label:'fallback 500 kW/m²'};
}

// Lite has no soot/extinction transport. This is a visual density for the
// original billowing gray shader, never a replacement simulation quantity.
export function displaySmokeDensity(od,legacyTexture=false){
 return legacyTexture&&od>0?Math.max(1,od):od;
}

// Only the display contract changes. All times, states, HRRs and flame heights are from this result.
export function createRealView(viewer,data,parent){
 const {THREE,C,groups}=viewer,layer=new THREE.Group();layer.name='복원된 실감 보기';parent.add(layer);
 const floorIndex=new Map(viewer.B.floors.map((f,i)=>[f.name,i])),roots=new Map();
 for(const room of data.rooms)if(!roots.has(room.cad_floor)){const root=new THREE.Group();root.position.z=viewer.B.floors[floorIndex.get(room.cad_floor)].z;layer.add(root);roots.set(room.cad_floor,root);}
 const rows=data.rooms.map(room=>{const s=data.solvers[room.solver_id];return {
  key:room.key,id:room.cad_room,floor:room.cad_floor,height:s.height_m,area:room.area_m2,
  c:room.cad_center_m,polys:room.cad_polys,solver:s,core_kind:s.single_zone?'shaft':null,
  series:data.time_s.map((t,i)=>[t,s.Tu[i],s.single_zone?s.Tu[i]:s.Tl[i],s.single_zone?0:s.h[i],s.ODu[i],s.single_zone?0:s.ODl[i]])};});
 const rowMap=new Map(rows.map(r=>[r.key,r]));
 const fires=data.fires.map(f=>{const r=rowMap.get(f.cad_key),v=f.visuals;if(!v)throw Error('실감 보기의 native 화원 자료가 없습니다.');return {
  visual_mode:f.visual_mode,...flameFuelForRoom(data.rooms.find(room=>room.key===f.cad_key)??{}),cell_area_m2:r.area,
  id:f.id,room_key:f.cad_key,floor:f.cad_floor,position:f.position_m.slice(0,2),base_height:v.base_height_m,
  ignition_time:f.time_s,hrr:f.Q_kW,flame_height:v.flame_height_m,area:v.area_m2[0],area_series:v.area_m2,
  fuel_units:data.fuel_units?.length?[]:(f.fuel_units||[]),plume_inputs:{area:v.area_m2[0],base:v.base_height_m,chi:v.radiative_fraction,
    height:r.height,corner_factor:1,hall:false},source:f};});
 const jetDisplay=doorJetDefinitions(viewer.B,data);
 for(const jet of jetDisplay.jets)Object.assign(jet,flameFuelForRoom(data.rooms.find(r=>r.key===jet.room_key)??{}));
 const renderer=createLegacyRealistic({THREE,C,groups},{rows,roots,geometry:r=>r.polys,
   fire:rowMap.get(data.fire_key),centre:r=>r.c,floorIndex,fires,jets:jetDisplay.jets,unmappedJets:jetDisplay.unmapped});
 if(data.engine_kind==='pyrocast_lite'){
  const note=document.querySelector('#cfPlumeLegend small');
  if(note)note.textContent='보라·청록은 고온 가스 구분색이며 불꽃이 아닙니다. 간략 엔진 결과에 CFAST 계열 상관식을 적용한 보조 표시로, 순정 CFAST 출력·실제 속도장과 동일하지 않습니다. 흐르는 무늬는 표시 효과입니다.';
 }
 let active=false;
 // A separate display-input clock also survives 20 s standalone exports.
 const inputs=data.display_inputs??{},inputTimes=inputs.time_s??data.time_s;
 const inputAt=(array,t)=>{if(!array?.length)return null;let lo=0,hi=inputTimes.length-1;while(lo<hi){const m=Math.ceil((lo+hi)/2);if(inputTimes[m]<=t)lo=m;else hi=m-1;}const a=array[lo],b=array[Math.min(lo+1,array.length-1)];if(!Number.isFinite(a))return null;const dt=(inputTimes[lo+1]??inputTimes[lo])-inputTimes[lo];return dt>0&&Number.isFinite(b)?a+(b-a)*Math.max(0,Math.min(1,(t-inputTimes[lo])/dt)):a;};
 const solverFor=key=>rowMap.get(key)?.solver;
 function combustionInputs(sample,time){
  for(const f of fires){const s=solverFor(f.room_key),saved=inputs.fires?.[f.id]??{},upper=(f.base_height??0)>sample(s.h),o=upper?s.Ou:s.Ol;
   f.combustion={supply_kW:inputAt(saved.Q_fuel_kW,time),oxygen_fraction:o?.length?sample(o):null,oxygen_basis:upper?'source upper layer':'source lower layer',Tu:sample(s.Tu),basis:saved.basis??'supply unavailable'};
  }
  for(const jet of jetDisplay.jets){const s=solverFor(jet.room_key),donor=data.rooms.find(r=>r.solver_id===jet.from),f=fires.find(f=>f.room_key===donor?.key),hoc=inputs.fires?.[f?.id]?.heat_of_combustion_kJ_kg;
   jet.combustion={supply_kW:jet.fuel_in_kg_s?.length&&hoc>0?sample(jet.fuel_in_kg_s)*hoc:null,oxygen_fraction:s.Ol?.length?sample(s.Ol):null,oxygen_basis:'receiving lower layer',Tu:sample(s.Tu),basis:'receiving jet: incoming fuel rate × saved heat of combustion when available; never donor-source supply'};
  }
  const byQ=(a,b)=>sample(b.hrr)-sample(a.hrr)||a.id.localeCompare(b.id),active=fires.filter(f=>sample(f.hrr)>0).sort(byQ);
  for(const row of rows){const local=active.filter(f=>f.room_key===row.key),incoming=jetDisplay.jets.filter(j=>j.room_key===row.key&&j.q>0).sort((a,b)=>b.q-a.q||a.id.localeCompare(b.id));
   const donor=data.rooms.find(r=>r.solver_id===incoming[0]?.from),source=local[0]??active.find(f=>f.room_key===donor?.key)??active[0],saved=inputs.fires?.[source?.id],valid=Number.isFinite(saved?.soot_yield);
   row.soot={value:valid?saved.soot_yield:displayConfig.soot_default,source:source?.id??null,basis:!valid?'configured default':local.length?'dominant local HRR':donor?'receiving-jet donor':'building dominant HRR proxy (no species source tracing)'};
  }
 }
 return {
  update({enabled,time,sample,floor,selectedSmokeKeys=[],smokeEnabled,smokeOpacity=1,smokeGain=1,flameGain=1,flameDisplay='compact',smokeMode='current',flameStyle='current',riskMode=false,phenomenon='all',customRiskBoundaries=false,legacySmokeTexture=false,plumesEnabled=true,temperatureSmoke=false,noiseAmp=1,noiseScale=1,rampMode=0}){
   active=enabled;layer.visible=enabled;
   const legend=document.getElementById('cfPlumeLegend');if(legend)legend.hidden=!enabled;
   if(!enabled)return;
   for(const [name,root] of roots)root.visible=floor==='all'||name===floor;
   const cached=new Map(rows.map(r=>[r.key,[time,sample(r.solver.Tu),sample(r.solver.Tl),
      r.solver.single_zone?0:sample(r.solver.h),displaySmokeDensity(sample(r.solver.ODu),legacySmokeTexture),r.solver.single_zone?0:displaySmokeDensity(sample(r.solver.ODl),legacySmokeTexture)]]));
   for(const fire of fires){fire.area=Math.max(.001,sample(fire.area_series));fire.plume_inputs.area=fire.area;}
   for(const jet of jetDisplay.jets)jet.q=Math.max(0,sample(jet.HRR_kW));
   combustionInputs(sample,time);
   renderer.setState({enabled:true,realView:true,time,step:data.time_s[1]-data.time_s[0],cached,
      selectedSmokeKeys,smokeEnabled,smokeOpacity,smokeGain,flameGain,flameDisplay,smokeMode,flameStyle,plumesEnabled,temperatureSmoke,noiseAmp,noiseScale,rampMode,darkSmoke:legacySmokeTexture,flamesEnabled:true,gasFlamesEnabled:false,q:0,h:0,
      gasStates:new Map(rows.map(r=>[r.key,gasVisualState({time,times:data.time_s,
         power:r.solver.Qbulk_kW,assumption:data.ignition_assumption,room:data.rooms.find(x=>x.key===r.key).solver_id})])),
      positiveHrrOnly:data.engine_kind==='pyrocast_lite',
      riskColors:customRiskBoundaries?new Map():riskMode?new Map(rows.map(r=>[r.key,riskFor(r.solver,time,data.time_s,phenomenon).color])):null});
  },
  animate(ms){if(active)renderer.animate(matchMedia('(prefers-reduced-motion: reduce)').matches?0:ms);},
  stats(){return active?renderer.stats():null;},
  detach(){document.getElementById('cfPlumeLegend')?.remove();layer.removeFromParent();}
 };
}

// Geometry association only. Never invent or duplicate receiving-room heat.
export function doorJetDefinitions(building,data){
 const bySolver=new Map(data.rooms.map(r=>[r.solver_id,r])),out=[],unmapped=[];
 for(const d of data.door_jet?.directions||[]){
  if(!d.HRR_kW?.some(q=>q>0))continue;
  const r=bySolver.get(d.to),source=bySolver.get(d.from);if(!r||!source){unmapped.push(d.vent);continue;}
  const floor=building.floors.find(f=>f.name===r.cad_floor);
  const opening=floor?.openings?.find(o=>o.id===d.vent||`CAD_${floor.name}_${o.id}`===d.vent);
  let g=d.visual_opening;
  if(!g&&opening){
   let span=opening.leaves?.length?[opening.leaves[0].hinge,opening.leaves[0].closed]:null;
   if(!span){let length=0;for(const ring of opening.polys||[])for(let i=0;i<ring.length;i++){const a=ring[i],b=ring[(i+1)%ring.length],n=Math.hypot(b[0]-a[0],b[1]-a[1]);if(n>length){length=n;span=[a,b];}}}
   if(span){const [a,b]=span,w=Math.hypot(b[0]-a[0],b[1]-a[1]),bottom=opening.sill_m??0,top=opening.door_h??floor.door_h??2.1;
    if(w>0)g={center_m:[(a[0]+b[0])/2,(a[1]+b[1])/2,(bottom+top)/2],span_direction:[(b[0]-a[0])/w,(b[1]-a[1])/w],width_m:w,bottom_m:bottom,top_m:top};
   }
  }
  if(!g){unmapped.push(d.vent);continue;}
  const [tx,ty]=g.span_direction,normal=[-ty,tx],delta=[r.cad_center_m[0]-g.center_m[0],r.cad_center_m[1]-g.center_m[1]];
  if(normal[0]*delta[0]+normal[1]*delta[1]<0){normal[0]*=-1;normal[1]*=-1;}
  out.push({...d,id:`jet:${d.vent}:${d.from}:${d.to}`,room_key:r.key,floor:r.cad_floor,normal,geometry:g});
 }
 return {jets:out,unmapped};
}
