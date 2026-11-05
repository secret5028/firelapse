"""Loopback AI connection broker. Credentials live only in this process."""
import json, re, threading
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

HOSTING = False
URL = 'http://127.0.0.1:8841/models/ai'
_session = None
_lock = threading.RLock()

def public_status():
    with _lock:
        s = _session
        return dict(connected=bool(s), base_url=s['base_url'] if s else '', model=s['model'] if s else '', storage='server_memory')

def connect(body, transport=None):
    global _session
    if not isinstance(body,dict) or set(body)!={'action','base_url','model','api_key'}:
        raise ValueError('API 주소·모델·키를 입력하세요')
    base,model,key=(body[k] for k in ('base_url','model','api_key'))
    if not all(isinstance(v,str) and v.strip() for v in (base,model,key)) or len(base)>500 or len(model)>150 or len(key)>4096:
        raise ValueError('API 입력 형식 오류')
    base,model,key=base.strip().rstrip('/'),model.strip(),key.strip()
    u=urlsplit(base)
    if not u.hostname or u.username or u.password or u.query or u.fragment or (u.scheme!='https' and not (u.scheme=='http' and u.hostname in ('127.0.0.1','localhost','::1'))):
        raise ValueError('API 주소는 HTTPS 또는 로컬 HTTP 주소를 입력하세요')
    if any(ord(c)<32 for c in base+model+key):raise ValueError('API 입력 형식 오류')
    cfg=dict(base_url=base,model=model,api_key_env='PYROCAST_AI_KEY')
    if transport is None:
        from lite_ai_fuel import completion
        transport=completion
    # Commit only after one small real provider request succeeds.
    try:
        result=transport({**cfg,'_probe':True},key,[dict(role='user',content='Reply OK.')])
        if not isinstance(result,str) or not result.strip() or key in result:raise ValueError('response')
    except Exception:raise ValueError('연결 실패 — API 주소·모델·키와 사용 한도를 확인하세요') from None
    with _lock:_session={**cfg,'key':key}
    return public_status()

def disconnect():
    global _session
    with _lock:_session=None
    return public_status()

def complete(messages):
    with _lock:s=dict(_session) if _session else None
    if not s:raise ValueError('AI 연결이 해제되었습니다')
    if not isinstance(messages,list) or not 1<=len(messages)<=100 or any(not isinstance(m,dict) or m.get('role') not in ('system','user','assistant') or not isinstance(m.get('content'),(str,list)) for m in messages):
        raise ValueError('AI 메시지 형식 오류')
    from lite_ai_fuel import completion
    value=completion({k:v for k,v in s.items() if k!='key'},s['key'],messages)
    if not isinstance(value,str) or s['key'] in value:raise ValueError('AI 응답 형식 오류')
    return value

def remote(path='',body=None):
    data=None if body is None else json.dumps(body,ensure_ascii=False).encode()
    req=Request(URL+path,data=data,headers={'Content-Type':'application/json'})
    try:
        with urlopen(req,timeout=100 if body else .6) as r:return json.loads(r.read(2_000_001))
    except Exception:raise ValueError('AI 연결 서버에 접속할 수 없습니다') from None

def runtime_settings():
    try:s=public_status() if HOSTING else remote('/connection')
    except ValueError:return None
    return {**s,'_runtime':True,'api_key_env':'PYROCAST_AI_KEY'} if s.get('connected') else None

def runtime_completion(messages):
    return complete(messages) if HOSTING else remote('/completion',{'messages':messages})['text']

def handle(handler,path):
    # No keys in GET, responses, log messages, disk, or environment variables.
    host=handler.headers.get('Host','')
    if handler.client_address[0]!='127.0.0.1' or host not in ('127.0.0.1:'+str(handler.server.server_port),'localhost:'+str(handler.server.server_port)) or handler.headers.get('Origin') not in (None,'http://'+host):
        return handler.json({'error':'외부 요청 차단'},403)
    try:
        if handler.command=='GET' and path.endswith('/connection'):return handler.json(public_status())
        size=int(handler.headers.get('Content-Length','0'))
        if not 0<size<=(25_000_000 if path.endswith('/completion') else 8192):raise ValueError('요청 크기 오류')
        if handler.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('JSON 요청이 필요합니다')
        body=json.loads(handler.rfile.read(size))
        if not isinstance(body,dict):raise ValueError('요청 형식 오류')
        if path.endswith('/completion'):return handler.json({'text':complete(body.get('messages'))})
        if body.get('action')=='disconnect':return handler.json(disconnect())
        if body.get('action')=='connect':return handler.json(connect(body))
        raise ValueError('지원하지 않는 동작')
    except Exception as exc:
        message=str(exc) if isinstance(exc,ValueError) and not isinstance(exc,json.JSONDecodeError) else 'AI 요청 처리 실패'
        return handler.json({'error':message},400)
