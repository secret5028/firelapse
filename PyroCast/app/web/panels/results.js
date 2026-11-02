import {infoTip} from './explanations.js';
export const resultTypes=[['FO','FO','#ef4444'],['FGI','FGI','#a855f7'],['backdraft','백드래프트','#facc15'],['rollover','롤오버','#f97316']];
const finite=Number.isFinite;
const number=(v,d=0)=>finite(v)?v.toFixed(d):'미평가';
const stamp=t=>`${Math.floor(t/60).toString().padStart(2,'0')}:${Math.floor(t%60).toString().padStart(2,'0')}`;
export function selectedScores(result,cell,index){return resultTypes.map(([type,name,color])=>{
 const c=result.cell_conditions[cell]?.[index]?.[type],axis=c?.bottleneck;
 return {type,name,color,value:result.index_by_cell[cell]?.[type]?.[index]??null,bottleneck:({T:'온도',F:'연료',O:'산소'})[axis]??null,factor:finite(c?.['r_'+axis])?c['r_'+axis]*100:null};
});}
export function worstIndexEntries(result,cells){return resultTypes.map(([type,name])=>{
 let value=null,time=null,source=null;
 for(const id of cells){const v=result.index_history_max?.[id]?.[type],t=result.index_history_peak_s?.[id]?.[type];
  if(finite(v)&&(value===null||v>value||(v===value&&finite(t)&&(!finite(time)||t<time)))){value=v;time=t;source=id;}
 }
 return {type,name,value,time,source};
});}
// Presentation aggregation only: read saved degrees, deduplicate cells by original room.
// No time integration, factor recomputation or room-average series.
export function summarizeMCPlayback(playback){
 if(!playback.complete)throw Error('미완료 표본');
 return Object.fromEntries(resultTypes.map(([type])=>{
  const rooms=new Set();let peak=null,unknown=false;
  for(const room of playback.rooms){const values=playback.solvers[room.solver_id]?.conditions?.[type]?.scores?.degree;
   if(!Array.isArray(values)||values.length!==playback.time_s.length){unknown=true;continue;}
   for(const value of values){if(!finite(value)){unknown=true;continue;}const score=value*100;peak=peak===null?score:Math.max(peak,score);if(score>=100)rooms.add(room.original_room||room.key);}
  }
  return [type,{rooms:rooms.size,peak,unknown}];
 }));
}
export function createResultsPanel({panel,store}){
 const $=id=>document.getElementById(id),root=document.createElement('div'),moves=[];root.id='resultContent';$('shellPane-result').append(root);panel.hidden=true;
 const move=(node,parent)=>{const mark=document.createComment('result restore');node.before(mark);moves.push(()=>mark.replaceWith(node));parent.append(node);};
 root.innerHTML='<h3>저장 결과</h3><div class="resultCard" id="resultCase"><label for="liteCase">사례</label><div id="resultCaseControls"></div><div id="resultMetadata"></div><div id="resultReuse" role="status"></div><button id="resultReplay" type="button" title="검증된 캐시는 반환하고, 증명 불가한 옛 사례는 과거 결과로 엽니다. 계산은 시작하지 않습니다.">다시 실행</button><div class="resultTools" id="resultTools"></div></div><h3>선택 실 위험 지수 <span class="resultInfo" tabindex="0" title="저장된 조건 지수 × 100. 100은 세 조건의 기준이며 발생 확률이 아닙니다. 표시 임계선은 표시 탭 설정을 따릅니다.">ⓘ</span></h3><div class="resultCard"><label for="liteRoom">실·셀</label><div id="resultRoomControl"></div><div id="resultRoomTitle"></div><details id="resultCells"><summary>셀 목록 · 방 평균 없음</summary><div id="resultCellList"></div></details><div id="resultScores"></div><div id="resultBottleneck"></div><details><summary>계산값</summary><div id="resultQuantities"></div></details></div><h3>MC 집계 <span class="resultInfo" tabindex="0" title="표본 비율은 발생 확률이 아닙니다. ≥100은 고정 집계 기준이며 표시 임계값 변경과 별개입니다. 최대 실은 전체 시간 중 한 번 이상 충족한 원래 방 수의 표본 간 최대입니다.">ⓘ</span></h3><div class="resultCard"><div id="resultMCStatus" role="status"></div><button id="resultMCLoad">저장 표본 집계 읽기</button><button id="resultMCApplyWorst" disabled title="연소 실 ↓ → 주의 이상 실 ↓ → 최초 FO ↑. 현재 재생 결과는 유지하며 이후 실행 입력에 적용합니다.">최악 표본 적용</button><div id="resultMCWorst"></div><table><thead><tr><th>현상</th><th>≥100 표본</th><th>최대 실</th><th>지수 최대</th></tr></thead><tbody id="resultMCRows"></tbody></table><div id="resultMCBasis"></div></div><details id="resultLimits"><summary>가정과 한계</summary><ul></ul></details>';
 move($('liteCase'),$('resultCaseControls'));move($('liteRefresh'),$('resultCaseControls'));$('liteRefresh').textContent='목록 새로고침';move($('liteRoom'),$('resultRoomControl'));
 $('resultTools').remove();
 const worst=document.createElement('div');worst.id='resultWorstTime';worst.style.cssText='font-size:11px;white-space:nowrap;overflow-x:auto;margin:8px 0;color:#b8cbd8';$('resultRoomTitle').after(worst);
 const reviewDetails=document.createElement('details');reviewDetails.id='resultMenuReview';reviewDetails.innerHTML='<summary>전체 메뉴 검토</summary><div id="resultReviewMount"></div>';root.append(reviewDetails);
 const style=document.createElement('style');style.dataset.pyrocastResults='true';style.textContent=`
 #resultContent #pyroMenuReview{position:static;inset:auto;width:auto;height:auto;max-height:none;overflow:visible;padding:8px 0;border:0;box-shadow:none;z-index:auto;font-size:11px}#resultContent #pyroMenuReview header{display:none}#resultContent #pyroMenuReview .reviewSection{overflow:auto}
 #resultContent{padding:12px 16px;font-size:12px;color:#eaf3f8}#resultContent h3{font-size:12px;font-weight:500;color:#b8cbd8;margin:14px 0 8px}.resultCard{border:1px solid #496273;border-radius:7px;padding:10px;margin-bottom:12px;background:#163345}.resultCard>label{display:block;margin-bottom:5px;color:#b8cbd8}
 #resultContent select{max-width:100%;width:100%;box-sizing:border-box;background:#1d4158;color:#eef5fa;padding:6px;border:1px solid #6a8d9f;border-radius:4px}#resultContent button{background:#1d4158;color:#eef5fa;border:1px solid #577487;border-radius:4px;padding:5px 7px;cursor:pointer}#resultContent button:focus-visible{outline:2px solid #42e8ff}.resultTools{display:flex;flex-wrap:wrap;gap:5px;margin-top:8px}#resultCaseControls button{margin-top:6px}#resultMetadata,#resultBottleneck,#resultMCBasis{font-size:11px;color:#b8cbd8;margin-top:8px}#resultRoomTitle{font-weight:600;margin:10px 0;overflow-wrap:anywhere}#resultCells{margin-bottom:10px}#resultCellList{display:flex;gap:5px;flex-wrap:wrap;padding-top:6px}#resultCellList button[aria-pressed=true]{border-color:#42e8ff;color:#42e8ff}
 .resultScore{display:grid;grid-template-columns:62px 1fr 54px;gap:6px;align-items:center;margin:14px 0}.resultBar{height:7px;background:#304c5e;border-radius:4px;position:relative}.resultFill{display:block;height:100%;border-radius:4px}.resultMark{position:absolute;top:-5px;height:17px;border-left:1px dashed #ced9df}.resultMark.main{border-color:#fff;border-left-style:solid}.resultValue{text-align:right;font-variant-numeric:tabular-nums}.resultScale{font-size:10px;text-align:right;color:#b8cbd8}.resultInfo{cursor:help;color:#b8cbd8}#resultQuantities{display:grid;grid-template-columns:1fr auto;gap:5px;margin-top:8px}#resultContent details{margin-top:8px}#resultContent summary{cursor:pointer;color:#b8cbd8}#resultContent table{width:100%;border-collapse:collapse;font-size:11px;margin-top:8px}#resultContent th,#resultContent td{border-bottom:1px solid #304c5e;padding:7px 2px;text-align:right}#resultContent th:first-child,#resultContent td:first-child{text-align:left}#resultMCLoad{margin-top:8px}#resultLimits li{margin:6px 0;color:#b8cbd8}#resultMCStatus{font-size:11px}
 `;document.head.append(style);
 const append=(parent,tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;parent.append(e);return e;};
 let previous=null,roomKey=null;
 function update({building,result,series,index,selection}){
  const room=building.floors.flatMap(f=>f.rooms).find(r=>r.room_id===selection.room_id),cell=selection.cell_id??(room?.cells.length===1?room.cells[0].cell_id:null),values=series.cells[cell];
  $('resultMetadata').textContent=`${result.engine.kind==='lite'?'간략':'CFAST'} · ${result.status==='complete'?'완료':'미완료'} ${stamp(result.t_end_s)}`;
  $('resultRoomTitle').textContent=`${room?.room_id?.replace('CAD_','')||'실 선택'} · ${stamp(result.time_s[index])}`;
  const peaks=worstIndexEntries(result,cell?[cell]:(room?.cells||[]).map(c=>c.cell_id));
  worst.textContent='최악 시각 · '+peaks.map(p=>`${p.name} ${number(p.value)}${finite(p.time)?' @ '+stamp(p.time):''}`).join(' · ');
  worst.title=(cell?'선택 셀':'실 내 멤버 셀 최대')+' · 전 구간, 동률은 최초 시각. '+peaks.map(p=>`${p.name}: ${p.source??'미평가'}`).join(' / ');
  if(roomKey!==room?.room_id||previous!==result){$('resultCellList').replaceChildren();for(const c of room?.cells||[]){const b=append($('resultCellList'),'button',c.cell_id.split('_').at(-1));b.dataset.cell=c.cell_id;b.onclick=()=>store.dispatch('selection/set',{room_id:room.room_id,cell_id:c.cell_id,source:'list'});}roomKey=room?.room_id;}
  $('resultCells').hidden=!(room?.cells.length>1);$('resultCells').open=room?.cells.length>1;for(const b of $('resultCellList').children)b.setAttribute('aria-pressed',String(b.dataset.cell===cell));
  const scores=cell?selectedScores(result,cell,index):resultTypes.map(([type,name,color])=>({type,name,color,value:null})),threshold=store.get('risk').threshold,scale=Math.max(200,threshold.ribbon,threshold.caution,...scores.map(s=>s.value??0));
  $('resultScores').replaceChildren();
  for(const s of scores){const row=append($('resultScores'),'div',undefined,'resultScore');row.dataset.type=s.type;append(row,'span',s.name);const bar=append(row,'div',undefined,'resultBar');bar.setAttribute('role','meter');bar.setAttribute('aria-label',s.name+' 지수');bar.setAttribute('aria-valuemin','0');bar.setAttribute('aria-valuemax',String(scale));if(finite(s.value))bar.setAttribute('aria-valuenow',String(s.value));bar.setAttribute('aria-valuetext',number(s.value));const fill=append(bar,'i',undefined,'resultFill');fill.style.width=(finite(s.value)?Math.max(0,s.value)/scale*100:0)+'%';fill.style.background=s.color;
   for(const [value,cls] of [[threshold.caution,''],[threshold.ribbon,' main']]){const mark=append(bar,'i',undefined,'resultMark'+cls);mark.style.left=value/scale*100+'%';mark.title=String(value);}
   const value=append(row,'span',number(s.value),'resultValue');value.style.color=finite(s.value)&&s.value>=threshold.ribbon?s.color:'';
  }
  append($('resultScores'),'div',`주의 ${threshold.caution} · 테두리 ${threshold.ribbon} · 축 0–${Math.ceil(scale)}`,'resultScale');
  $('resultBottleneck').textContent='병목 · '+scores.map(s=>`${s.name} ${s.bottleneck?`${s.bottleneck} ${number(s.factor)}`:'미평가'}`).join(' · ');
  $('resultBottleneck').title=$('resultBottleneck').textContent;$('resultBottleneck').style.cssText='white-space:nowrap;overflow:hidden;text-overflow:ellipsis';
  $('resultQuantities').replaceChildren();for(const [label,key,unit] of [['상층 온도','T_upper_C','℃'],['하층 온도','T_lower_C','℃'],['상층 산소','O2_upper_volfrac','%'],['하층 산소','O2_lower_volfrac','%'],['연기층 경계 높이','interface_m','m'],['화원 발열','HRR_actual_kW','kW'],['문 분출 연소','HRR_doorjet_kW','kW'],['상층 연소','HRR_upperburn_kW','kW']]){const v=values?.[key]?.[index];append($('resultQuantities'),'span',label);append($('resultQuantities'),'b',finite(v)?number(v*(unit==='%'?100:1),1)+' '+unit:'미평가');}
  if(previous!==result){const list=$('resultLimits').querySelector('ul');list.replaceChildren();for(const text of [...result.limits_text,'지수는 저장된 조건값 × 100이며 실제 발생 확률이 아닙니다. 여러 셀로 나뉜 방은 평균을 만들지 않습니다.','MC 집계는 저장된 완주 표본만 읽습니다. 미완료·읽기 실패·미평가 값은 안전으로 세지 않습니다.','연기 무늬와 화염·플룸은 표시 효과입니다. 온도 입력은 변경하지 않습니다.'])append(list,'li',text);previous=result;}
 }
 function mc(summary,full=null){const host=$('resultMCRows');host.replaceChildren();for(const [key,name] of resultTypes){const r=summary?.rates?.[key],q=full?.[key],tr=append(host,'tr');tr.dataset.type=key;for(const text of [name,r?`${r.numerator}/${r.denominator_completed_random}`:'미평가',q?(q.unknown?'≥':'')+q.rooms:'미집계',r&&finite(r.maximum_score)?number(r.maximum_score*100):'미평가'])append(tr,'td',text);if(q?.unknown)tr.title='미평가 값이 있어 최대 실 수는 확인된 하한입니다.';}
  $('resultMCBasis').replaceChildren();if(summary)$('resultMCBasis').append(infoTip(`조건 표본·지수 최대: 무작위 완주 / 최대 실: 전체 완주 ${summary.completed}표본`));
  const worst=summary?.worst;$('resultMCApplyWorst').disabled=!worst||store.get('buildingReview').saving;$('resultMCWorst').textContent=worst?`${worst.sample_id} · 연소 ${worst.burning} · 주의 이상 ${worst.attention} · 최초 FO ${worst.first_FO_s===null?'—':stamp(worst.first_FO_s)}`:(summary?.worst_error||'');
  $('resultMCStatus').textContent=summary?`저장 ${summary.completed}/${summary.rows.length}표본`:'저장 MC 집계 없음';$('resultMCLoad').disabled=!summary;
 }
 mc(null);
 return {update,mc,mountReview(review){$('resultReviewMount').append(review);review.hidden=false;},dispose(){for(const undo of moves.reverse())undo();panel.hidden=false;root.remove();style.remove();}};
}
