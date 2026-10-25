"""Read-only preview of the preserved CAD viewer and its saved state."""
import argparse
import hashlib
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('project', type=Path)
    parser.add_argument('--port', type=int, default=8778)
    args = parser.parse_args()
    project = args.project.resolve()
    job = 'd018b4bb75da4475b1fd75447603c1a0'
    folder = project / 'work' / 'cad-ui-test-data' / job
    assets = project / 'work' / 'cad-web' / 'local-resources' / 'cad-assets'
    model = folder / 'cad-output'
    assert (model / 'model.html').is_file() and assets.is_dir()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = unquote(urlsplit(self.path).path)
            prefix = '/cad-result/' + job + '/'
            if path == '/':
                self.send_response(302)
                self.send_header('Location', prefix + 'model.html')
                self.end_headers()
                return
            if path == prefix + 'legacy-context.json':
                manifest = json.loads((folder / 'files.json').read_text('utf-8'))
                digest = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
                state = folder / 'cad-ui-state.json'
                return self.send_json(dict(jobId=job, buildingId=digest,
                    state=json.loads(state.read_text('utf-8')) if state.exists() else None))
            if path == '/api/jobs/' + job + '/hydraulics':
                saved = folder / 'hydraulics.json'
                return self.send_json(json.loads(saved.read_text('utf-8')) if saved.exists() else None)
            if path.startswith(prefix):
                root, rel = model, path[len(prefix):]
            elif path.startswith('/cad-assets/'):
                root, rel = assets, path[len('/cad-assets/'):]
            else:
                return self.send_error(404)
            target = (root / rel).resolve()
            if not target.is_relative_to(root.resolve()) or not target.is_file():
                return self.send_error(404)
            allowed = {'.html', '.js', '.json', '.svg', '.png', '.css'}
            if target.suffix.lower() not in allowed:
                return self.send_error(404)
            mime = {'.js': 'text/javascript', '.html': 'text/html; charset=utf-8',
                    '.json': 'application/json; charset=utf-8'}.get(target.suffix)
            data = target.read_bytes()
            if target == model / 'model.html':
                # Presentation only: the preserved file is never changed.
                data += '''<style>
                #previewMenus{display:none}
                @media(max-width:650px){
                  body:not(.previewMenusOpen) #legacyTools,
                  body:not(.previewMenusOpen) #p{display:none!important}
                  body:not(.previewMenusOpen) #v{left:0!important;right:0!important}
                  #previewMenus{display:block;position:fixed;bottom:12px;left:12px;
                    z-index:9999;padding:9px 14px;background:#19394d;color:white;
                    border:1px solid #7b99ad;border-radius:5px;cursor:pointer}
                }</style><button id="previewMenus" type="button" aria-pressed="false">설정 메뉴</button>
                <script>document.getElementById('previewMenus').onclick=function(){
                  const on=document.body.classList.toggle('previewMenusOpen');
                  this.setAttribute('aria-pressed',String(on));
                  this.textContent=on?'3D로 돌아가기':'설정 메뉴';
                  window.dispatchEvent(new Event('resize'));
                };</script>'''.encode('utf-8')
            self.send_data(data, mime or mimetypes.guess_type(target.name)[0])

        def send_json(self, value):
            self.send_data(json.dumps(value, ensure_ascii=False).encode(), 'application/json; charset=utf-8')

        def send_data(self, data, mime):
            self.send_response(200)
            self.send_header('Content-Type', mime or 'application/octet-stream')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_):
            pass

    print(f'http://127.0.0.1:{args.port}{"/cad-result/" + job + "/model.html"}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
