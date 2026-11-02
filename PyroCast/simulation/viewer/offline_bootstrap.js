// Standalone runtime. No server fallback, including when opened over HTTP.
(() => {
 const bytes=Uint8Array.from(atob(document.getElementById('pcOfflineData').textContent.trim()),c=>c.charCodeAt(0));
 const data=JSON.parse(pako.ungzip(bytes,{to:'string'}));
 window.__PYROCAST_OFFLINE__=data;
 const errors=[];
 const record=e=>{errors.push(String(e.message||e.reason||e));document.documentElement.dataset.offlineErrors=String(errors.length);document.documentElement.dataset.offlineErrorMessages=JSON.stringify(errors);};
 window.addEventListener('error',record);window.addEventListener('unhandledrejection',record);
 document.documentElement.dataset.offlineErrors='0';
 document.documentElement.dataset.offlineCase=data.case_id;
 const icon=document.createElement('link');icon.rel='icon';icon.href='data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg"/>';document.head.append(icon);
 const plans=document.getElementById('mode2d');if(plans){plans.removeAttribute('href');plans.title='단독 HTML에는 원본 평면도 페이지가 포함되지 않습니다';plans.setAttribute('aria-disabled','true');}
 window.fetch=async(input,options={})=>{
  const method=options.method||input?.method||'GET';
  if(method!=='GET')return new Response(JSON.stringify({error:'보기 전용'}),{status:405,headers:{'Content-Type':'application/json'}});
  const path=new URL(typeof input==='string'?input:input.url,'https://offline.invalid'+data.base_path).pathname;
  if(!Object.hasOwn(data.routes,path))throw Error('단독 파일에 포함되지 않은 자료: '+path);
  const value=data.routes[path];return new Response(path.endsWith('.js')?value:JSON.stringify(value),{headers:{'Content-Type':path.endsWith('.js')?'text/javascript':'application/json'}});
 };
 const imports={};
 for(const [path,code] of Object.entries(data.modules))imports['pc:'+path]=URL.createObjectURL(new Blob([code],{type:'text/javascript'}));
 const map=document.createElement('script');map.type='importmap';map.textContent=JSON.stringify({imports});document.head.append(map);
 for(const code of data.scripts){const script=document.createElement('script');script.type='module';script.textContent=code;document.body.append(script);}
})();
