// Saved playback navigation only: selecting a row never starts a calculation.
export function resultListRows(cases,result,floors){
 const rooms=new Map(floors.flatMap(f=>f.rooms.map(r=>[`CAD_${f.name}_${r.id}`,{floor:f.name,room:r}])));
 const roomName=source=>source.room.names?.filter(Boolean).join(' · ')||source.room.name||'';
 const current=result&&['complete','partial'].includes(result.status)?result:null;
 const rows=new Map(cases.filter(c=>c.id).map(c=>[c.id,{...c}]));
 if(current&&!rows.has(current.result_id))rows.set(current.result_id,{id:current.result_id,label:current.result_id});
 return [...rows.values()].map(row=>{
  const active=row.id===current?.result_id,source=active?rooms.get(current.scenario.origin_room_id):null;
  const label=String(row.label||row.id).replace(/(?:CAD_)?(B?\d+F?|PH)[ _]+(R\d+)(?:_C\d+)?/g,(match,f,r)=>{const s=rooms.get(`CAD_${f}_${r}`);return s?`${f} ${r}${roomName(s)?' · '+roomName(s):''}`:match.replaceAll('_',' ');});
  const engine=active?current.engine.kind:row.engine_kind;
  const engineLabel=['lite','pyrocast_lite'].includes(engine)?'간략':['cfast','cfast_native'].includes(engine)?'CFAST 원본':'방식 미확인';
  return {...row,active,engineLabel,label:source?`${source.floor} ${source.room.id}${roomName(source)?' · '+roomName(source):''} · ${current.engine.kind==='cfast'?'CFAST':'간략'}${/MC\s+S\d+/.exec(label)?.[0]?' · '+/MC\s+S\d+/.exec(label)[0]:''}`:label};
 }).sort((a,b)=>Number(b.active)-Number(a.active));
}
export function createResultList({container,store,floors,onSelect}){
 let cases=[],pending=null,disposed=false,previousActive=null;
 const box=document.createElement('details');box.id='sceneResultList';box.open=true;box.hidden=true;
 box.innerHTML='<summary>계산 결과</summary><div class="sceneResultRows" role="group" aria-label="저장된 계산 결과"></div><div class="sceneResultStatus" role="status" hidden></div>';
 const rows=box.querySelector('.sceneResultRows'),status=box.querySelector('.sceneResultStatus');
 const style=document.createElement('style');style.textContent=`#sceneResultList{position:absolute;left:10px;top:10px;z-index:110;width:230px;max-width:calc(100% - 60px);box-sizing:border-box;background:#142b3be8;border:1px solid #496273;border-radius:7px;color:#dcebf3;font:11px/1.4 system-ui,'Malgun Gothic',sans-serif;box-shadow:0 2px 8px #0002}#sceneResultList[hidden],#sceneResultList [hidden]{display:none!important}#sceneResultList summary{padding:5px 8px;cursor:pointer;font-weight:600}#sceneResultList .sceneResultRows{max-height:78px;overflow:auto;overscroll-behavior:contain;padding:0 4px}#sceneResultList button{display:flex;align-items:center;gap:5px;width:100%;box-sizing:border-box;text-align:left;height:26px;padding:4px 6px;border:1px solid transparent;border-radius:4px;background:transparent;color:#c1d2dd;font:inherit;cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}#sceneResultList .resultName{min-width:0;overflow:hidden;text-overflow:ellipsis;flex:1}#sceneResultList .resultEngine{flex:none;font-size:10px;padding:1px 4px;border:1px solid #617786;border-radius:3px;color:#e4edf4}#sceneResultList button:hover{background:#254353}#sceneResultList button[aria-current=true]{color:#ff8585;background:#4c3039;border-color:#db6a75;font-weight:700}#sceneResultList button:focus-visible,#sceneResultList summary:focus-visible{outline:2px solid #42c4e8;outline-offset:-2px}#sceneResultList button:disabled{cursor:wait;opacity:.65}#sceneResultList .sceneResultStatus{padding:6px 10px;color:#ffbd85}`;
 container.append(box);document.head.append(style);
 const stop=e=>e.stopPropagation();for(const type of ['pointerdown','pointerup','click','dblclick','wheel'])box.addEventListener(type,stop);
 function render(){if(disposed)return;const entries=resultListRows(cases,store.get('result'),floors);box.hidden=!entries.length;box.querySelector('summary').textContent='계산 결과 · '+entries.length;rows.replaceChildren();
  for(const entry of entries){const b=document.createElement('button');b.type='button';b.dataset.caseId=entry.id;const name=document.createElement('span');name.className='resultName';name.textContent=entry.label.replace(/ · (?:순정 CFAST|CFAST|간략 계산|간략|저장 결과)(?= ·|$)/g,'');const badge=document.createElement('span');badge.className='resultEngine';badge.textContent=entry.engineLabel;b.append(name,badge);b.title=entry.engineLabel+' · '+String(entry.label)+' · '+entry.id;b.setAttribute('aria-current',String(entry.active));b.disabled=pending!==null;
   b.onclick=async()=>{if(pending!==null)return;pending=entry.id;status.hidden=false;status.textContent='결과 불러오는 중…';box.setAttribute('aria-busy','true');render();
    try{await onSelect(entry.id);if(!disposed){status.textContent='';status.hidden=true;}}
    catch(error){if(!disposed){status.hidden=false;status.textContent='결과 읽기 실패 · '+error.message;}}
    finally{pending=null;if(!disposed){box.setAttribute('aria-busy','false');render();}}
   };rows.append(b);
  }
  const active=entries.find(e=>e.active)?.id??null;if(active!==previousActive){rows.scrollTop=0;previousActive=active;}
 }
 const off=store.subscribe('result',render);render();
 return {setCases(value){cases=value||[];render();},dispose(){disposed=true;off();box.remove();style.remove();}};
}
