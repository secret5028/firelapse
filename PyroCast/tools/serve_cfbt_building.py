"""Local CAD viewer + asynchronous CFBT engine, isolated from the preserved application."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import gzip
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import math
from pathlib import Path
import re
import sys
import threading
import time
import traceback
from urllib.parse import urlsplit,unquote,parse_qs

ROOT=Path(__file__).resolve().parents[1]
SIM=ROOT/'simulation'
from runtime_storage import RESULTS as DATA_RESULTS
from loopback_guard import LoopbackHostMixin
sys.path.insert(0,str(SIM))
from pyrocast_cfbt.cad import adapt,resolve_building
from pyrocast_cfbt.playback import package
from pyrocast_cfbt.spread import simulate
from pyrocast_cfbt.comparison import compare_ignition,comparison_key


def execution_key(options,building_sha,engine):
    """Reuse verified native outputs only for identical code, engine and inputs."""
    implementation=hashlib.sha256()
    for path in sorted([*(SIM/'pyrocast_cfbt').glob('*.py'),SIM/'building_rules.py',ROOT/'config/building-rules.json']):
        implementation.update(path.name.encode());implementation.update(path.read_bytes())
    for path in [*sorted((SIM/'data').glob('*.json')), *sorted((SIM/'extensions/thermal').glob('*.c')), *list((SIM/'build').glob('plate.dll'))]:
        implementation.update(path.name.encode());implementation.update(path.read_bytes())
    payload={'cache_schema':'engine-inputs-v2-no-server', 'options':options,'building_sha256':building_sha,
             'engine_sha256':hashlib.sha256(Path(engine).read_bytes()).hexdigest(),
             'implementation_sha256':implementation.hexdigest()}
    return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()[:24]


def checked_options(raw):
    if not isinstance(raw,dict):raise ValueError('설정 형식 오류')
    allowed={'fire_floor','fire_room','duration_s','max_added_ignitions','solid_ignition_C','gas','pilot_assumed',
             'opening_overrides','door_fraction','window_fraction','max_time_step_s','scope_floor','flashover','risk','gas_model','iteration_mode','window_breakage','full_floor_search','vertical_smoke','fuel_source_base_m','room_fire_rule'}
    if set(raw)-allowed:raise ValueError('지원하지 않는 설정')
    options=dict(raw)
    if 'room_fire_rule' in options:
        rule=options['room_fire_rule']
        if not isinstance(rule,dict) or set(rule)-{'enabled','preset','setpoint','ramp_s','trigger_mode','threshold_multiplier','vent_cap_enabled','vent_cap_k','candidate_ids'} or not isinstance(rule.get('enabled'),bool):
            raise ValueError('실 전환 규칙 설정 오류')
        from pyrocast_cfbt.room_rule import settings
        settings({'room_fire_rule':rule})
    if 'vertical_smoke' in options and not isinstance(options['vertical_smoke'],bool):raise ValueError('층간 연기 설정 오류')
    if 'window_breakage' in options:
        from pyrocast_cfbt.openings import policy
        policy({'window_breakage':options['window_breakage']},
               {'id':'validation','kind':'window','b':'OUTSIDE','schedule':[[0,options.get('window_fraction',0.)]]})
    if options.get('iteration_mode','earliest_single') not in ('earliest_single','fixed_point'):raise ValueError('반복 방식 오류')
    if 'full_floor_search' in options and not isinstance(options['full_floor_search'],bool):raise ValueError('전층 탐색 설정 오류')
    limits={'duration_s':(30,3600),'max_added_ignitions':(0,1000),'solid_ignition_C':(30,1500),
            'door_fraction':(0,1),'window_fraction':(0,1),'max_time_step_s':(.05,2.),'fuel_source_base_m':(0,3.)}
    for key,(lo,hi) in limits.items():
        if key in options and (not isinstance(options[key],(int,float)) or not math.isfinite(options[key]) or not lo<=options[key]<=hi):
            raise ValueError('설정 범위 오류: '+key)
    if options.get('duration_s',900)%5:raise ValueError('계산 시간은 5초 단위로 지정하세요')
    if int(options.get('max_added_ignitions',3))!=options.get('max_added_ignitions',3):raise ValueError('착화 상한은 정수입니다')
    gas=options.get('gas',{})
    gas_limits={'gas_ignition_C':(20,1500),'vent_ignition_C':(20,1500),'hot_C':(20,1500),
                'oxygen_min_vol_percent':(.1,30),'rate_ref_s_inv':(0,10)}
    if not isinstance(gas,dict) or set(gas)-set(gas_limits):raise ValueError('가스 설정 오류')
    for key,value in gas.items():
        lo,hi=gas_limits[key]
        if not isinstance(value,(int,float)) or not math.isfinite(value) or not lo<=value<=hi:raise ValueError('가스 설정 범위 오류')
    if 'gas_model' in options:
        kind=options.pop('gas_model')
        if kind not in ('legacy','mixture'):raise ValueError('추가연소 모델 오류')
        options.setdefault('gas',{}).update(mixture_enabled=kind=='mixture',jet_enabled=True,energy_basis='total_potential_assumption')
    overrides=options.get('opening_overrides',{})
    if not isinstance(overrides,dict) or len(overrides)>1000:raise ValueError('개구부 설정 오류')
    for key,value in overrides.items():
        if not re.fullmatch(r'CAD_[A-Za-z0-9_]{1,40}',key) or not isinstance(value,(float,int)) or not math.isfinite(value) or not 0<=value<=1:
            raise ValueError('개구부 설정 범위 오류')
    if 'pilot_assumed' in options and not isinstance(options['pilot_assumed'],bool):raise ValueError('점화원 설정 오류')
    fo=options.get('flashover',{})
    if not isinstance(fo,dict) or set(fo)-{'enabled','temperature_C'}:raise ValueError('FO 설정 오류')
    if 'enabled' in fo and not isinstance(fo['enabled'],bool):raise ValueError('FO 설정 오류')
    if 'temperature_C' in fo:
        value=fo['temperature_C']
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 100<=value<=1500:raise ValueError('FO 온도 범위 오류')
        options['criteria']={'fo_temperature_C':value}
        options['flashover']={k:v for k,v in fo.items() if k!='temperature_C'}
    risk=options.get('risk',{})
    if not isinstance(risk,dict) or set(risk)-{'fgi_fuel_mass_percent','fgi_oxygen_vol_percent'}:raise ValueError('위험 판정 설정 오류')
    for key,value in risk.items():
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not .01<=value<=21:raise ValueError('위험 판정 범위 오류')
    criteria=options.setdefault('criteria',{})
    if 'fgi_fuel_mass_percent' in risk:criteria['fgi_fuel_mass_fraction']=risk['fgi_fuel_mass_percent']/100
    if 'fgi_oxygen_vol_percent' in risk:criteria['fgi_oxygen_vol_percent']=risk['fgi_oxygen_vol_percent']
    return options


def main():
    parser=argparse.ArgumentParser();parser.add_argument('project',type=Path);parser.add_argument('--port',type=int,default=8780)
    parser.add_argument('--result',type=Path,default=SIM/'results/cad_connected/playback.json')
    parser.add_argument('--building',type=Path,help='추출된 building.json 경로')
    parser.add_argument('--watch-result',type=Path,help='별도 실행 중인 workspace 결과 폴더의 진행 상태 표시')
    args=parser.parse_args();project=args.project.resolve()
    watch=args.watch_result.resolve() if args.watch_result else None
    if watch and not watch.is_relative_to((SIM/'results').resolve()):
        raise ValueError('Watched results must stay inside simulation/results')
    source=resolve_building(project,args.building);model=source.parent;folder=model.parent
    job=folder.name if model.name=='cad-output' else hashlib.sha256(source.read_bytes()).hexdigest()[:16]
    assets=project/'work/cad-web/local-resources/cad-assets'
    building=json.loads((model/'building.json').read_text('utf-8'))
    from model_library import execution_policy,RUN_PATHS
    model_execution=execution_policy(building,source)
    if not (model/'model.html').is_file():raise ValueError('3D model.html이 없습니다. 도면의 3D 생성 결과 폴더를 지정하세요.')
    sha=hashlib.sha256((model/'building.json').read_bytes()).hexdigest()
    from pyrocast_cfbt.topology import corrected_building
    from pyrocast_cfbt.outdoor import present_corrected_playback
    from pyrocast_cfbt.fuel_layout import present as present_fuel_layout
    def present_playback(payload):
        return present_fuel_layout(present_corrected_playback(payload,building))
    from pyrocast_cfbt.cad import geometry_dependencies
    geometry_dependencies(project)
    building,geometry_corrections=corrected_building(building,sha)
    state={'busy':False,'error':None,'latest':None,'started':None,'folder':None,'request_id':None,'kind':'run','comparison_path':None}
    engine=SIM/'build/mixture_r2/cfbt/cfast-cfbt.exe'
    lock=threading.Lock();pool=ThreadPoolExecutor(max_workers=1)
    r8_folder=SIM/'results/room_rule_r8_20261025'
    from result_catalog import CombinedResultCatalog as ResultCatalog
    catalog_index=ResultCatalog(SIM/'results', SIM/'config/native-case-aliases.json')
    import lite_mc_service as mc_service
    from execution_cache import ExecutionCache
    from result_catalog import atomic_json
    execution_cache=ExecutionCache(DATA_RESULTS)
    from saved_case_reuse import describe as describe_reuse
    def reuse_info(row,kind):
        return describe_reuse(row,kind,sha,execution_cache,lambda kind,options,building:execution_key(options,building,engine))
    def saved_cases():
        rows=catalog_index.cases(sha, 'native')
        return {r['id']:(r['label'],Path(r['path'])) for r in rows}
    sha_by_file={}
    def stored_sha(path):
        """building_sha256 of a saved replay, parsed once per file version (status polls call this)."""
        path=Path(path)
        try:stat=path.stat()
        except OSError:return None
        version=(stat.st_mtime_ns,stat.st_size);known=sha_by_file.get(path)
        if known and known[0]==version:return known[1]
        try:value=json.loads(path.read_text('utf-8')).get('building_sha256')
        except (OSError,ValueError,AttributeError):return None
        sha_by_file[path]=(version,value)
        return value
    def latest():
        with lock:
            path=state['latest'] or (args.result if args.result.is_file() else SIM/'results/cad_floor_smoke_v5_prescribed/playback.json')
            if not state['latest'] and watch and (watch/'playback.json').is_file():
                try:
                    candidate=json.loads((watch/'playback.json').read_text('utf-8'))
                    if candidate.get('complete') and candidate.get('building_sha256')==sha:path=watch/'playback.json'
                except (OSError,ValueError):pass
            return path if stored_sha(path)==sha else None
    def compute(options,identity):
        destination=DATA_RESULTS/'cad_interactive'/identity
        try:
            scenario=adapt(project,{**options,'building_path':str(source)});destination.mkdir(parents=True,exist_ok=True)
            atomic_json(destination/'execution-request.json',{'options':options,'building_sha256':sha})
            (destination/'scenario.json').write_text(json.dumps(scenario,ensure_ascii=False,indent=2),encoding='utf-8')
            with lock:state['folder']=destination
            result=simulate(scenario,engine if engine.is_file() else SIM/'build/cfbt/cfast-cfbt.exe',destination)
            payload=package(result);output=destination/'playback.json'
            tmp=output.with_suffix('.tmp');tmp.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':'),allow_nan=False),encoding='utf-8');tmp.replace(output)
            execution_cache.seal(destination,'native',identity,sha)
            with lock:state['latest']=output
        except Exception as exc:
            with lock:state['error']=str(exc)
        finally:
            with lock:state['busy']=False

    def compute_r8(options,rule_options,compare,identity):
        nonlocal r8_folder
        destination=DATA_RESULTS/'cad_r8_review'/identity
        try:
            from run_room_rule_r8 import run_batch
            raw=adapt(project,{**options,'building_path':str(source)})
            with lock:state['folder']=destination;r8_folder=destination
            atomic_json(destination/'execution-request.json',{'options':{'options':options,'room_rule_r8':rule_options,'compare':compare},'building_sha256':sha})
            run_batch(raw,destination,rule_options,compare)
            execution_cache.seal(destination,'r8',identity,sha)
            # Deliberately no state['latest'] assignment: replacement needs approval.
        except Exception as exc:
            with lock:state['error']=str(exc)
        finally:
            with lock:state['busy']=False

    def compute_comparison(base_path,options,identity):
        try:
            base=json.loads(base_path.read_text('utf-8'))
            if base['scenario']['cad']['building_sha256']!=sha:raise ValueError('다른 건물의 비교는 할 수 없습니다.')
            key=comparison_key(base,options['room'],options['time_s'],engine,options.get('duration_s',30),options.get('rate_s_inv',.2))
            destination=DATA_RESULTS/'cad_ignition_comparisons'/key[:24]
            for file in (destination/'comparison.json',SIM/'results/cad_exterior_ignition_demo_v4_ceiling_250/comparison.json'):
                if file.is_file() and json.loads(file.read_text('utf-8')).get('cache_key')==key:
                    with lock:state.update(comparison_path=str(file),folder=file.parent,cache_hit=True)
                    return
            destination.mkdir(parents=True,exist_ok=True)
            with lock:state['folder']=destination
            compare_ignition(base,options['room'],options['time_s'],engine,destination,
                             options.get('duration_s',30),options.get('rate_s_inv',.2))
            with lock:state['comparison_path']=str(destination/'comparison.json')
        except Exception as exc:
            with lock:state['error']=str(exc)
        finally:
            with lock:state['busy']=False

    class Handler(LoopbackHostMixin,BaseHTTPRequestHandler):
        def send_data(self,data,mime='application/json; charset=utf-8',code=200):
            compressed=(len(data)>65536 and mime.startswith('application/json') and
                        'gzip' in self.headers.get('Accept-Encoding','').lower())
            if compressed:data=gzip.compress(data,compresslevel=1,mtime=0)
            self.send_response(code);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)))
            if compressed:self.send_header('Content-Encoding','gzip');self.send_header('Vary','Accept-Encoding')
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(data)
        def json(self,value,code=200):return self.send_data(json.dumps(value,ensure_ascii=False).encode(),'application/json; charset=utf-8',code)
        def guarded(self,action):
            # An unexpected failure must still answer; details go to the server log only.
            try:return action()
            except ConnectionError:raise
            except Exception:
                traceback.print_exc()
                return self.json({'error':'요청 처리 실패'},500)
        def do_GET(self):return self.guarded(self.get)
        def do_POST(self):return self.guarded(self.post)
        def get(self):
            path=unquote(urlsplit(self.path).path);prefix='/cad-result/'+job+'/'
            # A server instance owns one building. Keep its entry URL stable
            # when an extracted model moves or its content-derived ID changes.
            old_model=re.fullmatch(r'/cad-result/[a-f0-9]{16,64}/model\.html',path)
            if path in ('/','/model.html') or (old_model and path!=prefix+'model.html'):
                query=urlsplit(self.path).query
                self.send_response(302);self.send_header('Location',prefix+'model.html'+('?' + query if query else ''))
                self.send_header('Cache-Control','no-store');self.end_headers();return
            if path==prefix+'building.json':return self.json(building)
            if path=='/cfbt/model-info':
                return self.json({'building_sha256':sha,'floors':[{'name':f['name'],'rooms':[{'id':r['id'],'area_m2':r.get('area',0)} for r in f['rooms'] if 'outdoor' not in r.get('tags',[])]} for f in building['floors'] if f.get('rooms')]})
            if path.startswith('/cfbt/reuse/'):
                parts=path.split('/')
                if len(parts)!=5 or parts[3] not in ('native','lite'):return self.json({'error':'Invalid reuse request'},400)
                kind,key=parts[3:]
                cfg=json.loads((SIM/'config/lite-viewer.json').read_text('utf-8')) if kind=='lite' else {}
                row=next((r for r in catalog_index.cases(sha,kind,cfg.get('cases',[])) if r['id']==key),None)
                if row is None:return self.json({'error':'Unknown saved case'},404)
                return self.json(reuse_info(row,kind))
            if path=='/cfbt/cases':
                return self.json([{'id':key,'label':label} for key,(label,file) in saved_cases().items()])
            if path.startswith('/cfbt/case/'):
                key=path[len('/cfbt/case/'):]
                cases=saved_cases()
                if key not in cases or not cases[key][1].is_file():return self.send_error(404)
                saved_case=json.loads(cases[key][1].read_text('utf-8'))
                if saved_case.get('building_sha256')!=sha:return self.send_error(404)
                return self.json(present_playback(saved_case))
            if path=='/cfbt/r8/schema':
                from pyrocast_cfbt.rule_settings import schema
                return self.json(schema())
            if path.startswith('/cfbt/lite/export/'):
                if self.client_address[0]!='127.0.0.1':return self.send_error(403)
                try:
                    from lite_export import build_export
                    params=parse_qs(urlsplit(self.path).query)
                    view_state=json.loads(params.get('state',['{}'])[0])
                    output,info=build_export('http://127.0.0.1:'+str(self.server.server_port),path.rsplit('/',1)[-1],view_state,int(params.get('interval',['10'])[0]))
                    return self.send_data(output,'text/html; charset=utf-8')
                except Exception as exc:return self.json({'error':str(exc)},400)
            if path=='/cfbt/lite/fuel-settings':
                from lite_fuel_settings import context
                return self.json(context(building,sha))
            if path=='/cfbt/lite/ai/fuel':
                if self.client_address[0]!='127.0.0.1':return self.send_error(403)
                try:
                    import lite_ai_fuel
                    return self.json(lite_ai_fuel.status(building,sha))
                except Exception:return self.json({'error':'AI 설정 또는 연료 입력 오류'},400)
            if path=='/cfbt/lite/fire-load-table':
                if self.client_address[0]!='127.0.0.1':return self.send_error(403)
                return self.send_data((SIM/'pyrocast_lite/fire_load_table.json').read_bytes(),'application/json; charset=utf-8')
            if path=='/cfbt/lite/doors':
                from pyrocast_lite.door_classification import classify_doors
                raw=json.loads((SIM/'results/room_rule_r8_20261025/source-scenario.json').read_text('utf-8'))
                saved=SIM/'config/lite-door-overrides.json'
                overrides=json.loads(saved.read_text('utf-8')) if saved.exists() else {}
                from lite_fixed_openings import door_report
                return self.json(door_report(raw,overrides))
            if path=='/cfbt/lite/mc':
                with lock:busy=state['busy']
                return self.json({**mc_service.status(sha),'server_busy':busy,'available':True})
            if path=='/cfbt/calculation':
                import fixed_calculation
                return self.json({**fixed_calculation.status(sha),'available':model_execution['allowed'],'server_busy':state['busy']})
            if path.startswith('/cfbt/lite/result/calc-'):
                import fixed_calculation
                try:return self.json(fixed_calculation.playback(sha,path.rsplit('/',1)[-1]))
                except ValueError as exc:return self.json({'error':str(exc)},400)
            if path=='/cfbt/lite/screening':
                import lite_screening_service as screening
                return self.json(screening.payload())
            if path=='/cfbt/r8/review':
                with lock:
                    review=r8_folder
                    live_error=state['error'] if state['kind']=='r8' else None
                    live_running=state['kind']=='r8' and state['busy']
                batch=review/'batch-state.json';result=review/'comparison.json'
                def read_review(file):
                    try:return json.loads(file.read_text('utf-8'))
                    except (OSError,ValueError):return None
                payload={'batch_state':read_review(batch),
                         'comparison':read_review(result),
                         'progress':{name:read_review(review/name/'execution-state.json') for name in ('selected','aggressive') if (review/name/'execution-state.json').exists()},
                         'operating_playback_replaced':False}
                if live_running:payload['batch_state']={'state':'running'}
                elif live_error:payload['batch_state']={'state':'failed','error':live_error}
                if payload['comparison'] and payload['comparison'].get('building_sha256')!=sha:
                    return self.json({'batch_state':None,'comparison':None,'message':'현재 건물과 다른 시험 결과입니다.'})
                return self.json(payload)
            if path=='/cfbt/status':
                with lock:
                    status={k:v for k,v in state.items() if k not in ('latest','folder','comparison_path')}
                    destination=state['folder']
                status['available']=latest() is not None
                status['elapsed_s']=round(time.monotonic()-status['started'],1) if status['started'] else 0
                status['native_time_s']=None;status['attempt']=0
                if watch and not destination:
                    destination=watch
                    try:job_state=json.loads((watch/'job-state.json').read_text('utf-8'))
                    except (OSError,ValueError):job_state={'status':'running'}
                    status['external_watch']=True
                    status['request_id']='watched_result'
                    try:watch_complete=bool(json.loads((watch/'playback.json').read_text('utf-8')).get('complete'))
                    except (OSError,ValueError):watch_complete=False
                    status['busy']=job_state['status']=='running' and not watch_complete
                    status['elapsed_s']=max(0,round(time.time()-(watch/'scenario.json').stat().st_mtime))
                    if job_state['status']=='failed':status['error']=job_state.get('error','별도 계산 실패')
                if destination:
                    runs=sorted((p for p in destination.glob('run_*') if p.is_dir() and p.name[4:].isdigit()),
                                key=lambda p:int(p.name[4:]))
                    if runs:
                        status['attempt']=len(runs)
                        execution=runs[-1]/'execution-state.json'
                        try:status['execution']=json.loads(execution.read_text('utf-8'))
                        except (OSError,ValueError):pass
                        file=runs[-1]/'case_cfbt_rooms.csv'
                        try:
                            with file.open('rb') as stream:
                                stream.seek(max(0,file.stat().st_size-2048));lines=stream.read().decode('ascii').strip().splitlines()
                            status['native_time_s']=float(lines[-1].split(',')[0])
                        except (OSError,ValueError,IndexError):pass
                return self.json(status)
            if path=='/cfbt/playback.json':
                saved=latest()
                if saved:return self.json(present_playback(json.loads(Path(saved).read_text('utf-8'))))
                return self.json({'error':'아직 완료된 계산이 없습니다'},404)
            if path in ('/cfbt/lite/active.json','/cfbt/lite/catalog.json') or path.startswith('/cfbt/lite/result/'):
                conf=SIM/'config/lite-viewer.json'
                if not conf.is_file():return self.json({'error':'No adopted lite result'},404)
                cfg=json.loads(conf.read_text('utf-8'))
                if not path.endswith('active.json'):
                    cfg['cases']=catalog_index.cases(sha,'lite',cfg.get('cases',[]))
                requested_room=parse_qs(urlsplit(self.path).query).get('mc_room',[None])[0]
                current_summary=mc_service.summary(sha,requested_room) if path.endswith('catalog.json') else None
                if current_summary:cfg['mc_summary']=current_summary;cfg['progress_text']='MC 저장 결과 · '+str(current_summary['completed'])+'표본 완료'
                if path.endswith('catalog.json'):
                    cfg['reuse_by_case']={r['id']:reuse_info(r,'lite') for r in cfg['cases']}
                    import fixed_calculation
                    cfg['cases']=[r for r in cfg['cases'] if '/fixed-calculations/' not in r.get('path','').replace('\\','/')]+fixed_calculation.cases(sha)
                    public={k:v for k,v in cfg.items() if k!='active_path'}
                    public['cases']=[{k:v for k,v in row.items() if k!='path'} for row in cfg['cases']]
                    return self.json(public)
                chosen=cfg.get('active_path') if path.endswith('active.json') else next((x['path'] for x in cfg.get('cases',[]) if x['id']==path.rsplit('/',1)[-1]),None)
                if not chosen:return self.json({'error':'Unknown lite case'},404)
                from runtime_storage import playback_path
                try:file=playback_path(chosen)
                except ValueError:return self.json({'error':'Invalid lite path'},404)
                payload=json.loads(file.read_text('utf-8'))
                if payload.get('building_sha256')!=sha:return self.json({'error':'Different building'},400)
                if file.parent.name.startswith('calc-'):
                    import fixed_calculation
                    return self.json(fixed_calculation.playback(sha,file.parent.name))
                return self.json(payload)
            if path in ('/cfbt/comparison.json','/cfbt/comparison-demo.json','/cfbt/comparison-floor.json'):
                with lock:selected_path=state['comparison_path']
                file=(SIM/'results/cad_exterior_ignition_demo_v4_ceiling_250/comparison.json' if path.endswith('-demo.json') else SIM/'results/cad_floor_smoke_ignition_v5_prescribed/comparison.json' if path.endswith('-floor.json') else Path(selected_path) if selected_path else None)
                if not file or not file.is_file():return self.json({'error':'완료된 점화 비교가 없습니다'},404)
                payload=json.loads(file.read_text('utf-8'))
                if payload['baseline']['building_sha256']!=sha:return self.json({'error':'다른 건물의 비교입니다'},400)
                for part in ('baseline','ignited'):
                    if part in payload:payload[part]=present_playback(payload[part])
                return self.json(payload)
            if path in ('/cfbt/theme.css','/cfbt/overlay.js','/cfbt/overlay.css','/cfbt/legacy_real_view.js','/cfbt/legacy_real_bridge.js','/cfbt/risk.js','/cfbt/gas_visual.js','/cfbt/smoke_visual.js','/cfbt/smoke_transport.js','/cfbt/ceiling_jets.js','/cfbt/frozen_rule_controls.js','/cfbt/lite_doors.js','/cfbt/screening.js'):
                file=SIM/'viewer'/Path(path).name
                return self.send_data(file.read_bytes(),'text/javascript' if file.suffix=='.js' else 'text/css')
            if path==prefix+'legacy-context.json':
                manifest=json.loads((folder/'files.json').read_text('utf-8')) if (folder/'files.json').is_file() else {};saved=folder/'cad-ui-state.json'
                return self.json({'jobId':job,'buildingId':hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest(),
                                  'state':json.loads(saved.read_text('utf-8')) if saved.exists() else None})
            if path=='/api/jobs/'+job+'/hydraulics':
                file=folder/'hydraulics.json';return self.json(json.loads(file.read_text('utf-8')) if file.exists() else None)
            if path.startswith(prefix):root,rel=model,path[len(prefix):]
            elif path.startswith('/cad-assets/'):root,rel=assets,path[len('/cad-assets/'):]
            else:return self.send_error(404)
            file=(root/rel).resolve()
            if not file.is_relative_to(root.resolve()) or not file.is_file() or file.suffix not in ('.html','.json','.js','.svg','.css','.png'):return self.send_error(404)
            data=file.read_bytes()
            if file==model/'model.html':
                html=data.decode('utf-8')
                # Load menu/layout rules before the CAD module creates panels,
                # avoiding a flash of the old menus while playback is fetched.
                html=html.replace('</head>','<link rel="stylesheet" href="/cfbt/overlay.css"></head>',1)
                html=html.replace('const tagCol={stair:','const tagCol={outdoor:0x829a84,stair:')
                hook='\nawait (await import("/cfbt/overlay.js")).attach({THREE,B,S,C,O,R,L2,groups,ext,shp,leaves,glassM,legacyRoot,getFloor:()=>selFloor,setFloor:n=>{const button=[...document.getElementById("fbtn").children].find(b=>b.textContent===(n==="all"?"전체":n));button?.click();}});\n'
                html=re.sub(r'(<script type="module">)(.*?)(</script>)',lambda m:m[1]+m[2]+hook+m[3],html,count=1,flags=re.S)
                data=html.encode('utf-8')
            mime={'.html':'text/html; charset=utf-8','.js':'text/javascript','.json':'application/json','.css':'text/css','.svg':'image/svg+xml','.png':'image/png'}[file.suffix]
            return self.send_data(data,mime)
        def post(self):
            nonlocal r8_folder
            request_path=urlsplit(self.path).path
            if request_path in (RUN_PATHS|{'/cfbt/calculation'}):
                from app_control import stopping
                if stopping():return self.json({'error':'FireLapse 종료 처리 중입니다.'},409)
            if request_path.startswith('/cfbt/storage/'):
                from storage_cleanup import handle
                if handle(self,request_path):return
            if request_path in (RUN_PATHS|{'/cfbt/calculation'}) and not model_execution['allowed']:
                return self.json({'error':model_execution['reason'],'simulation_started':False},403)
            if request_path.startswith('/cfbt/lite/ai/') and request_path!='/cfbt/lite/ai/fuel':
                from lite_ai_http import handle
                return handle(self,request_path)
            if request_path not in ('/cfbt/calculation','/cfbt/run','/cfbt/ignite','/cfbt/r8/run','/cfbt/lite/doors','/cfbt/lite/screening','/cfbt/lite/mc','/cfbt/lite/fixed-openings','/cfbt/lite/ai/fuel','/cfbt/lite/fuel-overrides','/cfbt/lite/fuel-settings'):return self.json({'error':'지원하지 않는 요청입니다'},405)
            if self.headers.get('Origin') not in (None,'http://'+self.headers.get('Host','')):return self.json({'error':'외부 요청 차단'},403)
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=100000:raise ValueError('요청 크기 오류')
                body=json.loads(self.rfile.read(length));base_path=None
                if mc_service.status(sha).get('running'):return self.json({'error':'현재 MC 계산 중입니다'},409)
                if request_path=='/cfbt/calculation':
                    if self.client_address[0]!='127.0.0.1':return self.send_error(403)
                    import fixed_calculation
                    with lock:
                        if state['busy'] or fixed_calculation.status(sha)['running']:return self.json({'error':'현재 계산 중입니다'},409)
                        destination=fixed_calculation.reserve(sha,body)
                        state.update(busy=True,kind='fixed',error=None)
                    def work_fixed():
                        try:fixed_calculation.compute(destination)
                        finally:
                            with lock:state['busy']=False
                    pool.submit(work_fixed)
                    return self.json({'started':True,'id':destination.name},202)
                if request_path in ('/cfbt/lite/ai/fuel','/cfbt/lite/fuel-overrides','/cfbt/lite/fuel-settings'):
                    if self.client_address[0]!='127.0.0.1':return self.send_error(403)
                    import lite_ai_fuel
                    import lite_screening_service as screening
                    if request_path.endswith('/ai/fuel'):
                        return self.json(lite_ai_fuel.propose(body,building,sha))
                    with lock:
                        if state['busy'] or (screening.payload().get('progress') or {}).get('running'):return self.json({'error':'현재 계산 중입니다'},409)
                        if request_path.endswith('/fuel-settings'):
                            from lite_fuel_settings import apply
                            return self.json(apply(body,building,sha))
                        return self.json(lite_ai_fuel.apply(body,building,sha))
                if request_path=='/cfbt/lite/mc':
                    with lock:
                        import lite_screening_service as screening
                        if state['busy'] or (screening.payload().get('progress') or {}).get('state')=='running':return self.json({'error':'현재 계산 중입니다'},409)
                        request,mc_input=mc_service.prepare_request(body,sha)
                        destination=mc_service.reserve(request,mc_input)
                        state.update(busy=True,kind='lite_mc',error=None,started=time.monotonic())
                    def work_mc():
                        try:
                            mc_service.compute(destination)
                            catalog_index.scan(force=True)
                        except Exception as exc:
                            with lock:state['error']=str(exc)
                        finally:
                            with lock:state['busy']=False
                    pool.submit(work_mc)
                    return self.json({'started':True,'id':destination.name,'workers':1,'budget_s_per_sample':1200},202)
                if request_path=='/cfbt/lite/screening':
                    import lite_screening_service as screening
                    if not isinstance(body,dict) or set(body)-{'top_n','mc_room','run','rooms'}:raise ValueError('후보 선택 요청 오류')
                    if type(body.get('run',False)) is not bool:raise ValueError('run은 참/거짓입니다')
                    with lock:
                        external=screening.payload().get('progress') or {}
                        if state['busy'] or external.get('state')=='running':return self.json({'error':'현재 계산 중입니다. 완료 후 선택하세요.'},409)
                        data=screening.select(body.get('top_n'),body.get('mc_room'),body.get('rooms'))
                        if not body.get('run'):return self.json(data)
                        state.update(busy=True,kind='lite_screening',error=None,started=time.monotonic())
                    def work():
                        try:screening.compute(body['top_n'],body.get('rooms'))
                        except Exception as exc:
                            with lock:state['error']=str(exc)
                        finally:
                            with lock:state['busy']=False
                    pool.submit(work)
                    return self.json({'started':True,'workers':1,'MC_started':False},202)
                if request_path=='/cfbt/lite/fixed-openings':
                    from lite_fixed_openings import apply_worst, clear, door_report
                    import lite_screening_service as screening
                    if not isinstance(body,dict) or set(body) not in ({'job_id'},{'clear'},{'assistant_proposal'}):raise ValueError('확정 급기 요청 오류')
                    with lock:
                        if state['busy'] or (screening.payload().get('progress') or {}).get('state')=='running':return self.json({'error':'현재 계산 중입니다'},409)
                        if 'assistant_proposal' in body:
                            from lite_ai_tools import apply_opening_proposal
                            apply_opening_proposal(body['assistant_proposal'],sha)
                        elif 'clear' in body:
                            if body['clear'] is not True:raise ValueError('clear는 true입니다')
                            clear()
                        else:apply_worst(body['job_id'],sha)
                        raw=json.loads((SIM/'results/room_rule_r8_20261025/source-scenario.json').read_text('utf-8'))
                        saved=SIM/'config/lite-door-overrides.json'
                        return self.json(door_report(raw,json.loads(saved.read_text('utf-8'))))
                if request_path=='/cfbt/lite/doors':
                    from pyrocast_lite.door_classification import classify_doors
                    if not isinstance(body,dict) or set(body)!={'id','door_class'}:raise ValueError('문 분류 요청 오류')
                    raw=json.loads((SIM/'results/room_rule_r8_20261025/source-scenario.json').read_text('utf-8'))
                    saved=SIM/'config/lite-door-overrides.json'
                    with lock:
                        overrides=json.loads(saved.read_text('utf-8')) if saved.exists() else {}
                        overrides[body['id']]=body['door_class']
                        from lite_fixed_openings import door_report
                        report=door_report(raw,overrides)
                        saved.parent.mkdir(parents=True,exist_ok=True)
                        tmp=saved.with_suffix('.tmp');tmp.write_text(json.dumps(overrides,ensure_ascii=False,indent=2),'utf-8');tmp.replace(saved)
                    return self.json(report)
                if request_path=='/cfbt/r8/run':
                    from pyrocast_cfbt.rule_settings import resolve
                    if not isinstance(body,dict) or set(body)-{'options','settings','compare_aggressive'}:raise ValueError('r8 요청 형식 오류')
                    rule_options=body.get('settings',{});resolve(rule_options)
                    compare=body.get('compare_aggressive',False)
                    if not isinstance(compare,bool):raise ValueError('비교 실행은 참/거짓으로 지정하세요')
                    options=checked_options(body.get('options',{}));options.pop('room_fire_rule',None)
                    stock=SIM/'build/baseline/cfast-baseline.exe'
                    identity=execution_key({'options':options,'room_rule_r8':rule_options,'compare':compare},sha,stock)
                    with lock:
                        current=r8_folder/'batch-state.json'
                        external_running=current.exists() and json.loads(current.read_text('utf-8')).get('state')=='running'
                        if state['busy'] or external_running:return self.json({'error':'현재 계산이 진행 중입니다'},409)
                        cached=execution_cache.lookup('r8',identity,sha)
                        if cached:
                            r8_folder,record=cached
                            state.update(cache_hit=True,folder=r8_folder,request_id=identity)
                            return self.json({'request_id':identity,'review_only':True,'already_attempted':True,'cache_hit':True,'legacy_key':record.get('old_key'),'solver_runs':0},200)
                        destination=DATA_RESULTS/'cad_r8_review'/identity
                        if (destination/'batch-state.json').exists():
                            r8_folder=destination
                            return self.json({'request_id':identity,'review_only':True,'already_attempted':True},200)
                        r8_folder=destination
                        state.update(busy=True,error=None,started=time.monotonic(),folder=None,request_id=identity,kind='r8',cache_hit=False)
                    pool.submit(compute_r8,options,rule_options,compare,identity)
                    return self.json({'request_id':identity,'review_only':True},202)
                if request_path=='/cfbt/ignite':
                    if not isinstance(body,dict) or set(body)-{'case','room','time_s','duration_s','rate_s_inv'}:raise ValueError('점화 비교 요청 오류')
                    if not isinstance(body.get('room'),str):raise ValueError('실을 선택하세요.')
                    for key,lo,hi in [('time_s',0,3600),('duration_s',1,60),('rate_s_inv',.01,1)]:
                        v=body.get(key,{'duration_s':30,'rate_s_inv':.2}.get(key))
                        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not lo<=v<=hi:raise ValueError('점화 비교 설정 오류: '+key)
                    selected_case=body.get('case','latest')
                    if selected_case=='latest':base_path=Path(latest()).with_name('result.json') if latest() else None
                    elif selected_case in saved_cases():base_path=saved_cases()[selected_case][1].with_name('result.json')
                    if not base_path or not base_path.is_file():raise ValueError('기준 계산 결과가 없습니다.')
                    base=json.loads(base_path.read_text('utf-8'))
                    outdoor_ids={f"CAD_{f['name']}_{r['id']}" for f in building['floors'] for r in f['rooms'] if 'outdoor' in r.get('tags',[])}
                    if any(r['id'] in outdoor_ids for r in base['scenario']['rooms']):raise ValueError('테라스 분류 정정 전 계산입니다. 새 구획으로 기준 계산을 먼저 실행하세요.')
                    options=body
                else:options=checked_options(body)
                identity=execution_key(options,sha,engine)
                with lock:
                    if state['busy']:return self.json({'error':'현재 계산이 진행 중입니다'},409)
                    if base_path is None:
                        cached=execution_cache.lookup('native',identity,sha)
                        if cached:
                            destination,record=cached
                            state.update(latest=destination/'playback.json',folder=destination,request_id=identity,cache_hit=True,error=None,kind='run',started=None)
                            return self.json({'request_id':identity,'cache_hit':True,'legacy_key':record.get('old_key'),'solver_runs':0},200)
                    state.update(busy=True,error=None,started=time.monotonic(),folder=None,request_id=identity,kind='ignition' if base_path else 'run',cache_hit=False)
                if base_path:pool.submit(compute_comparison,base_path,options,identity)
                else:pool.submit(compute,options,identity)
                return self.json({'request_id':identity},202)
            except (ValueError,TypeError,json.JSONDecodeError) as exc:return self.json({'error':str(exc)},400)
        def log_message(self,*_):pass

    print(f'http://127.0.0.1:{args.port}/cad-result/{job}/model.html',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()


if __name__=='__main__':main()
