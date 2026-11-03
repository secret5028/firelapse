import {createLegacyRealistic} from './legacy_real_view.js';
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
  ...flameFuelForRoom(data.rooms.find(room=>room.key===f.cad_key)??{}),cell_area_m2:r.area,
  id:f.id,room_key:f.cad_key,floor:f.cad_floor,position:f.position_m.slice(0,2),base_height:v.base_height_m,
  ignition_time:f.time_s,hrr:f.Q_kW,flame_height:v.flame_height_m,area:v.area_m2[0],area_series:v.area_m2,
  fuel_units:data.fuel_units?.length?[]:(f.fuel_units||[]),plume_inputs:{area:v.area_m2[0],base:v.base_height_m,chi:v.radiative_fraction,
    height:r.height,corner_factor:1,hall:false},source:f};});
 const renderer=createLegacyRealistic({THREE,C,groups},{rows,roots,geometry:r=>r.polys,
   fire:rowMap.get(data.fire_key),centre:r=>r.c,floorIndex,fires});
 if(data.engine_kind==='pyrocast_lite'){
  const note=document.querySelector('#cfPlumeLegend small');
  if(note)note.textContent='보라·청록은 고온 가스 구분색이며 불꽃이 아닙니다. 간략 엔진 결과에 CFAST 계열 상관식을 적용한 보조 표시로, 순정 CFAST 출력·실제 속도장과 동일하지 않습니다. 흐르는 무늬는 표시 효과입니다.';
 }
 let active=false;
 return {
  update({enabled,time,sample,floor,smokeEnabled,smokeOpacity=1,smokeGain=1,flameGain=1,flameDisplay='compact',riskMode=false,phenomenon='all',customRiskBoundaries=false,legacySmokeTexture=false,plumesEnabled=true,temperatureSmoke=false,noiseAmp=1,noiseScale=1,rampMode=0}){
   active=enabled;layer.visible=enabled;
   const legend=document.getElementById('cfPlumeLegend');if(legend)legend.hidden=!enabled;
   if(!enabled)return;
   for(const [name,root] of roots)root.visible=floor==='all'||name===floor;
   const cached=new Map(rows.map(r=>[r.key,[time,sample(r.solver.Tu),sample(r.solver.Tl),
      r.solver.single_zone?0:sample(r.solver.h),displaySmokeDensity(sample(r.solver.ODu),legacySmokeTexture),r.solver.single_zone?0:displaySmokeDensity(sample(r.solver.ODl),legacySmokeTexture)]]));
   for(const fire of fires){fire.area=Math.max(.001,sample(fire.area_series));fire.plume_inputs.area=fire.area;}
   renderer.setState({enabled:true,realView:true,time,step:data.time_s[1]-data.time_s[0],cached,
      smokeEnabled,smokeOpacity,smokeGain,flameGain,flameDisplay,plumesEnabled,temperatureSmoke,noiseAmp,noiseScale,rampMode,darkSmoke:legacySmokeTexture,flamesEnabled:true,gasFlamesEnabled:false,q:0,h:0,
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
