// Self-contained result export. Preserve original JSON bytes for the result hash.
// No server, CDN, or CFAST executable is required to replay the exported file.
(function installHtmlExport(){
 const $=id=>document.getElementById(id),offline=window.CAD_OFFLINE;
 const button=document.createElement('button');button.id='htmlExport';button.textContent='HTML 내보내기';
 button.title='건물·계산 결과·보기 설정을 HTML 한 파일로 저장';$('legacyTools').prepend(button);
 const status=document.createElement('p');status.id='htmlExportStatus';status.setAttribute('role','status');status.style.cssText='font-size:11px;line-height:1.5';button.after(status);
 const files=['building.json','legacy-context.json','cfast-demo.json'];
 const modules={'three':'/cad-assets/three.module.js','three/addons/controls/OrbitControls.js':'/cad-assets/addons/controls/OrbitControls.js','three/addons/renderers/CSS2DRenderer.js':'/cad-assets/addons/renderers/CSS2DRenderer.js','three/addons/exporters/OBJExporter.js':'/cad-assets/addons/exporters/OBJExporter.js'};
 const encode=bytes=>{let s='';for(let i=0;i<bytes.length;i+=32768)s+=String.fromCharCode(...bytes.subarray(i,i+32768));return btoa(s)};
 const encodeText=s=>encode(new TextEncoder().encode(s));
 const safeJson=value=>JSON.stringify(value).replace(/</g,'\\u003c');
 const controlIds=['above','ex','op','wallTransparency','rl','gl','cl','dl','sh','show_stair','show_elev','show_ramp','show_anchor','coreEmphasis','ramp_slope','ramp_reverse','layer_wall','layer_opening','layer_outline','layer_grid','layer_floor','layer_reference','structuralCeiling','cfMode','cfSpeed','cfPaths','cfFuelFilter'];
 function snapshot(){return {floor:selFloor,camera:C.position.toArray(),target:O.target.toArray(),zoom:C.zoom,
  controls:Object.fromEntries(controlIds.filter(id=>$(id)).map(id=>[id,{value:$(id).value,checked:$(id).checked}])),
  doors:leaves.map(s=>({floor:s.floor,id:s.id,j:s.j,pct:s.pct,rev:s.rev})),windows:wins.map(w=>({floor:w.floor,id:w.id,pct:w.pct})),
  floors:[...shownFloors],ceilings:ceilState.map(s=>({on:s.on,h:s.h})),
  cfast:JSON.parse(document.body.dataset.cfastState||'null')};}
 function bootstrap(pack){
  window.CAD_OFFLINE=pack;
  window.fetch=async(input,options={})=>{
   const value=typeof input==='string'?input:input.url,key=value.split(/[?#]/)[0].split('/').pop();
   if((options.method||'GET').toUpperCase()==='GET'&&Object.hasOwn(pack.files,key)){
    const bytes=Uint8Array.from(atob(pack.files[key]),c=>c.charCodeAt(0));return new Response(bytes,{headers:{'Content-Type':'application/json'}});
   }
   return new Response('내보낸 HTML에서는 서버 작업을 실행할 수 없습니다.',{status:404});
  };
 }
 let cached=null;
 async function resources(){
  if(offline)return {source:offline.source,files:{...offline.files},imports:{...offline.imports}};
  if(cached)return cached;
  const r=await fetch(location.href,{cache:'no-store'});if(!r.ok)throw Error('화면 원본을 읽지 못했습니다.');
  const source=await r.text(),payload={},imports={};
  await Promise.all(files.map(async name=>{const r=await fetch(name,{cache:'no-store'});if(r.status===404&&name==='cfast-demo.json')return;if(!r.ok)throw Error(name+' 읽기 실패');const bytes=new Uint8Array(await r.arrayBuffer());JSON.parse(new TextDecoder().decode(bytes));payload[name]=encode(bytes)}));
  await Promise.all(Object.entries(modules).map(async([key,url])=>{const r=await fetch(url);if(!r.ok)throw Error('3D 라이브러리 읽기 실패');const code=await r.text();imports[key]='data:text/javascript;base64,'+encodeText(code)}));
  cached={source,files:payload,imports};return cached;
 }
 async function exportHtml(){
  const base=await resources(),view=snapshot(),context={...legacyContext,state:{version:1,jobId:legacyContext.jobId,operations:structuredClone(state.operations)}};
  if(base.files['cfast-demo.json']&&!view.cfast)throw Error('계산 결과가 아직 준비되지 않았습니다. 로딩 후 다시 시도하세요.');
  const pack={version:1,createdAt:new Date().toISOString(),source:base.source,files:{...base.files,'legacy-context.json':encodeText(JSON.stringify(context))},imports:base.imports,view,hydraulics:window.HydraulicUI?.getNetwork()||null};
  const doc=new DOMParser().parseFromString(base.source,'text/html'),map=doc.querySelector('script[type="importmap"]');
  if(!map)throw Error('3D 모듈 설정이 없습니다.');map.textContent=safeJson({imports:pack.imports});
  const boot=doc.createElement('script');boot.textContent='('+bootstrap.toString()+')('+safeJson(pack)+');';map.before(boot);
  doc.title='소방 크로키 업 · 저장된 3D 결과';
  return new Blob(['<!doctype html>\n'+doc.documentElement.outerHTML],{type:'text/html;charset=utf-8'});
 }
 button.onclick=async()=>{button.disabled=true;status.textContent='건물·결과·3D 라이브러리를 묶는 중…';try{
  const blob=await exportHtml(),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='소방-3D-결과-'+new Date().toISOString().slice(0,10)+'.html';a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);
  status.textContent=`HTML 저장 준비 완료 · ${(blob.size/1024/1024).toFixed(1)} MB · 서버 없이 결과 재생 가능`;
 }catch(error){status.textContent='내보내기 실패: '+error.message;console.error('HTML export',error)}finally{button.disabled=false}};
 if(offline){
  status.textContent='저장된 결과 · 오프라인 보기 / 조건 변경 후 재계산은 원래 웹앱에서 실행';
  document.querySelectorAll('a[href="plans.html"],#mode2d').forEach(a=>{a.removeAttribute('href');a.title='평면도 원본은 기존 웹앱에서 확인';a.style.opacity='.5'});
  for(const id of ['fzpick','fzmc'])if($(id))$(id).disabled=true;
  const view=offline.view;
  const restore=()=>{
   if(offline.files['cfast-demo.json']&&!document.body.dataset.cfastState)return false;
   if(view.cfast&&$('cfEnabled')){$('cfEnabled').checked=view.cfast.enabled;$('cfEnabled').dispatchEvent(new Event('change'));}
   for(const[id,v]of Object.entries(view.controls)){const e=$(id);if(!e||e.disabled)continue;e.value=v.value;if(e.type==='checkbox')e.checked=v.checked;e.dispatchEvent(new Event(e.type==='range'||e.type==='number'?'input':'change'));}
   view.floors.forEach((v,i)=>shownFloors[i]=v);view.ceilings.forEach((s,i)=>Object.assign(ceilState[i],s));
   [...$('fbtn').children].find(b=>b.textContent===(view.floor==='all'?'전체':view.floor))?.click();
   if(view.cfast){$(view.cfast.mode==='real'?'cfReal':'cfBasic')?.click();if($('cfRoom')){$('cfRoom').value=view.cfast.selected;$('cfRoom').dispatchEvent(new Event('change'));}if($('cfTime')){$('cfTime').value=view.cfast.time;$('cfTime').dispatchEvent(new Event('input'));}}
   for(const s of leaves){const v=view.doors.find(v=>v.floor===s.floor&&v.id===s.id&&v.j===s.j);if(v){s.pct=v.pct;s.rev=v.rev;s.cur=leafTarget(s);s.piv.rotation.z=s.cur}}
   for(const w of wins){const v=view.windows.find(v=>v.floor===w.floor&&v.id===w.id);if(v){w.pct=v.pct;paintWin(w)}}
   applyCeil();applyFloor();C.position.fromArray(view.camera);C.zoom=view.zoom;C.updateProjectionMatrix();O.target.fromArray(view.target);O.update();
   document.body.dataset.htmlExportRestored='true';return true;
  };
  let attempts=0;const timer=setInterval(()=>{if(restore())clearInterval(timer);else if(++attempts>150){clearInterval(timer);status.textContent='저장된 결과 초기화 실패 · 개발자 오류를 확인하세요.'}},100);
 }
})();
