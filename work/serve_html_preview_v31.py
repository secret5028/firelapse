from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote, urlparse
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT/'outputs/CAD-HTML내보내기-v31'
class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        path = unquote(urlparse(path).path)
        base = ROOT/'work/cad-web/local-resources' if path.startswith('/cad-assets/') else OUT
        resolved = (base/path.lstrip('/')).resolve()
        return str(resolved if resolved.is_relative_to(base.resolve()) else OUT/'missing')
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()
    def log_message(self, *args): pass
ThreadingHTTPServer(('127.0.0.1', 8831), Handler).serve_forever()
