"""Test-only mock provider. No API credentials or real provider calls."""
import sys,json,threading
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
import ai_connection,serve_model_library
class Provider(BaseHTTPRequestHandler):
 def do_POST(self):
  body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
  self.send_response(401 if body['model']=='reject' else 200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps({'choices':[{'message':{'content':'OK'}}]}).encode())
 def log_message(self,*args):pass
ai_connection.HOSTING=True
provider=ThreadingHTTPServer(('127.0.0.1',8867),Provider)
threading.Thread(target=provider.serve_forever,daemon=True).start()
ThreadingHTTPServer(('127.0.0.1',8866),serve_model_library.Handler).serve_forever()
