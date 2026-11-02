import sys,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'app/tests'))
import smoke_amplitude_proxy as base
base.OUT=Path(__file__).resolve().parent
base.SCRIPT=base.SCRIPT.replace('<button id="testInspect">','<button id="testS09_3600">S09 3600</button><button id="testInspect">')
base.SCRIPT=base.SCRIPT.replace("['testAll','S09',1800,true]", "['testAll','S09',1800,true],['testS09_3600','S09',3600,false]")
base.SCRIPT=base.SCRIPT.replace('const state={scene:', "const state={history:window.__ui.store.get('risk').history??false,risk:window.__ui.layers.find(l=>l.constructor.id==='risk').diagnostics(),scene:")
if __name__=='__main__':
 servers=[base.ThreadingHTTPServer(('127.0.0.1',port),base.Handler) for port in (8794,8795)]
 for server in servers:threading.Thread(target=server.serve_forever,daemon=True).start()
 threading.Event().wait()
