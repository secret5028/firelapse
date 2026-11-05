// Shared entry point. Scan import stays on the loopback model-library service.
export function createNewBuildingButton({container,onCreated}){
 const origin='http://127.0.0.1:8841',button=document.createElement('button');button.id='shellNewBuilding';button.type='button';button.textContent='새 건물 생성하기';button.style.whiteSpace='nowrap';container.append(button);
 const offline=window.__PYROCAST_OFFLINE__||location.protocol==='file:';button.disabled=!!offline;button.title=offline?'보기 전용 · 운영 앱에서 생성하세요':'스캔 도면 파일·폴더로 새 건물 생성';
 let dialog=null,frame=null;
 function close(){dialog?.close();}
 button.onclick=()=>{if(!dialog){dialog=document.createElement('dialog');dialog.setAttribute('aria-label','새 건물 생성하기');dialog.style.cssText='width:min(1100px,96vw);height:90vh;max-width:96vw;padding:0;border:1px solid #7292a3;border-radius:10px;background:#102331;color:#eaf3f8;overflow:hidden';
  const bar=document.createElement('div');bar.style.cssText='display:flex;justify-content:flex-end;padding:8px;background:#163345';const exit=document.createElement('button');exit.textContent='닫기';exit.setAttribute('aria-label','새 건물 생성 창 닫기');exit.onclick=close;bar.append(exit);
  frame=document.createElement('iframe');frame.title='새 건물 도면 업로드';frame.src=origin+'/models/new';frame.style.cssText='display:block;border:0;width:100%;height:calc(100% - 46px)';dialog.append(bar,frame);document.body.append(dialog);
 }dialog.showModal();};
 const receive=e=>{if(e.origin!==origin||e.source!==frame?.contentWindow||!/^scan-[a-f0-9]{32}$/.test(e.data?.id||''))return;
  if(e.data.type==='pyrocast:model-created')onCreated?.();
  if(e.data.type==='pyrocast:open-created-model')location.assign(origin+'/models/?id='+encodeURIComponent(e.data.id));
 };
 window.addEventListener('message',receive);
 return ()=>{window.removeEventListener('message',receive);dialog?.remove();button.remove();};
}
