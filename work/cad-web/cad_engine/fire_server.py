# -*- coding: utf-8 -*-
"""경량 해석 로컬 서버 — 뷰어에서 화점을 찍으면 바로 해석

python fire_server.py <건물 출력 폴더(building.json 있는 곳)> [--port 8765] [--procs 2] [--mc 4F_fire_mc.json]
브라우저: http://localhost:8765
  POST /api/run  {floor, point:[x,y], doors:{id:%}, windows:{id:%}, t_end?, T_break?}  → 단일 해석 결과
  POST /api/mc   {floor, point:[x,y], n}  → 몬테카를로 시작(백그라운드),  GET /api/mc → 진행·결과
로컬(127.0.0.1)에서만 듣는다.
"""
import json, os, sys, threading, argparse, traceback
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fire_zone as fz
import fire_mc

ROOT = os.path.dirname(os.path.abspath(__file__))
STATE = dict(mc=None)


def page(B, mc):
    html = open(os.path.join(ROOT, 'viewer_template.html'), encoding='utf-8').read()
    return (html.replace('/*__DATA__*/null', json.dumps(B, ensure_ascii=False))
                .replace('/*__FIRE__*/null', json.dumps(mc, ensure_ascii=False) if mc else 'null')
                .replace('/*__LIVE__*/false', 'true'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dir'); ap.add_argument('--port', type=int, default=8765); ap.add_argument('--procs', type=int, default=2)
    ap.add_argument('--mc', help='미리 계산한 몬테카를로 결과 json(선택)')
    ap.add_argument('--t', type=float, default=1200, help='단일 해석 시간 s')
    a = ap.parse_args()
    bpath = os.path.join(a.dir, 'building.json')
    B = json.load(open(bpath, encoding='utf-8'))
    mc0 = json.load(open(a.mc, encoding='utf-8')) if a.mc else None
    if mc0: mc0.pop('runs', None)

    class H(BaseHTTPRequestHandler):
        def log_message(self, *x): pass
        def send(self, code, body, ctype='application/json; charset=utf-8'):
            b = body.encode('utf-8') if isinstance(body, str) else body
            self.send_response(code); self.send_header('Content-Type', ctype); self.send_header('Content-Length', str(len(b)))
            self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(b)
        def jsend(self, o, code=200): self.send(code, json.dumps(o, ensure_ascii=False))
        def body(self):
            n = int(self.headers.get('Content-Length') or 0)
            return json.loads(self.rfile.read(n) or b'{}')

        def do_GET(self):
            if self.path in ('/', '/index.html'):
                return self.send(200, page(B, STATE['mc'] and STATE['mc'].get('result') or mc0), 'text/html; charset=utf-8')
            if self.path == '/api/mc':
                s = STATE['mc'] or {}
                return self.jsend({k: v for k, v in s.items() if k != 'thread'} if s else dict(error='실행 중인 몬테카를로 없음'))
            self.send(404, 'not found', 'text/plain')

        def do_POST(self):
            try:
                q = self.body()
                if self.path == '/api/run':
                    sc = dict(fire_point=q['point'], doors=q.get('doors', {}), windows=q.get('windows', {}),
                              T_break=q.get('T_break', 400))
                    M = fz.Model(B, q['floor'], sc); M.run(q.get('t_end', a.t), 10); R = M.result(); R.pop('flags')
                    R['floor'] = q['floor']
                    print(f"해석 {q['floor']} {q['point']} → {R['fire']['room']} {R['fire']['label']} 최대 {max(R['HRR_kW']):.0f}kW", flush=True)
                    return self.jsend(R)
                if self.path == '/api/mc':
                    if STATE['mc'] and not STATE['mc'].get('done') and not STATE['mc'].get('error'):
                        return self.jsend(dict(error='이미 실행 중'))
                    cfg = dict(fire_mc.DEF); cfg.update(n=int(q.get('n', 40)))
                    st = dict(done=False, k=0, n=cfg['n'])
                    def job():
                        try:
                            st['result'] = fire_mc.run(bpath, q['floor'], cfg, None, a.procs, q['point'], B=B,
                                                       progress=lambda k, n: st.update(k=k))
                            st['result'].pop('runs', None); st['done'] = True
                        except Exception as e:
                            traceback.print_exc(); st['error'] = str(e)
                    STATE['mc'] = st; threading.Thread(target=job, daemon=True).start()
                    return self.jsend(dict(started=True, n=cfg['n']))
                self.send(404, 'not found', 'text/plain')
            except Exception as e:
                traceback.print_exc(); self.jsend(dict(error=str(e)), 400)

    srv = ThreadingHTTPServer(('127.0.0.1', a.port), H)
    print(f'경량 해석 서버: http://localhost:{a.port}  (Ctrl+C 종료)', flush=True)
    srv.serve_forever()


if __name__ == '__main__':
    main()
