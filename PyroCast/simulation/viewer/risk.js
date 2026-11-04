// Discrete screening flags; colours do not encode event probabilities.
export function riskFor(state,time,times,phenomenon='all'){
 let lo=0,hi=times.length;while(lo+1<hi){const m=(lo+hi)>>1;if(times[m]<=time)lo=m;else hi=m;}
 const tags=state.tags||{},on=k=>k==='UPPER_GAS'&&!tags.UPPER_GAS ? (state.Qbulk_kW?.[lo]||0)>1e-9 : !!tags[k]?.[lo]; // Existing 1e-6 W diagnostic gate, expressed in kW.
 if(phenomenon!=='all'){
  const condition=state.conditions?.[phenomenon],met=condition?.all_met?.[lo]??null;
  const palettes={fo:'#ffdb58',upper_gas:'#ff9c39',backdraft:'#ee4055',fgi:'#b16cff',rapid:'#ff786b'};
  return {color:met===true?palettes[phenomenon]:null,labels:[met===null?'조건 미평가':met?'선택 조건 충족':'선택 조건 미충족'],keys:[],met};
 }
 // New payloads share the same condition truth in individual and combined views.
 if(state.conditions&&Object.values(state.conditions).some(c=>Array.isArray(c?.all_met))){
  const defs=[['backdraft','#ee4055','고온연기 축적·산소부족(백드래프트) 조건'],['fgi','#b16cff','FGI 선별 조건'],
   ['upper_gas','#ff9c39','상층 혼합가스 반응 조건'],['fo','#ffdb58','FO 조건'],['rapid','#ff786b','급격한 온도 상승 조건']];
  const active=defs.filter(([k])=>state.conditions[k]?.all_met?.[lo]===true);
  return {color:active[0]?.[1]||null,labels:active.map(d=>d[2]),keys:active.map(d=>d[0]),
   met:active.length?true:defs.some(([k])=>state.conditions[k]?.all_met?.[lo]==null)?null:false,basis:'condition_table_v2'};
 }
 const definitions=[
  ['BD_POTENTIAL','#ee4055','고온연기 축적·산소부족(백드래프트) 가능 조건'],['BD','#ee4055','고온연기 축적·산소부족(백드래프트) 관련 이력 조건 · 원인 미확정'],
  ['IGNITION_ASSUMED','#bd72ff','가정 점화·가스 추가연소'],
  ['FGI_POTENTIAL','#b16cff','FGI 가능 조건'],
  ['UPPER_GAS','#ff9c39','상층 가스 추가연소 · 롤오버 표현'],['FO_transition','#ffdb58','FO 공급 전환'],
  ['FO_thermal','#ffdb58','FO 열적 기준'],['RAPID','#ff786b','급격한 온도 상승 조건']];
 const active=definitions.filter(d=>on(d[0]));
 return {color:active[0]?.[1]||null,labels:active.map(d=>d[2]),keys:active.map(d=>d[0])};
}
