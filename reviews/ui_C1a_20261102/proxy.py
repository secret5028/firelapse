"""Read-only before/after visual fixture; operated through browser UI controls.

Serves two local test pages, proxies GETs only, freezes animation at 180000 ms.
No production server edits, engine execution or POST is allowed.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen
import threading

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
CACHE = {}
LOCK = threading.Lock()

SCRIPT = r'''
const testControls=document.createElement('div');testControls.id='smokeTest';
testControls.style.cssText='position:fixed;z-index:9999;left:0;top:0px;background:#163244;color:white;padding:4px';
testControls.innerHTML='<button id="testS09_1420">S09 1420</button><button id="testS09_1800">S09 1800</button><button id="testS06_890">S06 890</button><button id="testAll">전체 코어</button><button id="testS09_0">S09 0</button><button id="testInspect">검사</button><span id="testStatus">준비</span><pre id="testReport" hidden></pre><a id="testPng" hidden>PNG</a>';
document.body.append(testControls);
const fixtureStyle=document.createElement('style');fixtureStyle.textContent='body #v,body.pyroShell #v{position:fixed!important;left:0!important;top:50px!important;right:auto!important;bottom:auto!important;width:595px!important;height:700px!important}';document.head.append(fixtureStyle);
const settle=async()=>{await document.fonts.ready;for(let i=0;i<5;i++)await new Promise(requestAnimationFrame);};
const inspect=()=>{
 window.__ui.render();const smoke=[],other=[];window.__cad.S.traverse(o=>{const u=o.material?.uniforms;if(!u?.uTemperatureSmoke)return;
 const row={visible:o.visible,temp:u.uLayerTemp.value,amp:u.uNoiseAmp?.value??1,scale:u.uNoiseScale?.value??1,ramp:u.uRampMode?.value??0,temperature:u.uTemperatureSmoke.value,od:u.uOD.value};
 (u.uFire.value===0&&u.uGas.value===0?smoke:other).push(row);});
 const state={history:window.__ui.store.get('risk').history,risk:window.__ui.layers.find(l=>l.constructor.id==='risk').diagnostics(),worst:document.getElementById('resultWorstTime')?.textContent,scene:window.__testScene,clock_ms:180000,case:document.getElementById('liteCase').value,room:document.getElementById('liteRoom').value,time:window.__ui.store.get('playback').t_s,mode:document.getElementById('displayTemperature').value,ramp:document.getElementById('displaySmokeColor')?.value??'current',smoke,other,hud:document.querySelector('.compactHUD').textContent,camera:window.__cad.C.position.toArray()};
 document.getElementById('testReport').textContent=JSON.stringify(state);document.getElementById('testPng').href=window.__cad.R.domElement.toDataURL('image/png');return state;
};
document.getElementById('testInspect').onclick=()=>{inspect();document.getElementById('testStatus').textContent='검사 완료';};
async function scene(id,time,all=false){try{
 document.getElementById('testStatus').textContent='불러오는 중';const $=id=>document.getElementById(id);
 if($('liteCase').value!==id){$('liteCase').value=id;await $('liteCase').onchange();}
 $('reviewClose')?.click();$('liteRoom').value='CAD_3F_R2_C0';$('liteRoom').onchange();
 $('liteTime').value=time;$('liteTime').oninput();$('liteCores').checked=true;$('liteCores').onchange();
 if(all)$('liteBuilding').click();else{[...$('fbtn').children].find(b=>b.textContent==='3F').click();$('liteWhole').click();$('iso').click();}
 window.__ui.store.dispatch('risk/history',{enabled:false});$('shellTab-display').click();await settle();window.__testScene=all?'all-core':id+'-'+time;inspect();$('testStatus').textContent='완료 '+window.__testScene;
 }catch(e){document.getElementById('testStatus').textContent='실패 '+e.message;}}
for(const [button,id,time,all] of [['testS09_1420','S09',1420,false],['testS09_1800','S09',1800,false],['testS06_890','S06',890,false],['testAll','S09',1800,true],['testS09_0','S09',0,false]])document.getElementById(button).onclick=()=>scene(id,time,all);
await settle();document.getElementById('testStatus').textContent='준비 완료';
'''


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_POST(self): self.send_error(405)
    def do_GET(self):
        try:
            path = self.path
            before = self.server.server_port == 8814
            names = {'/cfbt/overlay.js':'before-overlay.js',
                     '/cfbt/legacy_real_view.js':'before-legacy_real_view.js',
                     '/cfbt/legacy_real_bridge.js':'before-legacy_real_bridge.js'}
            if before and path.split('?')[0] in names:
                data = (OUT/names[path.split('?')[0]]).read_bytes(); mime='text/javascript'
            elif not before and path.split('?')[0] in names:
                data = (ROOT/'simulation/viewer'/path.split('?')[0].rsplit('/',1)[1]).read_bytes(); mime='text/javascript'
            else:
                remote = '/cfbt/lite/result/S09' if path=='/cfbt/lite/active.json' else path
                with LOCK:
                    if remote not in CACHE:
                        with urlopen('http://127.0.0.1:8780'+remote, timeout=90) as r:
                            CACHE[remote]=(r.read(), r.headers.get('Content-Type','application/octet-stream'))
                    data,mime=CACHE[remote]
            if path.split('?')[0].endswith('/model.html'):
                h=data.decode();hook='await (await import("/cfbt/overlay.js")).attach({'
                i=h.index(hook);j=h.index('\n</script>',i);old=h[i:j]
                arg=old[len(hook)-1:old.rfind(');')]
                h=h[:i]+'window.__cad='+arg+';window.__ui=await (await import("/cfbt/overlay.js")).attach(window.__cad);'+SCRIPT+h[j:]
                freeze='<script>performance.now=()=>180000;const nativeRAF=requestAnimationFrame;window.requestAnimationFrame=cb=>nativeRAF(()=>cb(180000));</script>'
                h=freeze+h;data=h.encode()
            self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
        except Exception as exc:
            self.send_error(500,str(exc))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output-root',type=Path,default=OUT)
    OUT=parser.parse_args().output_root.resolve()
    servers=[ThreadingHTTPServer(('127.0.0.1',port),Handler) for port in (8814,8815)]
    for server in servers:threading.Thread(target=server.serve_forever,daemon=True).start()
    print('Before8814 / After8815; GET-only; no simulation',flush=True)
    threading.Event().wait()
