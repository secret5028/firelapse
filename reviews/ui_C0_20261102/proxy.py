import sys,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'app/tests'))
import flame_hrr_proxy as fixture
base=fixture.base
base.OUT=Path(__file__).resolve().parent
base.SCRIPT=base.SCRIPT.replace('visible:o.visible,scale:o.scale.toArray()', 'visible:o.visible,footprint:o.userData.maskFootprint??null,uSize:o.material.uniforms.uSize.value.toArray(),maskScale:o.material.uniforms.uMaskScale.value.toArray(),scale:o.scale.toArray()')
if __name__=='__main__':
 servers=[base.ThreadingHTTPServer(('127.0.0.1',port),base.Handler) for port in (8794,8795)]
 for server in servers:threading.Thread(target=server.serve_forever,daemon=True).start()
 print('C0 GET-only before8794 after8795',flush=True);threading.Event().wait()
