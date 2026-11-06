// Saved playback navigation only: selecting a row never starts a calculation.
export function resultListRows(cases,result,floors){
 const rooms=new Map(floors.flatMap(f=>f.rooms.map(r=>[`CAD_${f.name}_${r.id}`,{floor:f.name,room:r}])));
 const roomName=source=>source.room.names?.filter(Boolean).join(' · ')||source.room.name||'';
 const current=result&&!result.source_refs?.model_preview&&['complete','partial'].includes(result.status)?result:null;
 const rows=new Map(cases.filter(c=>c.id).map(c=>[c.id,{...c}]));
 if(current&&!rows.has(current.result_id))rows.set(current.result_id,{id:current.result_id,label:current.result_id});
 return [...rows.values()].map(row=>{
  const active=row.id===current?.result_id,source=active?rooms.get(current.scenario.origin_room_id):null;
  const label=String(row.label||row.id).replace(/(?:CAD_)?(B?\d+F?|PH)[ _]+(R\d+)(?:_C\d+)?/g,(match,f,r)=>{const s=rooms.get(`CAD_${f}_${r}`);return s?`${f} ${r}${roomName(s)?' · '+roomName(s):''}`:match.replaceAll('_',' ');});
  const engine=active?current.engine.kind:row.engine_kind;
  const engineLabel=['lite','pyrocast_lite'].includes(engine)?'간략':['cfast','cfast_native'].includes(engine)?'CFAST 원본':'방식 미확인';
  const minutes=Number.isFinite(row.duration_s)?`${Math.round(row.duration_s/60)}분`:'';
  const d=new Date(row.saved_at_ms),date=Number.isFinite(row.saved_at_ms)&&!Number.isNaN(d.valueOf())?`${d.getMonth()+1}/${d.getDate()} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`:'';
  const detail=[minutes,date].filter(Boolean).join(' · ');
  return {...row,active,engineLabel,detail,label:source?`${source.floor} ${source.room.id}${roomName(source)?' · '+roomName(source):''} · ${current.engine.kind==='cfast'?'CFAST':'간략'}${/MC\s+S\d+/.exec(label)?.[0]?' · '+/MC\s+S\d+/.exec(label)[0]:''}`:label};
 }).sort((a,b)=>Number(b.active)-Number(a.active));
}
export function createResultList({container,store,floors,onSelect}){
 let cases=[],pending=null,disposed=false,previousActive=null;
 const box=document.createElement('details');box.id='sceneResultList';const narrow=matchMedia('(max-width:600px)');box.open=!narrow.matches;box.hidden=true;
 const resizeList=()=>{box.open=!narrow.matches;};narrow.addEventListener('change',resizeList);
 box.innerHTML='<summary>계산 결과</summary><div class="sceneResultRows" role="group" aria-label="저장된 계산 결과"></div><div class="sceneResultStatus" role="status" hidden></div>';
 const rows=box.querySelector('.sceneResultRows'),status=box.querySelector('.sceneResultStatus');
 const style=document.createElement('style');style.textContent=`#sceneResultList{position:absolute;left:10px;top:10px;z-index:110;width:250px;max-width:calc(100% - 60px);box-sizing:border-box;background:color-mix(in srgb,var(--bg-card) 90.980392%,transparent);border:1px solid var(--border);border-radius:7px;color:var(--text);font:11px/1.4 system-ui,'Malgun Gothic',sans-serif;box-shadow:0 2px 8px var(--shadow)}#sceneResultList[hidden],#sceneResultList [hidden]{display:none!important}#sceneResultList summary{padding:5px 8px;cursor:pointer;font-weight:600}#sceneResultList .sceneResultRows{max-height:114px;overflow:auto;overscroll-behavior:contain;padding:0 4px}#sceneResultList button{display:flex;align-items:center;gap:5px;width:100%;box-sizing:border-box;text-align:left;height:38px;padding:4px 6px;border:1px solid transparent;border-radius:4px;background:transparent;color:var(--text-muted);font:inherit;cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}#sceneResultList .resultText{display:flex;flex-direction:column;min-width:0;flex:1}#sceneResultList .resultDetail{font-size:11px;font-weight:400;color:var(--text-muted);overflow:hidden;text-overflow:ellipsis}#sceneResultList .resultName{font-size:13px;min-width:0;overflow:hidden;text-overflow:ellipsis;flex:1}#sceneResultList .resultEngine{flex:none;font-size:11px;padding:1px 4px;border:1px solid var(--border-strong);border-radius:3px;color:var(--text)}#sceneResultList button:hover{background:var(--bg-control-hover)}#sceneResultList button[aria-current=true]{color:var(--accent);background:var(--bg-selected);border-color:var(--accent);font-weight:700}#sceneResultList button:focus-visible,#sceneResultList summary:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}#sceneResultList button:disabled{cursor:wait;opacity:.65}#sceneResultList .sceneResultStatus{padding:6px 10px;color:var(--busy)}@media(max-width:600px){#sceneResultList .sceneResultRows{max-height:76px}#sceneResultList{left:8px;top:8px}}`;
 container.append(box);document.head.append(style);
 const stop=e=>e.stopPropagation();for(const type of ['pointerdown','pointerup','click','dblclick','wheel'])box.addEventListener(type,stop);
 function render(){if(disposed)return;const entries=resultListRows(cases,store.get('result'),floors);box.hidden=!entries.length;box.querySelector('summary').textContent='계산 결과 · '+entries.length;rows.replaceChildren();
  for(const entry of entries){const b=document.createElement('button');b.type='button';b.dataset.caseId=entry.id;const name=document.createElement('span');name.className='resultName';name.textContent=entry.label.replace(/ · (?:순정 CFAST|CFAST|간략 계산|간략|저장 결과)(?= ·|$)/g,'');const badge=document.createElement('span');badge.className='resultEngine';badge.textContent=entry.engineLabel;const text=document.createElement('span');text.className='resultText';text.append(name);if(entry.detail){const sub=document.createElement('small');sub.className='resultDetail';sub.textContent=entry.detail;text.append(sub);}b.append(text,badge);b.title=[entry.engineLabel,name.textContent,entry.detail,entry.run_id!==entry.id?entry.run_id:null,entry.id].filter(Boolean).join(' · ');b.setAttribute('aria-current',String(entry.active));b.disabled=pending!==null;
   b.onclick=async()=>{if(pending!==null)return;pending=entry.id;status.hidden=false;status.textContent='결과 불러오는 중…';box.setAttribute('aria-busy','true');render();
    try{await onSelect(entry.id);if(!disposed){status.textContent='';status.hidden=true;}}
    catch(error){if(!disposed){status.hidden=false;status.textContent='결과 읽기 실패 · '+error.message;}}
    finally{pending=null;if(!disposed){box.setAttribute('aria-busy','false');render();}}
   };rows.append(b);
  }
  const active=entries.find(e=>e.active)?.id??null;if(active!==previousActive){rows.scrollTop=0;previousActive=active;}
 }
 const off=store.subscribe('result',render);render();
 return {setCases(value){cases=value||[];render();},dispose(){disposed=true;narrow.removeEventListener('change',resizeList);off();box.remove();style.remove();}};
}
