"""GET-only visual fixture. No computations/POST; UI buttons drive production controls."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen
import threading
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
SCRIPT=r'''
const controls=document.createElement('div');controls.id='d1Fixture';controls.style.cssText='position:fixed;top:0;left:0;z-index:99999;background:#163244;color:white';
controls.innerHTML='<button id="test1420">S09 1420</button><button id="test1800">S09 1800</button><button id="test890">S06 890</button><button id="testAll">전체</button><button id="testWando">P1 2100</button><button id="testInspect">검사</button><span id="testStatus">준비</span><pre id="testReport" hidden></pre><a id="testPng" hidden>PNG</a>';
document.body.append(controls);
const settle=async()=>{await document.fonts.ready;for(let i=0;i<5;i++)await new Promise(requestAnimationFrame);};
function inspect(){const ui=window.__ui,cad=window.__cad,$=id=>document.getElementById(id);ui.render();const smoke=[];cad.S.traverse(o=>{const u=o.material?.uniforms;if(u?.uTemperatureSmoke&&u.uFire.value===0&&u.uGas.value===0)smoke.push({name:o.name,visible:o.visible,position:o.position.toArray(),scale:o.scale.toArray(),od:u.uOD.value,temp:u.uLayerTemp.value,opacity:u.uOpacity?.value,amp:u.uNoiseAmp?.value});});
const risk=ui.layers.find(l=>l.constructor.id==='risk');const report={scene:window.__scene,clock_ms:180000,case:$('liteCase').value,time:ui.store.get('playback').t_s,room:$('liteRoom').value,state:Object.fromEntries(['layers','realView','openings','risk','route',...($('displayCellOutline')?['displayDetails']:[])].map(k=>[k,ui.store.get(k)])),risk:risk.diagnostics(),detailMasks:risk.views.map(v=>({id:v.id,line:v.line.layers.mask,tint:v.tint.layers.mask,interface:v.interfaceLine.layers.mask})),hud:document.querySelector('.compactHUD').innerText,legend:$('cfMeaning').innerText,plumeLegend:!!$('cfPlumeLegend'),smoke,checks:[...document.querySelectorAll('#shellPane-display input[type=checkbox]')].map(x=>({id:x.id,checked:x.checked})),calls:cad.R.info.render.calls};
$('testReport').textContent=JSON.stringify(report);$('testPng').href=cad.R.domElement.toDataURL('image/png');return report;}
async function scene(id,t,all=false,wando=false){try{const $=id=>document.getElementById(id);$('testStatus').textContent='불러오는 중';if($('liteCase').value!==id){$('liteCase').value=id;await $('liteCase').onchange();}const wanted=wando?'CAD_1F_R5':'CAD_3F_R2_C0';if([...$('liteRoom').options].some(o=>o.value===wanted)){$('liteRoom').value=wanted;$('liteRoom').onchange();}$('liteTime').value=t;$('liteTime').oninput();$('reviewClose')?.click();if(all)$('liteBuilding').click();else if(wando){$('floor1').click();$('iso').click();}else{[...$('fbtn').children].find(b=>b.textContent==='3F').click();$('liteWhole').click();$('iso').click();}$('shellTab-result').click();await settle();window.__scene=all?'all':id+'-'+t;inspect();$('testStatus').textContent='완료 '+window.__scene;}catch(e){document.getElementById('testStatus').textContent='실패 '+e.message;}}
document.getElementById('test1420').onclick=()=>scene('S09',1420);document.getElementById('test1800').onclick=()=>scene('S09',1800);document.getElementById('test890').onclick=()=>scene('S06',890);document.getElementById('testAll').onclick=()=>scene('S09',1800,true);document.getElementById('testWando').onclick=()=>scene('wando-P1',2100,false,true);document.getElementById('testInspect').onclick=()=>{inspect();document.getElementById('testStatus').textContent='검사 완료';};
await settle();document.getElementById('testStatus').textContent='준비 완료';
'''
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_POST(self):self.send_error(405)
 def do_GET(self):
  try:
   port=self.server.server_port;wando=port in (8842,8843);before=port in (8840,8842);path=self.path.split('?')[0]
   if path=='/cfbt/overlay.js':
    data=(OUT/'before-overlay.js' if before else ROOT/'simulation/viewer/overlay.js').read_bytes();mime='text/javascript'
   elif path.endswith('/operating.js'):
    data=(OUT/'before-operating.js' if before else ROOT/'data/wando-coldstore/operating.js').read_bytes();mime='text/javascript'
   else:
    remote='/cfbt/lite/result/S09' if not wando and path=='/cfbt/lite/active.json' else self.path
    with urlopen('http://127.0.0.1:'+('8832' if wando else '8780')+remote,timeout=90) as r:data,mime=r.read(),r.headers.get('Content-Type','application/octet-stream')
   if path.endswith('/model.html'):
    h=data.decode('utf8');freeze='<script>performance.now=()=>180000;const nativeRAF=requestAnimationFrame;window.requestAnimationFrame=cb=>nativeRAF(()=>cb(180000));</script>'
    if not wando:
     hook='await (await import("/cfbt/overlay.js")).attach({';i=h.index(hook);j=h.index('\n</script>',i);old=h[i:j];arg=old[len(hook)-1:old.rfind(');')]
     h=h[:i]+'window.__cad='+arg+';window.__ui=await (await import("/cfbt/overlay.js")).attach(window.__cad);'+SCRIPT+h[j:]
    data=(freeze+h).encode('utf8')
   if path.endswith('/operating.js'):
    h=data.decode('utf8').replace('const app=await attach(viewer);','window.__cad=viewer;const app=await attach(viewer);window.__ui=app;').replace("}catch(e){$('error')",SCRIPT+"\n}catch(e){$('error')");data=h.encode('utf8')
   self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
  except Exception as e:self.send_error(500,str(e))
if __name__=='__main__':
 for port in (8840,8841,8842,8843):
  server=ThreadingHTTPServer(('127.0.0.1',port),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
 print('D1 before/after: 3F 8840/8841, Wando 8842/8843',flush=True);threading.Event().wait()
