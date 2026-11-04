"""Local CAD review preview, exact GET allowlist; no directory/file browsing."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import argparse
ROOT=Path(__file__).resolve().parents[1]
FILES={
 '/data/parkmarine-hotel/review.html':('data/parkmarine-hotel/review.html','text/html; charset=utf-8'),
 '/data/parkmarine-hotel/review.js':('data/parkmarine-hotel/review.js','text/javascript; charset=utf-8'),
 '/data/parkmarine-hotel/building.json':('data/parkmarine-hotel/building.json','application/json; charset=utf-8'),
 '/app/web/panels/model_review.js':('app/web/panels/model_review.js','text/javascript; charset=utf-8'),
 '/vendor/three.module.js':('simulation/results/github-publish-20261026/PyroCast/cad-project/work/cad-web/local-resources/cad-assets/three.module.js','text/javascript; charset=utf-8')}
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  entry=FILES.get(urlsplit(self.path).path)
  if not entry:return self.send_error(404)
  data=(ROOT/entry[0]).read_bytes();self.send_response(200)
  self.send_header('Content-Type',entry[1]);self.send_header('Content-Length',str(len(data)))
  self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(data)
 def do_POST(self):self.send_error(405)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8840);a=p.parse_args()
 ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()
