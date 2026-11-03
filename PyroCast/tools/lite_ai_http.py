"""Same-origin loopback-only assistant HTTP boundary shared by both viewers."""
import json
from lite_ai_tools import Tools
service=Tools()

def handle(handler,path):
    def send(value,code=200):
        data=json.dumps(value,ensure_ascii=False,allow_nan=False).encode()
        handler.send_response(code);handler.send_header('Content-Type','application/json; charset=utf-8');handler.send_header('Cache-Control','no-store');handler.send_header('Content-Length',str(len(data)));handler.end_headers();handler.wfile.write(data)
    if handler.client_address[0]!='127.0.0.1' or handler.headers.get('Origin') not in (None,'http://'+handler.headers.get('Host','')):return send({'error':'외부 요청 차단'},403)
    try:
        size=int(handler.headers.get('Content-Length','0'))
        if not 0<size<=100000:raise ValueError('요청 크기 오류')
        args=json.loads(handler.rfile.read(size))
        return send(service.call(path.rsplit('/',1)[-1],args))
    except (ValueError,KeyError,TypeError):return send({'error':'도구 요청 또는 저장 데이터 오류 · 미평가'},400)
    except Exception:return send({'error':'도구 처리 실패 · 미평가'},500)
