"""Production panel/scene API for one model. Reads saved jobs; never runs on GET."""
import json
import logging
import threading
from functools import lru_cache
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs
from model_library import ROOT, model_path
import model_simulation as sim

PORTS = {'parkmarine':8842, 'showroom':8843}
_servers = {}
_server_lock = threading.RLock()
_base_handler = None


def active_operation_ports():
    with _server_lock:
        return [server.server_port for server in _servers.values()]


def operation_port(row):
    return row.get('operation_port') or PORTS.get(row['id'])


def operation_url(row):
    return f"http://127.0.0.1:{operation_port(row)}/model.html"


def register_cad(row, loaders, registry):
    """Register validated floors; uncertain geometry remains explicitly inferred."""
    if row.get('source_kind') != 'cad':
        raise ValueError('스캔 모델은 계산 등록할 수 없습니다')
    row['calculation_floors'] = loaders
    row['simulation_enabled'] = any(r.get('ok') for r in loaders)
    if not row['simulation_enabled']:
        row.update(operation_url=None, execution_note='계산 가능한 층 없음 · 모델 검토 필요')
        return
    old = next((r for r in registry['models'] if r['id'] == row['id']), {})
    port = operation_port(old) if old else None
    if not port:
        import socket
        used = {operation_port(r) for r in registry['models']}
        for candidate in range(8844, 8944):
            if candidate in used: continue
            try:
                with socket.socket() as probe: probe.bind(('127.0.0.1', candidate))
            except OSError: continue
            port = candidate; break
        if not port: raise ValueError('운영 포트를 확보하지 못했습니다')
    row.update(operation_port=port, execution_mode='library_lite',
        execution_note='층별 계산 가능 · 추정 연결·층고 유지 · 수직 전파 미평가')
    row['operation_url'] = operation_url(row)


def ensure_server(row):
    if _base_handler is None: return None
    if row.get('source_kind') != 'cad' or row.get('execution_mode') != 'library_lite' or not row.get('simulation_enabled'):
        return None
    with _server_lock:
        if row['id'] in _servers: return _servers[row['id']]
        server = ThreadingHTTPServer(('127.0.0.1', operation_port(row)), handler(_base_handler, row['id']))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        _servers[row['id']] = server
        return server


def model_preview(ident):
    """Geometry for a building with no calculation; no synthetic measurements."""
    b = sim.read(model_path(sim.entry(ident))); rooms = []
    for f in b['floors']:
        for r in f.get('rooms', []):
            key = f"CAD_{f['name']}_{r['id']}"
            rooms.append(dict(key=key, original_room=key, solver_id=key, cad_floor=f['name'],
                cad_room=r['id'], cad_names=r.get('names', []), cad_polys=r['polys'],
                z_m=f['z'], height_m=f['h'], display_name=' / '.join(r.get('names', []))))
    if not rooms: raise ValueError('표시할 실 형상이 없습니다')
    return dict(schema='pyrocast-cad-playback-1',engine_kind='pyrocast_lite',model_preview=True,
        complete=False,simulation_output_complete=False,case_id='model-preview',
        building_sha256=sim.fingerprint(ident),label='계산 전 · 미평가',time_s=[0],
        fire_key=None,rooms=rooms,solvers={},fires=[],events=[],fuel_symbols=[],fuel_units=[],
        limits=b.get('notes',[])+['층별 계산 · 미확정 연결·층고는 추정값 유지 · 수직 전파 미평가'])


def active_playback(ident):
    rows = jobs(ident)
    if rows: return playback(ident, rows[0][0].name)
    import model_mc, fixed_calculation
    cases = fixed_calculation.cases(sim.fingerprint(ident)) + model_mc.cases(ident)
    return playback(ident, cases[0]['id']) if cases else model_preview(ident)


def jobs(ident, warnings=None):
    digest = sim.fingerprint(ident)
    out = []
    for p in sorted(sim.result_glob(sim.RESULTS/ident,'*/status.json'), key=lambda p:p.stat().st_mtime, reverse=True):
        try:
            status = json.loads(p.read_text('utf-8-sig'))
            if not isinstance(status, dict) or status.get('state') != 'complete': continue
            request = json.loads((p.parent/'request.json').read_text('utf-8-sig'))
            if not isinstance(request, dict): raise ValueError('Invalid saved request')
            if request.get('building_sha256') != digest: continue
            if not all(isinstance(request.get(k), str) and request[k] for k in ('floor', 'room')):
                raise ValueError('Missing saved floor or room')
            if not all((p.parent/name).is_file() for name in ('input.json', 'playback.json')):
                raise ValueError('Incomplete saved result')
        except (OSError, ValueError, TypeError) as exc:
            logging.getLogger(__name__).warning('Skipping unreadable saved case %s: %s', p.parent.name, exc)
            if warnings is not None: warnings.append(dict(case_id=p.parent.name, reason=str(exc)))
            continue
        out.append((p.parent, request))
    return out

@lru_cache(maxsize=256)
def saved_engine(path, mtime_ns):
    # Old requests omitted engine; use saved playback evidence, never its label.
    return sim.read(path).get('engine_kind')


def playback(ident, job=None):
    if job and job.startswith('calc-'):
        from fixed_calculation import playback as fixed_playback
        return fixed_playback(sim.fingerprint(ident), job)
    if job and job.startswith("modelmc-"):
        import model_mc
        return model_mc.playback(ident,job)
    rows = jobs(ident)
    row = next((r for r in rows if r[0].name == job), None) if job else next(iter(rows), None)
    if row is None: raise ValueError('이 건물의 완료된 저장 결과가 없습니다')
    value = sim.read(row[0]/'playback.json')
    if value['building_sha256'] != sim.fingerprint(ident): raise ValueError('건물 해시 불일치')
    value['case_id'] = row[0].name
    # Display the saved calculation input, never today's regenerated defaults.
    saved = sim.read(row[0]/'input.json')
    states = saved.get('screening_source', {}).get('opening_states', [])
    if (saved.get('cad', {}).get('building_sha256') == value['building_sha256']
            and states and all(type(s.get('open')) is bool for s in states)):
        value['display_opening_state'] = dict(
            building_sha256=value['building_sha256'], case_id=value['case_id'],
            basis='saved_case_input', states={s['id']:s for s in states})
    return value

def scope(ident, floor=None):
    rows = jobs(ident)
    floor = floor or (rows[0][1]['floor'] if rows else None)
    if not floor:
        floor = next((r['floor'] for r in sim.entry(ident).get('calculation_floors', []) if r.get('ok')), None)
    if not floor: raise ValueError('계산 층을 지정하세요')
    return sim.prepared(ident, floor, sim.fingerprint(ident))

def screening(ident, floor=None):
    raw, score = scope(ident, floor)
    value = json.loads(json.dumps(score))
    value['approved_input'] = raw['approved_input']
    value['ranked'] = [r for r in value['ranked'] if r['origin_budget']['Q_origin_peak_kW'] > 0]
    for r in value['ranked']:
        r['name'] = raw['approved_input']['room_uses'][r['room']]['label']
    rows=jobs(ident); target_floor=floor or (rows[0][1]['floor'] if rows else None)
    saved=next((sim.read(p/'input.json') for p,r in rows if r['floor']==target_floor),{})
    return dict(available=False, fuel_rerun_required=saved.get('approved_input',{}).get('quantity_settings',{})!=raw['approved_input'].get('quantity_settings',{}), unavailable_reason='점수 1위 화점 → MC 급기 탐색',
                score=value, manual_origins=value['ranked'], selection={}, comparison=None, progress={'running':False})

def handler(base, ident):
    from model_ai_tools import ModelTools
    class OperationHandler(base):
        def do_GET(self):
            path=urlsplit(self.path).path; query=parse_qs(urlsplit(self.path).query)
            try:
                if path in ('/','/model.html'):
                    return self.send((ROOT/'app/model-library/operation.html').read_bytes(),'text/html; charset=utf-8')
                if path=='/operation.js':
                    return self.send((ROOT/'app/model-library/operation.js').read_bytes(),'text/javascript')
                if path=='/operation-controls.js':
                    return self.send((ROOT/'app/model-library/operation-controls.js').read_bytes(),'text/javascript')
                if path=='/building.json':return self.send(model_path(sim.entry(ident)).read_bytes())
                if path=='/cfbt/model-info':return self.json(dict(building_id=ident,label=sim.entry(ident)['label'],operation_url=operation_url(sim.entry(ident))))
                if path=='/cfbt/lite/active.json':return self.json(active_playback(ident))
                if path.startswith('/cfbt/lite/export/'):
                    if self.client_address[0]!='127.0.0.1' or self.headers.get('Origin') not in (None,'http://'+self.headers.get('Host','')):return self.json({'error':'외부 요청 차단'},403)
                    from lite_export import build_export
                    output,_=build_export('http://127.0.0.1:'+str(self.server.server_port),path.rsplit('/',1)[-1],
                        json.loads(query.get('state',['{}'])[0]),int(query.get('interval',['10'])[0]),model_service=True)
                    return self.send(output,'text/html; charset=utf-8')
                if path.startswith('/cfbt/lite/result/'):return self.json(playback(ident,path.rsplit('/',1)[1]))
                if path=='/cfbt/lite/catalog.json':
                    import model_mc
                    import fixed_calculation
                    warnings=[];rows=jobs(ident,warnings)
                    cases=[dict(id=p.name,label=f"{r['floor']} {r['room'].split('_')[-1]} · 저장 결과",duration_s=r.get('duration_s'),saved_at_ms=int((p/'playback.json').stat().st_mtime*1000),run_id=p.name,engine_kind=r.get('engine') or saved_engine(p/'playback.json',(p/'playback.json').stat().st_mtime_ns)) for p,r in rows]+model_mc.cases(ident)+fixed_calculation.cases(sim.fingerprint(ident))
                    return self.json(dict(cases=cases,warnings=warnings,mc_summary=model_mc.summary(ident,query.get('mc_room',[None])[0]),
                        progress_text='저장 결과 · 추가 계산 없음',reuse_by_case={p.name:dict(case_id=p.name,label='저장 결과 재생 · 재계산 없음',equivalent=False) for p,r in rows}))
                if path.startswith('/cfbt/reuse/lite/'):
                    value=playback(ident,path.rsplit('/',1)[1])
                    return self.json(dict(case_id=value['case_id'],label='저장 결과 재생 · 재계산 없음',equivalent=False))
                if path=='/cfbt/lite/screening':return self.json(screening(ident,query.get('floor',[None])[0]))
                if path=='/cfbt/lite/mc':
                    import model_mc
                    return self.json(model_mc.status(ident))
                if path=='/cfbt/calculation':
                    import fixed_calculation
                    return self.json({**fixed_calculation.status(sim.fingerprint(ident)), 'server_busy':bool(sim._active)})
                if path=='/cfbt/lite/doors':
                    raw,_=scope(ident);rows=[]
                    for v in raw['openings']:
                        if 'door' not in v.get('kind',''):continue
                        rows.append(dict(id=v['id'],a=v['a'],b=v['b'],door_class=v.get('door_class','external' if v['b']=='OUTSIDE' else 'ordinary'),confidence=v.get('door_class_confidence','inferred'),connected_names=[v['a'],v['b']],reason=v.get('door_class_reason','자동 연결망 분류 · 미확인 표시 유지'),read_only=True))
                    import model_mc
                    fixed=sim.read(model_mc.config_path(ident)).get('fixed_state') if model_mc.config_path(ident).exists() else None
                    return self.json(dict(rows=rows,fixed_state=fixed))
                if path=='/cfbt/lite/fuel-settings':
                    from lite_fuel_settings import context
                    return self.json(context(sim.read(model_path(sim.entry(ident))),sim.fingerprint(ident)))
                if path=='/cfbt/lite/ai/fuel':
                    return self.json(dict(configured=False,message='이 건물의 AI 수정 연결 전',rooms=None))
                if path.startswith('/models/simulation/') and query.get('building',[None])[0]!=ident:
                    return self.json({'error':'다른 건물 요청 차단'},400)
                if path.startswith(('/app/web/','/cfbt/','/simulation/viewer/')):
                    folder=ROOT/('app/web' if path.startswith('/app/web/') else 'simulation/viewer')
                    rel=path.split('/app/web/',1)[1] if path.startswith('/app/web/') else path.split('/simulation/viewer/',1)[1] if path.startswith('/simulation/viewer/') else path[len('/cfbt/'):]
                    target=(folder/rel).resolve()
                    if target.is_relative_to(folder.resolve()) and target.is_file() and target.suffix in ('.js','.css'):
                        return self.send(target.read_bytes(),('text/css' if target.suffix=='.css' else 'text/javascript')+'; charset=utf-8')
                return super().do_GET()
            except (ValueError,KeyError,TypeError,OSError) as exc:return self.json({'error':str(exc)},400)
        def do_POST(self):
            path=urlsplit(self.path).path
            if path in ('/cfbt/calculation','/cfbt/lite/mc','/models/simulation/run'):
                from app_control import stopping
                if stopping():return self.json({'error':'FireLapse 종료 처리 중입니다.'},409)
            if path.startswith('/cfbt/storage/'):
                from storage_cleanup import handle
                if handle(self,path):return
            if path.startswith('/cfbt/lite/export/'):
                if self.client_address[0]!='127.0.0.1' or self.headers.get('Origin') not in (None,'http://'+self.headers.get('Host','')):return self.json({'error':'외부 요청 차단'},403)
                try:
                    n=int(self.headers.get('Content-Length','0'))
                    if not 0<n<=2*1024*1024:raise ValueError('화면 상태 크기 오류')
                    body=json.loads(self.rfile.read(n))
                    from lite_export import build_export
                    output,_=build_export('http://127.0.0.1:'+str(self.server.server_port),path.rsplit('/',1)[-1],body.get('state',{}),int(body.get('interval',10)),model_service=True)
                    return self.send(output,'text/html; charset=utf-8')
                except (ValueError,KeyError,TypeError,OSError) as exc:return self.json({'error':str(exc)},400)
            if path=='/cfbt/calculation':
                if self.client_address[0]!='127.0.0.1' or self.headers.get('Origin') not in (None,'http://'+self.headers.get('Host','')):return self.json({'error':'외부 요청 차단'},403)
                try:
                    n=int(self.headers.get('Content-Length','0'))
                    if not 0<n<=4096:raise ValueError('요청 크기 오류')
                    import fixed_calculation
                    return self.json(fixed_calculation.start_model(ident,json.loads(self.rfile.read(n))),202)
                except RuntimeError as exc:return self.json({'error':str(exc)},409)
                except (ValueError,TypeError,KeyError,OSError) as exc:return self.json({'error':str(exc)},400)
            if path in ('/cfbt/lite/mc','/cfbt/lite/fixed-openings'):
                if self.client_address[0]!='127.0.0.1' or self.headers.get('Origin') not in (None,'http://'+self.headers.get('Host','')):return self.json({'error':'외부 요청 차단'},403)
                try:
                    n=int(self.headers.get('Content-Length','0'))
                    if not 0<n<=4096:raise ValueError('요청 크기 오류')
                    body=json.loads(self.rfile.read(n));import model_mc
                    return self.json(model_mc.start(ident,body),202) if path.endswith('/mc') else self.json(model_mc.apply(ident,body))
                except RuntimeError as exc:return self.json({'error':str(exc)},409)
                except (ValueError,TypeError,KeyError,OSError) as exc:return self.json({'error':str(exc)},400)
            if path=='/cfbt/lite/fuel-settings':
                if self.client_address[0]!='127.0.0.1' or self.headers.get('Origin') not in (None,'http://'+self.headers.get('Host','')):return self.json({'error':'외부 요청 차단'},403)
                try:
                    n=int(self.headers.get('Content-Length','0'))
                    if not 0<n<=100000:raise ValueError('요청 크기 오류')
                    body=json.loads(self.rfile.read(n))
                    from lite_fuel_settings import apply
                    with sim._lock:
                        if sim._active:raise RuntimeError('현재 계산 중입니다')
                        return self.json(apply(body,sim.read(model_path(sim.entry(ident))),sim.fingerprint(ident)))
                except RuntimeError as exc:return self.json({'error':str(exc)},409)
                except (ValueError,TypeError,KeyError,OSError) as exc:return self.json({'error':str(exc)},400)
            if path.startswith('/cfbt/lite/ai/'):
                from lite_ai_http import handle
                return handle(self,path,ModelTools(ident))
            if path=='/models/simulation/run':
                if self.headers.get('Origin') not in (None,'http://'+self.headers.get('Host','')):return self.json({'error':'외부 요청 차단'},403)
                try:
                    n=int(self.headers.get('Content-Length','0'))
                    if not 0<n<=4096:raise ValueError('요청 크기 오류')
                    body=json.loads(self.rfile.read(n))
                    if body.get('building')!=ident:raise ValueError('다른 건물 요청 차단')
                    return self.json(sim.start(body),202)
                except RuntimeError as exc:return self.json({'error':str(exc)},409)
                except (ValueError,TypeError,KeyError,OSError) as exc:return self.json({'error':str(exc)},400)
            return self.json({'error':'이 건물에서 아직 연결되지 않은 기능입니다','simulation_started':False},403)
    return OperationHandler

def start_servers(base):
    global _base_handler
    _base_handler = base
    from model_library import entries
    return [server for row in entries() if (server := ensure_server(row)) is not None]
