// Shared entry point. CAD import stays on the loopback model-library service.
export function createNewBuildingButton({container,onCreated}){
 const origin='http://127.0.0.1:8841',button=document.createElement('button');button.id='shellNewBuilding';button.type='button';button.textContent='새 건물 생성하기';button.style.whiteSpace='nowrap';container.append(button);
 const offline=window.__PYROCAST_OFFLINE__||location.protocol==='file:';button.disabled=!!offline;button.title=offline?'보기 전용 · 운영 앱에서 생성하세요':'CAD 도면(DWG·DXF)으로 새 건물 생성';
 let dialog=null,frame=null;
 function close(){dialog?.close();}
 function open(url){if(!dialog){dialog=document.createElement('dialog');dialog.setAttribute('aria-label','새 건물 생성·모델 검토');dialog.style.cssText='width:min(1100px,96vw);height:90vh;max-width:96vw;padding:0;border:1px solid var(--border-strong);border-radius:10px;background:var(--bg-scene);color:var(--text);overflow:hidden';
  const bar=document.createElement('div');bar.style.cssText='display:flex;justify-content:flex-end;padding:8px;background:var(--bg-card)';const exit=document.createElement('button');exit.textContent='닫기';exit.setAttribute('aria-label','새 건물 생성 창 닫기');exit.onclick=close;bar.append(exit);
  frame=document.createElement('iframe');frame.title='새 건물 도면 업로드';frame.src=origin+'/models/new';frame.style.cssText='display:block;border:0;width:100%;height:calc(100% - 46px)';dialog.append(bar,frame);document.body.append(dialog);
 }frame.src=url;if(!dialog.open)dialog.showModal();}
 button.onclick=()=>open(origin+'/models/new');
 const review=e=>{if(/^(?:cad|scan)-[a-f0-9]{32}$/.test(e.detail?.id||''))open(origin+'/models/?id='+encodeURIComponent(e.detail.id));};
 window.addEventListener('firelapse:review-model',review);
 const receive=async e=>{if(e.origin!==origin||e.source!==frame?.contentWindow||!/^(?:cad|scan)-[a-f0-9]{32}$/.test(e.data?.id||''))return;
  if(e.data.type==='pyrocast:model-created')onCreated?.();
  if(e.data.type==='pyrocast:open-created-model'){
   const id=e.data.id;
   try{const r=await fetch(origin+'/models/catalog.json');if(!r.ok)throw Error('catalog');const c=await r.json(),entry=c.models.find(m=>m.id===id);const u=entry?.operation_url&&new URL(entry.operation_url);if(u&&u.protocol==='http:'&&u.hostname==='127.0.0.1'&&u.pathname==='/model.html'){location.assign(u.href);return;}}catch{}
   open(origin+'/models/?id='+encodeURIComponent(id));
  }
 };
 window.addEventListener('message',receive);
 return ()=>{window.removeEventListener('message',receive);window.removeEventListener('firelapse:review-model',review);dialog?.remove();button.remove();};
}
