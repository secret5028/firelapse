"""Local GET-only preview server. No execution API or simulation dependency."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse

ROOT=Path(__file__).resolve().parents[1]


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/vendor/three.module.js':
            paths=[ROOT/'cad-project/work/cad-web/local-resources/cad-assets/three.module.js',
                   ROOT/'simulation/results/github-publish-20261026/PyroCast/cad-project/work/cad-web/local-resources/cad-assets/three.module.js']
            src=next((p for p in paths if p.exists()),None)
            if src is None:return self.send_error(404,'Bundled Three.js missing')
            data=src.read_bytes();self.send_response(200);self.send_header('Content-Type','text/javascript');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
        if not self.path.startswith(('/data/wando-coldstore/','/app/web/')):
            return self.send_error(404)
        return super().do_GET()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8831);args=parser.parse_args()
    print(f'http://127.0.0.1:{args.port}/data/wando-coldstore/preview.html',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),partial(Handler,directory=str(ROOT))).serve_forever()
