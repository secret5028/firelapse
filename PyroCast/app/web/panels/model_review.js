// CAD quality is independent of playback and hazard indices.
export function reviewRows(building){
 const r=building?.model_review;
 return [...(r?.corrections||[]).map(x=>({...x,status:'자동보정',detail:x.kind==='aperture_width'?`개구부 폭 ${x.before} → ${x.after} m`:`연결 ${JSON.stringify(x.before)} → ${JSON.stringify(x.after)}`})),
  ...(r?.items||[]).map(x=>({...x,status:x.kind==='estimated_usage'?'용도 추정':x.kind==='door_connection_estimated'&&x.sides?'연결 추정':'검토 필요'}))];
}
export function createModelReview({container,building,onLocate=()=>{}}){
 const rows=reviewRows(building),root=document.createElement('details');root.className='modelReview';root.open=rows.length>0;
 const add=(p,tag,text)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;p.append(e);return e;};
 add(root,'summary',building?.model_review?`모델 점검 · 자동보정 ${building.model_review.corrections.length} · 추정/검토 ${building.model_review.items.length}`:'모델 점검 · 미실시');
 const tip=add(root,'div','기하 근거에 따른 보정 · 현장 확인 아님');tip.style.color='#9eb2c4';
 if(building?.model_review?.connectivity_validation==='incomplete')add(root,'div',`연결 검증 미완료 · 미연결 공간 ${building.model_review.unresolved_space_count}개`);
 const floor=add(root,'select');floor.setAttribute('aria-label','점검 층');add(floor,'option','모든 층').value='';
 for(const f of building?.floors||[])add(floor,'option',f.name).value=f.name;
 const status=add(root,'select');status.setAttribute('aria-label','점검 분류');add(status,'option','모든 분류').value='';
 for(const s of ['자동보정','연결 추정','용도 추정','검토 필요'])add(status,'option',s).value=s;
 const scroll=add(root,'div');scroll.style.cssText='max-height:360px;overflow:auto';
 const table=add(scroll,'table'),head=add(table,'thead'),tr=add(head,'tr');for(const s of ['위치','상태','내용'])add(tr,'th',s);const body=add(table,'tbody');
 function render(){body.replaceChildren();for(const r of rows.filter(x=>(!floor.value||x.floor===floor.value)&&(!status.value||x.status===status.value))){
  const tr=add(body,'tr'),button=add(add(tr,'td'),'button',`${r.floor} ${r.id}`);button.onclick=()=>onLocate(r);button.title='도면 위치 보기';
  const s=add(tr,'td',r.status);s.style.color=r.status==='자동보정'?'#7bd6c4':'#edbf75';
  const detail=add(tr,'td',r.detail);detail.title=JSON.stringify(r,null,2);
 }}
 floor.onchange=status.onchange=render;render();container.prepend(root);
 return {root,dispose(){root.remove();}};
}
