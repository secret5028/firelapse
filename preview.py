"""Serve the exported HTML locally; no third-party Python packages required."""
from pathlib import Path
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import argparse

def main():
    p=argparse.ArgumentParser(); p.add_argument('--port',type=int,default=8831)
    args=p.parse_args()
    handler=partial(SimpleHTTPRequestHandler,directory=str(Path(__file__).parent/'preview'))
    with ThreadingHTTPServer(('127.0.0.1',args.port),handler) as server:
        print(f'Open http://127.0.0.1:{args.port} (Ctrl+C to stop)',flush=True)
        try: server.serve_forever()
        except KeyboardInterrupt: pass

if __name__=='__main__': main()
