// Clear-height surfaces use the same room heights as this saved calculation.
// Structural slabs, floor elevations and vertical transport geometry stay intact.
function createCfastCeilingDisplay(data,rows,floorIndex,geometry){
 if(!data.ceiling_config)return {setEnabled(){},stats(){return null}};
 const saved=ceilState.map(s=>({on:s.on,h:s.h})),meshes=[],controls=[];
 let active=false;
 for(const r of rows){if(r.core_kind||r.height>=(r.structural_height||r.height)-.05)continue;
  const mesh=ext(geometry(r),r.height-.025,r.height,mat.ceil);
  if(mesh){mesh.name='cfast_clear_ceiling_'+r.key;mesh.raycast=()=>{};groups[floorIndex.get(r.floor)].add(mesh);meshes.push({mesh,r});}
 }
 const floorLabels=[...document.getElementById('fl').children];
 B.floors.forEach((f,i)=>{const label=floorLabels[i*2+1];if(!label)return;const cb=label.querySelector('input[type=checkbox]'),number=label.querySelector('input[type=number]');
  const texts=[...(floorLabels[i*2]?.childNodes||[])].filter(n=>n.nodeType===3).map(n=>({n,text:n.textContent}));
  controls.push({i,cb,number,disabled:number?.disabled,value:number?.value,title:number?.title,texts});
 });
 function sync(){for(const {mesh,r}of meshes)mesh.visible=active&&ceilState[floorIndex.get(r.floor)].on&&document.getElementById('cl').checked;
  if(active)for(const s of ceilState)if(s.mesh)s.mesh.visible=false;
 }
 const previousApply=applyCeil;applyCeil=function(){previousApply();sync()};
 return {
  setEnabled(on){if(on!==active){active=on;for(const c of controls){const f=B.floors[c.i],rs=rows.filter(r=>r.floor===f.name&&!r.core_kind),st=ceilState[c.i];
    if(on){const occupied=rs.filter(r=>r.height<(r.structural_height||r.height)-.05);st.on=occupied.length>0;st.h=occupied.length?Math.max(...occupied.map(r=>r.height)):st.h;}
    else Object.assign(st,saved[c.i]);
    if(c.cb)c.cb.checked=st.on;
    for(const t of c.texts)t.n.textContent=on?t.text.replace(/반자 [^,]+/,'반자 실별 도면·추정'):t.text;
    if(c.number){c.number.disabled=on||c.disabled;c.number.value=on?st.h.toFixed(2):c.value;c.number.title=on?'저장된 계산의 실별 반자고. 선택 실의 높이는 결과창에 표시됩니다.':c.title;}
   }applyCeil();}sync();},
  stats(){return {active,ceilingRoomCount:meshes.length,visibleCeilingCount:meshes.filter(v=>v.mesh.visible).length,source:'saved solver room clear heights',fireFloorHeights:meshes.filter(v=>v.r.floor==='3F').map(v=>({room:v.r.key,height:v.r.height})),structuralSlabsUnchanged:true};}
 };
}
