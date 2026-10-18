from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote,urlparse
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'outputs/CAD-가연물묶음-v30'
class Handler(SimpleHTTPRequestHandler):
 def translate_path(self,path):
  path=unquote(urlparse(path).path)
  base=ROOT/'work/cad-web/local-resources' if path.startswith('/cad-assets/') else OUT
  resolved=(base/path.lstrip('/')).resolve()
  if not resolved.is_relative_to(base.resolve()):return str(OUT/'missing')
  return str(resolved)
 def end_headers(self):
  self.send_header('Cache-Control','no-store');super().end_headers()
 def log_message(self,*args):pass
ThreadingHTTPServer(('127.0.0.1',8830),Handler).serve_forever()
