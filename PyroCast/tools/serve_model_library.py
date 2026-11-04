"""Loopback-only model library with validated, building-scoped simulation jobs."""
import argparse,gzip,json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit,parse_qs
from model_library import ROOT,entries,model_path,catalog
ASSETS=ROOT/'cad-project/work/cad-web/local-resources/cad-assets'
if not ASSETS.is_dir():
 ASSETS=ROOT/'simulation/results/github-publish-20261026/PyroCast/cad-project/work/cad-web/local-resources/cad-assets'
FILES={
 '/models/':(ROOT/'app/model-library/index.html','text/html; charset=utf-8'),
 '/models/viewer.js':(ROOT/'app/model-library/viewer.js','text/javascript; charset=utf-8'),
 '/models/simulation.js':(ROOT/'app/model-library/simulation.js','text/javascript; charset=utf-8'),
 '/app/web/panels/model_review.js':(ROOT/'app/web/panels/model_review.js','text/javascript; charset=utf-8'),
 '/vendor/three.module.js':(ASSETS/'three.module.js','text/javascript'),
 '/vendor/OrbitControls.js':(ASSETS/'addons/controls/OrbitControls.js','text/javascript')}
for name in ('legacy_real_bridge.js','legacy_real_view.js','risk.js','gas_visual.js','smoke_visual.js'):
 FILES['/cfbt/'+name]=(ROOT/'simulation/viewer'/name,'text/javascript; charset=utf-8')
FILES['/cfbt/lite/fire-load-table']=(ROOT/'simulation/pyrocast_lite/fire_load_table.json','application/json; charset=utf-8')
class Handler(BaseHTTPRequestHandler):
 def send(self,data,mime='application/json; charset=utf-8',code=200):
  zipped=len(data)>65536 and 'gzip' in self.headers.get('Accept-Encoding','')
  if zipped:data=gzip.compress(data,compresslevel=1,mtime=0)
  self.send_response(code);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)))
  origin=self.headers.get('Origin')
  if origin in ('http://127.0.0.1:8780','http://127.0.0.1:8832','http://127.0.0.1:8840','http://127.0.0.1:8841'):self.send_header('Access-Control-Allow-Origin',origin)
  if zipped:self.send_header('Content-Encoding','gzip')
  self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(data)
 def json(self,d,code=200):return self.send(json.dumps(d,ensure_ascii=False).encode(),code=code)
 def do_GET(self):
  path=urlsplit(self.path).path
  if path=='/':path='/models/'
  if path=='/models/catalog.json':return self.json(catalog())
  if path in ('/models/simulation/capabilities','/models/simulation/status','/models/simulation/playback','/models/simulation/jobs'):
   try:
    import model_simulation as sim
    query=parse_qs(urlsplit(self.path).query);ident=query.get('building',[''])[0]
    sim.entry(ident)
    if path.endswith('/capabilities'):return self.json(sim.capabilities(ident))
    if path.endswith('/jobs'):
     folders=sorted((sim.RESULTS/ident).glob('*/status.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:50]
     return self.json({'jobs':[dict(job=p.parent.name,**{k:v for k,v in sim.read(p).items() if k!='job'},request=sim.read(p.parent/'request.json')) for p in folders]})
    folder=sim.job_path(ident,query.get('job',[''])[0])
    if path.endswith('/status'):return self.json(sim.read(folder/'status.json'))
    if sim.read(folder/'status.json')['state']!='complete':return self.json({'error':'아직 완료되지 않은 결과'},409)
    return self.send((folder/'playback.json').read_bytes())
   except (ValueError,KeyError,TypeError,OSError) as exc:return self.json({'error':str(exc)},400)
  if path in FILES:
   p,mime=FILES[path];return self.send(p.read_bytes(),mime)
  for e in entries():
   if path=='/models/'+e['id']+'/building.json':return self.send(model_path(e).read_bytes())
  return self.json({'error':'Not found'},404)
 def do_POST(self):
  if urlsplit(self.path).path=='/models/simulation/run':
   if self.headers.get('Origin') not in (None,'http://'+self.headers.get('Host','')):
    return self.json({'error':'외부 요청 차단','simulation_started':False},403)
   try:
    length=int(self.headers.get('Content-Length','0'))
    if not 0<length<=4096:raise ValueError('잘못된 요청 크기')
    body=json.loads(self.rfile.read(length))
    import model_simulation as sim
    return self.json(sim.start(body),202)
   except RuntimeError as exc:return self.json({'error':str(exc),'simulation_started':False},409)
   except (ValueError,KeyError,TypeError,OSError) as exc:return self.json({'error':str(exc),'simulation_started':False},400)
  # Legacy paths cannot accidentally dispatch a factory calculation.
  return self.json({'error':'모델 목록은 열람 전용입니다. 스캔 모델은 개구부 미검증으로 시뮬레이션 금지.','simulation_started':False},403)
 def do_PUT(self):return self.json({'error':'Method not allowed','simulation_started':False},405)
 def do_DELETE(self):return self.do_PUT()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8841);a=p.parse_args()
 ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()
