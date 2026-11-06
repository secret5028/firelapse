"""Serve the exported HTML locally; no third-party Python packages required."""
from pathlib import Path
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import argparse

def main():
    p=argparse.ArgumentParser(); p.add_argument('--port',type=int,default=8831)
    args=p.parse_args()
    if not (Path(__file__).parent/'preview').is_dir():
        print('이전 HTML 증거는 archive/evidence-20261106 보존 브랜치에 있습니다. 현재 앱은 python PyroCast/start_viewer.py로 실행하세요.')
        return
    handler=partial(SimpleHTTPRequestHandler,directory=str(Path(__file__).parent/'preview'))
    with ThreadingHTTPServer(('127.0.0.1',args.port),handler) as server:
        print(f'Open http://127.0.0.1:{args.port} (Ctrl+C to stop)',flush=True)
        try: server.serve_forever()
        except KeyboardInterrupt: pass

if __name__=='__main__': main()
