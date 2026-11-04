"""Loopback-only model library. Exact resource routes; no execution or directory serving."""
import argparse,gzip,json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit
from model_library import ROOT,entries,model_path,catalog
ASSETS=ROOT/'cad-project/work/cad-web/local-resources/cad-assets'
if not ASSETS.is_dir():
 ASSETS=ROOT/'simulation/results/github-publish-20261026/PyroCast/cad-project/work/cad-web/local-resources/cad-assets'
FILES={
 '/models/':(ROOT/'app/model-library/index.html','text/html; charset=utf-8'),
 '/models/viewer.js':(ROOT/'app/model-library/viewer.js','text/javascript; charset=utf-8'),
 '/app/web/panels/model_review.js':(ROOT/'app/web/panels/model_review.js','text/javascript; charset=utf-8'),
 '/vendor/three.module.js':(ASSETS/'three.module.js','text/javascript'),
 '/vendor/OrbitControls.js':(ASSETS/'addons/controls/OrbitControls.js','text/javascript')}
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
  if path in FILES:
   p,mime=FILES[path];return self.send(p.read_bytes(),mime)
  for e in entries():
   if path=='/models/'+e['id']+'/building.json':return self.send(model_path(e).read_bytes())
  return self.json({'error':'Not found'},404)
 def do_POST(self):
  # This host never dispatches work, even if UI controls are bypassed.
  return self.json({'error':'모델 목록은 열람 전용입니다. 스캔 모델은 개구부 미검증으로 시뮬레이션 금지.','simulation_started':False},403)
 def do_PUT(self):return self.do_POST()
 def do_DELETE(self):return self.do_POST()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8841);a=p.parse_args()
 ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()
