"""Read-only verification view; no registration or simulation endpoints."""
from pathlib import Path
import sys,json,argparse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit
ROOT=Path(r'C:/Users/예방/Documents/ChatGPT/PyroCast')
sys.path.insert(0,str(ROOT/'tools'))
from serve_model_library import FILES
p=argparse.ArgumentParser();p.add_argument('--work',required=True);p.add_argument('--port',type=int,default=8848);args=p.parse_args()
work=Path(args.work).resolve();base=ROOT/'reviews/cad-ai-validation-20261106'
if not work.is_relative_to(base.resolve()):raise SystemExit('Unexpected preview path')
class Preview(BaseHTTPRequestHandler):
 def send(self,data,mime='application/json; charset=utf-8',status=200):
  self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
 def do_GET(self):
  path=urlsplit(self.path).path
  if path=='/':path='/models/'
  if path=='/models/catalog.json':
   b=json.loads((work/'building.json').read_text('utf8'));v=b['cad_completion']
   row=dict(id='cad-verification',label='새 CAD · API 보정 검증',model_url='/verification/building.json',source_kind='cad',floor_count=len(b['floors']),room_count=sum(len(f['rooms']) for f in b['floors']),simulation_enabled=False,execution_note='검증 전용 · 미확인 연결 확인 필요',source_evidence='API '+v['ai_status']+' · 호출 '+str(v['ai_calls'])+'회',operation_url=None,review_url=None)
   return self.send(json.dumps({'models':[row]},ensure_ascii=False).encode())
  if path=='/verification/building.json':return self.send((work/'building.json').read_bytes())
  if path in ('/source-1F.png','/source-2F.png'):return self.send((work/path[1:]).read_bytes(),'image/png')
  if path in ('/models/','/models/viewer.js','/app/web/panels/model_review.js','/vendor/three.module.js','/vendor/OrbitControls.js'):
   file,mime=FILES[path];return self.send(file.read_bytes(),mime)
  return self.send(b'not found','text/plain',404)
 def do_POST(self):self.send(b'read only','text/plain',405)
ThreadingHTTPServer(('127.0.0.1',args.port),Preview).serve_forever()
