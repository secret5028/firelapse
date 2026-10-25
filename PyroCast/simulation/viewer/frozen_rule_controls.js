// Frozen r8 controls and review panel. Does not install/replace playback data.
export async function attachFrozenRules(panel,getOptions){
 const response=await fetch('/cfbt/r8/schema');if(!response.ok)throw Error('r8 schema unavailable');const schema=await response.json();
 const host=document.createElement('details');host.id='cfbtFrozenRules';
 host.innerHTML='<summary>동결 정밀 모드 r8 · 사용자 전이 설정/시험 결과</summary><p>순정 CFAST · 기존 전이 구조 동결. 아래 계산은 검토용이며 현재 3D 재생 결과를 자동으로 교체하지 않습니다.</p><p>화점·층·계산 시간·문·창 설정은 위의 계산 조건을 사용합니다. r8은 가스 추가연소를 끄고 아래 전이 규칙으로 1회 계산합니다. 기존 반복 계산·가스 반응 설정은 r8에 적용되지 않습니다.</p>';
 const form=document.createElement('form'),row=document.createElement('div');row.className='row';form.append(row);
 const addSelect=(label,entries)=>{const wrap=document.createElement('label');wrap.append(label+' ');const select=document.createElement('select');for(const [key,text] of entries){const option=document.createElement('option');option.value=key;option.textContent=text;select.append(option);}wrap.append(select);row.append(wrap);return select;};
 const preset=addSelect('프리셋',Object.entries(schema.preset_labels));preset.value='standard';preset.id='r8Preset';
 const supply=addSelect('공급',[['item_peak','입력 peak · 기본'],['room_involvement','전실 공급 · 선택']]);supply.id='r8Supply';
 const grid=document.createElement('div');grid.id='r8SettingsGrid';grid.style.cssText='display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:8px';form.append(grid);
 const fields={},overrides={};
 for(const [key,field] of Object.entries(schema.fields)){
  const label=document.createElement('label');label.append(`${field.label} (${field.minimum}~${field.maximum} ${field.unit}) `);
  const input=document.createElement('input');input.type='number';input.min=field.minimum;input.max=field.maximum;input.step='any';input.required=true;input.id='r8_'+key;
  input.addEventListener('input',()=>{overrides[key]=input.value===''?null:Number(input.value);});fields[key]=input;label.append(input);grid.append(label);
 }
 const fill=()=>{const defaults=Object.fromEntries(Object.entries(schema.fields).map(([k,v])=>[k,v.default]));Object.assign(defaults,schema.supply_defaults[supply.value],schema.presets[preset.value],overrides);for(const [key,input] of Object.entries(fields)){input.value=defaults[key];input.disabled=key==='coverage_default'&&supply.value!=='room_involvement';}};
 preset.addEventListener('change',()=>{for(const key of Object.keys(schema.presets.standard))delete overrides[key];fill();});supply.addEventListener('change',fill);fill();
 const comparison=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.id='r8Compare';comparison.append(check,' 공격 프리셋 1회와 병렬 비교 (기본은 1회 실행)');form.append(comparison);
 const note=document.createElement('p');note.textContent=schema.assumption;form.append(note);
 const submit=document.createElement('button');submit.type='submit';submit.id='r8Run';submit.textContent='r8 검토 계산';form.append(submit);
 const error=document.createElement('p');error.setAttribute('role','alert');form.append(error);host.append(form);
 const applied=document.createElement('div');applied.id='r8AppliedSettings';host.append(applied);(panel.querySelector('#cfbtBody')||panel).append(host);
 let poll=null,submitting=false;
 const paragraph=(parent,text)=>{const p=document.createElement('p');p.textContent=text;parent.append(p);};
 const render=value=>{
  applied.replaceChildren();const batch=value.batch_state,result=value.comparison;
  submit.disabled=submitting||batch?.state==='running';
  paragraph(applied,'r8 검토 결과 · 현재 재생 중인 3D 결과와 별도 · 운영 결과 교체는 사용자 승인 후');
  if(batch)paragraph(applied,`상태: ${batch.state}${batch.error?' · '+batch.error:''}`);
  for(const [name,progress] of Object.entries(value.progress||{}))paragraph(applied,`${name==='selected'?'사용자 설정':'공격 비교'}: ${progress.status} · ${progress.last_native_time_s??0}/${progress.requested_horizon_s??'—'}초 · 경과 ${Math.round(progress.wall_seconds??0)}초`);
  if(!result){paragraph(applied,'아직 완료된 r8 비교 보고서가 없습니다. 입력란은 다음 실행의 설정입니다.');return;}
  const bounds=result.ranges?.burning_room_count_range;
  paragraph(applied,result.complete?`전체 완료 · 실제 발열 관측 실 수 ${bounds?.[0]}~${bounds?.[1]}실 (최초 실 포함) · 발생확률이 아닙니다.`:'미완료 사례 포함 · 완전한 연소 실 수 범위로 해석하지 않습니다.');
  for(const [name,settings] of Object.entries(result.settings)){
   const section=document.createElement('details');section.open=true;const title=document.createElement('summary');title.textContent=`${name==='selected'?'사용자 설정':'공격 비교'} · ${settings.preset_label} · ${settings.room_supply}`;section.append(title);
   const table=document.createElement('table'),head=table.insertRow();for(const text of ['실제 설정','값','기본값 여부 / 출처']){const th=document.createElement('th');th.textContent=text;head.append(th);}
   for(const item of Object.values(settings.parameters)){const tr=table.insertRow();for(const text of [item.label,`${item.value} ${item.unit}${item.applicable?'':' (이 공급 방식에서 미적용)'}`,`${item.is_default?'기본값':'변경값'} / ${{default:'기본',preset:'프리셋',user_override:'직접 입력',comparison_shared:'사용자 설정과 공유'}[item.source]}`])tr.insertCell().textContent=text;}
   section.append(table);const report=result.cases[name],observed=report.complete?report:result.partial_cases?.[name];paragraph(section,`${report.complete?'완료':'미완료'} · 계산 ${report.native_wall_seconds?.toFixed(1)??'미확인'}초 · 실제 발열 관측: ${observed?.actual_burning_original_rooms?.join(', ')||'분석 결과 없음'}`);
   if(!report.complete&&observed)paragraph(section,`부분 결과: ${observed.horizon_s}초까지 분석. 1시간 완료 결과 및 완전한 비교 범위에 포함하지 않습니다.`);
   if(observed?.fallback_sensors?.length)paragraph(section,'판정 불확실 · 대체 센서: '+observed.fallback_sensors.join(', '));
   const transitions=document.createElement('details'),heading=document.createElement('summary');heading.textContent='실별 경로 · 조건 시각 · 실제 발열';transitions.append(heading);
   for(const item of observed?.rows||[])paragraph(transitions,`${item.parent?.room||'최초'} → ${item.cell}: 조건 ${item.trigger_estimate_s??'미충족'}초 · 실제 첫 발열 ${item.first_actual_positive_HRR_s??'미관측'}초`);
   section.append(transitions);applied.append(section);
  }
  const ranges=document.createElement('details'),heading=document.createElement('summary');heading.textContent='실별 첫 발열 관측 시각 범위';ranges.append(heading);
  for(const [room,times] of Object.entries(result.ranges?.room_first_actual_HRR||{}))paragraph(ranges,`${room}: ${times.observed_range_s.join('~')}초${times.not_observed_in.length?' · 미관측 사례: '+times.not_observed_in.join(', '):''}${times.unevaluated_in?.length?' · 미완료/미평가: '+times.unevaluated_in.join(', '):''} (관측된 사례 범위)`);
  applied.append(ranges);paragraph(applied,'정적 최단경로의 부모 하나만 사용합니다. 다른 경로의 열이나 활성 화원이 있어도 해당 경로를 대신 적용하지 않습니다.');
 };
 const refresh=async()=>{const res=await fetch('/cfbt/r8/review');if(!res.ok)throw Error('r8 결과를 읽을 수 없습니다.');const value=await res.json();render(value);if(value.batch_state?.state==='running'){if(!poll)poll=setInterval(()=>refresh().catch(e=>error.textContent=e.message),3000);}else if(poll){clearInterval(poll);poll=null;}};
 form.addEventListener('submit',async event=>{event.preventDefault();error.textContent='';if(!form.reportValidity())return;submitting=true;submit.disabled=true;
  try{const settings={preset:preset.value,room_supply:supply.value,...overrides};for(const [key,value] of Object.entries(overrides)){const f=schema.fields[key];if(typeof value!=='number'||!Number.isFinite(value)||value<f.minimum||value>f.maximum)throw Error(`${f.label}: 허용 범위 ${f.minimum}~${f.maximum} ${f.unit}`);}
   const res=await fetch('/cfbt/r8/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({options:getOptions(),settings,compare_aggressive:check.checked})});const value=await res.json();if(!res.ok)throw Error(value.error||'r8 실행 요청 실패');if(!poll)poll=setInterval(()=>refresh().catch(e=>error.textContent=e.message),3000);
  }catch(e){error.textContent=e.message;}finally{submitting=false;submit.disabled=false;await refresh().catch(e=>error.textContent=e.message);}
 });
 await refresh();
}
