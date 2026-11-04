import {infoTip} from './explanations.js';
const short=id=>id==='OUTSIDE'?'외기':String(id||'—').replace(/^CAD_/,'').replace('_',' ');
const number=(v,d=0)=>Number.isFinite(v)?v.toFixed(d):'미확인';
export function doorCategory(row){return row.door_class==='fire'?(row.confidence==='inferred'?'inferred':['confirmed','user'].includes(row.confidence)?'confirmed':'unknown'):['ordinary','external'].includes(row.door_class)?'ordinary':'unknown';}
export function buildingTable(score){
 const rows=new Map([...score.ranked,...score.excluded].map(r=>[r.room,r]));
 const uses=score.approved_input?.room_uses||{};
 return [...new Set([...rows.keys(),...Object.keys(uses)])].map(id=>{const r=rows.get(id),b=r?.origin_budget,u=uses[id]??b?.classification;
  return {id,name:u?.name??r?.name??'',usage:u?.label??'미확인',area:u?.area_m2??b?.area_m2??r?.area_m2,load:u?.load_MJ_m2??b?.fuel_load_MJ_m2,coverage:u?.coverage??b?.coverage,hrrpua:u?.hrrpua_kW_m2??b?.hrrpua_kW_m2,basis:[u?.classification_basis,u?.value_basis,u?.table_basis,u?.excluded_reason??r?.excluded_reason].filter(Boolean).join(' · ')};
 }).sort((a,b)=>a.id.localeCompare(b.id,undefined,{numeric:true}));
}
export function openingCounts(doors,openings){const counts={confirmed:0,inferred:0,ordinary:0,window:0,unknown:0};for(const r of doors||[])counts[doorCategory(r)]++;counts.window=(openings||[]).filter(r=>r.class?.includes('window')).length;return counts;}
export function createBuildingPanel({store}){
 const $=id=>document.getElementById(id),root=document.createElement('div');root.id='buildingContent';$('shellPane-building').append(root);
 root.innerHTML='<section id="buildingFuelSection" hidden><h3>실 용도·연료</h3><div class="buildingScroll"><table><thead><tr><th>실·용도</th><th>면적<br>m²</th><th>하중<br>MJ/m²</th><th>피복률</th><th>HRRPUA<br>kW/m²</th></tr></thead><tbody id="buildingFuel"></tbody></table></div></section><p id="buildingSettingsEmpty">이 건물에서 제공하는 연료 설정이 없습니다.</p>';
 const style=document.createElement('style');style.dataset.pyrocastBuildingPanel='true';style.textContent=`#buildingContent{padding:12px 16px;font-size:12px;color:#eaf3f8}#buildingContent h3{font-size:12px;color:#b8cbd8;font-weight:500;margin:14px 0 8px}.buildingScroll{overflow:auto;max-height:370px;border:1px solid #496273;border-radius:6px}#buildingContent table{width:100%;border-collapse:collapse;font-size:11px}#buildingContent th,#buildingContent td{border-bottom:1px solid #304c5e;padding:7px 4px;text-align:right}#buildingContent th:first-child,#buildingContent td:first-child{text-align:left}#buildingContent th{white-space:nowrap}#buildingContent td{vertical-align:top}#buildingContent summary{cursor:pointer}#buildingContent .buildingSource{white-space:normal;overflow-wrap:anywhere;min-width:130px;color:#b8cbd8;margin-top:7px}#buildingSettingsEmpty{color:#b8cbd8}`;document.head.append(style);
 const append=(p,tag,text)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;p.append(e);return e;};
 let previous=null;
 function render(){const s=store.get('buildingReview');if(previous===s.rooms)return;previous=s.rooms;
  const rows=s.rooms||[];$('buildingFuelSection').hidden=!rows.length;$('buildingSettingsEmpty').hidden=!!rows.length;
  $('buildingFuel').replaceChildren();for(const row of rows){const tr=append($('buildingFuel'),'tr');tr.dataset.room=row.id;const first=append(tr,'td'),details=append(first,'details');append(details,'summary',`${short(row.id)} · ${row.usage}`);const source=append(details,'div',`CAD 원문: ${row.name||'미제공'}`);source.className='buildingSource';source.append(infoTip(row.basis||'근거 미제공'));for(const text of [number(row.area,1),number(row.load),Number.isFinite(row.coverage)?number(row.coverage*100)+'%':'미확인',number(row.hrrpua)])append(tr,'td',text);}
 }
 const off=store.subscribe('buildingReview',render);render();
 return {dispose(){off();root.remove();style.remove();}};
}
