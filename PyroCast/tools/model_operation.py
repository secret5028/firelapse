"""Production panel/scene API for one model. Reads saved jobs; never runs on GET."""
import json
import logging
import threading
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs
from model_library import ROOT, model_path
import model_simulation as sim

PORTS = {'parkmarine':8842, 'showroom':8843}

def jobs(ident, warnings=None):
    digest = sim.fingerprint(ident)
    out = []
    for p in sorted((sim.RESULTS/ident).glob('*/status.json'), key=lambda p:p.stat().st_mtime, reverse=True):
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
                if path=='/cfbt/model-info':return self.json(dict(building_id=ident,label=sim.entry(ident)['label'],operation_url=f'http://127.0.0.1:{PORTS[ident]}/model.html'))
                if path=='/cfbt/lite/active.json':return self.json(playback(ident))
                if path.startswith('/cfbt/lite/result/'):return self.json(playback(ident,path.rsplit('/',1)[1]))
                if path=='/cfbt/lite/catalog.json':
                    import model_mc
                    import fixed_calculation
                    warnings=[];rows=jobs(ident,warnings)
                    cases=[dict(id=p.name,label=f"{r['floor']} {r['room'].split('_')[-1]} · 저장 결과") for p,r in rows]+model_mc.cases(ident)+fixed_calculation.cases(sim.fingerprint(ident))
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
                    if target.is_relative_to(folder.resolve()) and target.is_file() and target.suffix=='.js':
                        return self.send(target.read_bytes(),'text/javascript; charset=utf-8')
                return super().do_GET()
            except (ValueError,KeyError,TypeError,OSError) as exc:return self.json({'error':str(exc)},400)
        def do_POST(self):
            path=urlsplit(self.path).path
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
            if path=='/cfbt/lite/ai/reports/list':return self.json({'reports':[]})
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
    servers=[]
    for ident,port in PORTS.items():
        server=ThreadingHTTPServer(('127.0.0.1',port),handler(base,ident))
        threading.Thread(target=server.serve_forever,daemon=True).start();servers.append(server)
    return servers
