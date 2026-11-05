const $=id=>document.getElementById(id);
const parentOrigin=(()=>{try{return new URL(document.referrer).origin;}catch{return location.origin;}})();
let busy=false;
async function api(body){const r=await fetch('/models/ai/connection',body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{}),v=await r.json();if(!r.ok)throw Error(v.error||'연결 실패');return v;}
function render(v){$('status').textContent=v.connected?`연결됨 · ${v.model}`:'연결 안 됨';$('disconnect').disabled=!v.connected;if(v.connected){$('url').value=v.base_url;$('model').value=v.model;}window.parent.postMessage({type:'pyrocast:ai-connection',connected:v.connected,model:v.model},parentOrigin);}
$('form').onsubmit=async e=>{e.preventDefault();if(busy)return;busy=true;$('connect').disabled=true;$('disconnect').disabled=true;$('status').textContent='API 연결 확인 중…';const body={action:'connect',base_url:$('url').value,model:$('model').value,api_key:$('key').value};$('key').value='';try{render(await api(body));}catch(e){$('status').textContent=e.message;try{const v=await api();$('disconnect').disabled=!v.connected;}catch{}}finally{body.api_key='';busy=false;$('connect').disabled=false;}};
$('disconnect').onclick=async()=>{if(busy)return;busy=true;$('connect').disabled=true;try{render(await api({action:'disconnect'}));}catch(e){$('status').textContent=e.message;}finally{busy=false;$('connect').disabled=false;}};
window.addEventListener('pagehide',()=>$('key').value='');
try{render(await api());}catch(e){$('status').textContent=e.message;}
