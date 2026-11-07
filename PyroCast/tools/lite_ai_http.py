"""Same-origin loopback-only assistant HTTP boundary shared by both viewers."""
import json
from lite_ai_tools import Tools
service=Tools()

def handle(handler,path,tool_service=None):
    service=tool_service or globals()['service']
    def send(value,code=200):
        data=json.dumps(value,ensure_ascii=False,allow_nan=False).encode()
        handler.send_response(code);handler.send_header('Content-Type','application/json; charset=utf-8');handler.send_header('Cache-Control','no-store');handler.send_header('Content-Length',str(len(data)));handler.end_headers();handler.wfile.write(data)
    host=handler.headers.get('Host','')
    if handler.client_address[0]!='127.0.0.1' or host not in ('127.0.0.1:'+str(handler.server.server_port),'localhost:'+str(handler.server.server_port)) or handler.headers.get('Origin') not in (None,'http://'+host):return send({'error':'외부 요청 차단'},403)
    try:
        size=int(handler.headers.get('Content-Length','0'))
        if not 0<size<=100000:raise ValueError('요청 크기 오류')
        args=json.loads(handler.rfile.read(size))
        if path.startswith('/cfbt/lite/ai/tools/'):return send(service.call(path.rsplit('/',1)[-1],args))
        from lite_ai_briefing import briefing,save_report,list_reports
        if path.endswith('/reports/list'):return send({'reports':list_reports(service,args['context'])})
        if path.endswith('/reports/save'):return send(save_report(service,args['briefing_id']))
        if path.endswith('/saved-summary'):
            from saved_briefings import for_case
            return send(for_case(service,args['context']))
        if path.endswith('/briefing'):return send(briefing(service,args['context']))
        if path.endswith('/chat'):
            from lite_ai_chat import chat
            return send(chat(service,args))
        return send({'error':'지원하지 않는 요청'},404)
    except (ValueError,KeyError,TypeError) as e:
        # Only fixed application errors; never provider payloads or credentials.
        message='API 미설정 — config/ai.json' if str(e)=='API 미설정 — config/ai.json' else '도구 요청 또는 저장 데이터 오류 · 미평가'
        return send({'error':message},400)
    except Exception:return send({'error':'도구 처리 실패 · 미평가'},500)
