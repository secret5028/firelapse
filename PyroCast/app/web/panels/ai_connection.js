export function createAIConnectionControl(parent){
 const origin='http://127.0.0.1:8841',root=document.createElement('div');root.style.cssText='padding:10px 16px;display:flex;gap:8px;align-items:center;font-size:12px';root.id='aiConnectionControl';
 const button=document.createElement('button'),status=document.createElement('span');button.type='button';button.textContent='AI 연결';button.id='aiConnectButton';status.textContent='미연결';root.append(button,status);parent.prepend(root);
 const offline=!!window.__PYROCAST_OFFLINE__||location.protocol==='file:';button.disabled=offline;if(offline)status.textContent='보기 전용';
 let dialog=null,frame=null,disposed=false;
 button.onclick=()=>{dialog=document.createElement('dialog');dialog.setAttribute('aria-label','AI API 연결');dialog.style.cssText='width:min(480px,90vw);padding:8px;border:1px solid var(--compat-7292a3);border-radius:9px;background:var(--bg-card);color:var(--compat-018fa96a)';const close=document.createElement('button');close.textContent='닫기';close.onclick=()=>dialog.close();frame=document.createElement('iframe');frame.title='AI API 설정';frame.src=origin+'/models/ai';frame.style.cssText='width:100%;height:520px;border:0';dialog.append(close,frame);document.body.append(dialog);dialog.addEventListener('close',()=>{dialog.remove();dialog=null;frame=null;},{once:true});dialog.showModal();};
 const show=v=>{status.textContent=v.connected?'연결됨':'미연결';status.title=v.model||'';};
 const receive=e=>{if(e.origin!==origin||e.source!==frame?.contentWindow||e.data?.type!=='pyrocast:ai-connection')return;show(e.data);window.dispatchEvent(new CustomEvent('pyrocast:ai-connection',{detail:e.data}));};window.addEventListener('message',receive);
 if(!offline)fetch(origin+'/models/ai/connection').then(r=>r.json()).then(v=>{if(!disposed)show(v);}).catch(()=>{if(!disposed)status.textContent='연결 서버 확인 필요';});
 return ()=>{disposed=true;window.removeEventListener('message',receive);dialog?.remove();root.remove();};
}
