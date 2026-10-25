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
from urllib.parse import urlsplit,unquote

ROOT=Path(__file__).resolve().parents[1]
SIM=ROOT/'simulation'
sys.path.insert(0,str(SIM))
from pyrocast_cfbt.cad import adapt,resolve_building
from pyrocast_cfbt.playback import package
from pyrocast_cfbt.spread import simulate
from pyrocast_cfbt.comparison import compare_ignition,comparison_key


def execution_key(options,building_sha,engine):
    """Reuse verified native outputs only for identical code, engine and inputs."""
    implementation=hashlib.sha256()
    for path in [Path(__file__),*sorted((SIM/'pyrocast_cfbt').glob('*.py'))]:
        implementation.update(path.name.encode());implementation.update(path.read_bytes())
    for path in [*sorted((SIM/'data').glob('*.json')), *sorted((SIM/'extensions/thermal').glob('*.c')), *list((SIM/'build').glob('plate.dll'))]:
        implementation.update(path.name.encode());implementation.update(path.read_bytes())
    payload={'options':options,'building_sha256':building_sha,
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
    saved_cases={'spread60uniform':('균등 바닥 연료 · 통로 적치 가정 · 3F 1시간 전파 탐색',(watch/'playback.json') if watch else SIM/'results/floor_spread_20261022/r4_uniform_bounded/playback.json'),
                 'mixture60v7':('고연료 1시간 · 테라스 정정 전 계산 · 실내 표시 30실',SIM/'results/mixture_r2_20261022/enriched_floor60_v7/playback.json'),
                 'mixture60v1':('혼합물 · 1시간 전파 탐색 v1 · 2실 연소',SIM/'results/mixture_r2_20261022/enriched_floor60/playback.json'),
                 'compare30legacy':('동일 조건 비교 · 기존 방식 · 3F 30분',SIM/'results/mixture_r2_20261022/cad30_view_legacy/playback.json'),
                 'compare30mixture':('동일 조건 비교 · 혼합물 방식 · 3F 30분',SIM/'results/mixture_r2_20261022/cad30_view_mixture/playback.json'),
                 'topology30':('3F 연결 보정 · 31실 · 30분',SIM/'results/topology_audit_20261022/floor_corrected_30min/playback.json'),
                 'vertical30':('화재층 + 전층 코어·출입 공간 · 82구획 · 30분',SIM/'results/topology_audit_20261022/vertical_corrected_30min/playback.json'),
                 'windows30':('연결 보정 전 · 3F 31실 · 30분 · 창 평가',SIM/'results/window_r8_20261022/floor_windows_30min/playback.json'),
                 'windows60':('3F 전체 31실 · 1시간 · 창 파괴 평가 450℃',SIM/'results/window_r8_20261022/floor_windows_60min/playback.json'),
                 'windows60vent':('3F 전체 31실 · 1시간 · 외기 창 초기 50% 개방',SIM/'results/window_r8_20261022/floor_windows_60min_ventilated/playback.json'),
                 'conditions_v1':('조건표·개구부/상층 표시 분리 · 기존 3실 계산',SIM/'results/condition_display_v1/playback.json'),
                 'floor_smoke':('연결층 전체 연기 · 화원/FO 시각 지정',SIM/'results/cad_floor_smoke_v5_prescribed/playback.json'),
                 'exterior_demo':('R25 휴게실→홀2·홀3 · 반자고3m · 연료 가산 · 계단 제외',SIM/'results/cad_exterior_risk_demo_v4_ceiling/playback.json'),
                 'practical30':('실용 탐색 · 30분 · 용도별 대표 연료',SIM/'results/cad_practical_30min/playback.json'),
                 'opening30':('개구부 후보 · 30분 · 고체 45℃ 가정',SIM/'results/cad_opening_30min/playback.json'),
                 'floor':('이전 15분 · 화재층 기본값 · 대표점',SIM/'results/cad_floor/playback.json'),
                 'building':('이전 15분 · 연결 건물 기본값 · 대표점',SIM/'results/cad_whole_verified/playback.json'),
                 'test45':('이전 15분 · 고체 45℃ 시험 · 대표점',SIM/'results/cad_low_threshold/playback.json')}
    def latest():
        with lock:
            path=state['latest'] or (args.result if args.result.is_file() else SIM/'results/cad_floor_smoke_v5_prescribed/playback.json')
            if not state['latest'] and watch and (watch/'playback.json').is_file():
                try:
                    candidate=json.loads((watch/'playback.json').read_text('utf-8'))
                    if candidate.get('complete') and candidate.get('building_sha256')==sha:path=watch/'playback.json'
                except (OSError,ValueError):pass
            if not Path(path).is_file():return None
            try:
                if json.loads(Path(path).read_text('utf-8')).get('building_sha256')!=sha:return None
            except (OSError,ValueError):return None
            return path
    def compute(options,identity):
        destination=SIM/'results/cad_interactive'/identity
        try:
            scenario=adapt(project,{**options,'building_path':str(source)});destination.mkdir(parents=True,exist_ok=True)
            (destination/'scenario.json').write_text(json.dumps(scenario,ensure_ascii=False,indent=2),encoding='utf-8')
            with lock:state['folder']=destination
            result=simulate(scenario,engine if engine.is_file() else SIM/'build/cfbt/cfast-cfbt.exe',destination)
            payload=package(result);output=destination/'playback.json'
            tmp=output.with_suffix('.tmp');tmp.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':'),allow_nan=False),encoding='utf-8');tmp.replace(output)
            with lock:state['latest']=output
        except Exception as exc:
            with lock:state['error']=str(exc)
        finally:
            with lock:state['busy']=False

    def compute_r8(options,rule_options,compare,identity):
        nonlocal r8_folder
        destination=SIM/'results/cad_r8_review'/identity
        try:
            from run_room_rule_r8 import run_batch
            raw=adapt(project,{**options,'building_path':str(source)})
            with lock:state['folder']=destination;r8_folder=destination
            run_batch(raw,destination,rule_options,compare)
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
            destination=SIM/'results/cad_ignition_comparisons'/key[:24]
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

    class Handler(BaseHTTPRequestHandler):
        def send_data(self,data,mime='application/json; charset=utf-8',code=200):
            compressed=(len(data)>65536 and mime.startswith('application/json') and
                        'gzip' in self.headers.get('Accept-Encoding','').lower())
            if compressed:data=gzip.compress(data,compresslevel=1,mtime=0)
            self.send_response(code);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)))
            if compressed:self.send_header('Content-Encoding','gzip');self.send_header('Vary','Accept-Encoding')
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(data)
        def json(self,value,code=200):return self.send_data(json.dumps(value,ensure_ascii=False).encode(),'application/json; charset=utf-8',code)
        def do_GET(self):
            path=unquote(urlsplit(self.path).path);prefix='/cad-result/'+job+'/'
            if path==prefix+'building.json':return self.json(building)
            if path=='/':
                self.send_response(302);self.send_header('Location',prefix+'model.html');self.end_headers();return
            if path=='/cfbt/model-info':
                return self.json({'building_sha256':sha,'floors':[{'name':f['name'],'rooms':[{'id':r['id'],'area_m2':r.get('area',0)} for r in f['rooms'] if 'outdoor' not in r.get('tags',[])]} for f in building['floors'] if f.get('rooms')]})
            if path=='/cfbt/cases':
                return self.json([{'id':key,'label':label} for key,(label,file) in saved_cases.items() if file.is_file() and json.loads(file.read_text('utf-8')).get('building_sha256')==sha])
            if path.startswith('/cfbt/case/'):
                key=path[len('/cfbt/case/'):]
                if key not in saved_cases or not saved_cases[key][1].is_file():return self.send_error(404)
                if json.loads(saved_cases[key][1].read_text('utf-8')).get('building_sha256')!=sha:return self.send_error(404)
                return self.json(present_playback(json.loads(saved_cases[key][1].read_text('utf-8'))))
            if path=='/cfbt/r8/schema':
                from pyrocast_cfbt.rule_settings import schema
                return self.json(schema())
            if path=='/cfbt/lite/doors':
                from pyrocast_lite.door_classification import classify_doors
                raw=json.loads((SIM/'results/room_rule_r8_20261025/source-scenario.json').read_text('utf-8'))
                saved=SIM/'config/lite-door-overrides.json'
                overrides=json.loads(saved.read_text('utf-8')) if saved.exists() else {}
                return self.json(classify_doors(raw,overrides)[1])
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
                if path.endswith('catalog.json'):
                    return self.json({k:v for k,v in cfg.items() if k!='active_path'})
                chosen=cfg.get('active_path') if path.endswith('active.json') else next((x['path'] for x in cfg.get('cases',[]) if x['id']==path.rsplit('/',1)[-1]),None)
                if not chosen:return self.json({'error':'Unknown lite case'},404)
                file=Path(chosen).resolve()
                if not file.is_relative_to((SIM/'results').resolve()) or not file.is_file():return self.json({'error':'Invalid lite path'},404)
                payload=json.loads(file.read_text('utf-8'))
                if payload.get('building_sha256')!=sha:return self.json({'error':'Different building'},400)
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
            if path in ('/cfbt/overlay.js','/cfbt/overlay.css','/cfbt/legacy_real_view.js','/cfbt/legacy_real_bridge.js','/cfbt/risk.js','/cfbt/gas_visual.js','/cfbt/smoke_visual.js','/cfbt/smoke_transport.js','/cfbt/ceiling_jets.js','/cfbt/frozen_rule_controls.js','/cfbt/lite_doors.js','/cfbt/screening.js','/cfbt/lite_viewer.js'):
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
        def do_POST(self):
            nonlocal r8_folder
            request_path=urlsplit(self.path).path
            if request_path not in ('/cfbt/run','/cfbt/ignite','/cfbt/r8/run','/cfbt/lite/doors','/cfbt/lite/screening'):return self.json({'error':'지원하지 않는 요청입니다'},405)
            if self.headers.get('Origin') not in (None,'http://'+self.headers.get('Host','')):return self.json({'error':'외부 요청 차단'},403)
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=100000:raise ValueError('요청 크기 오류')
                body=json.loads(self.rfile.read(length));base_path=None
                if request_path=='/cfbt/lite/screening':
                    import lite_screening_service as screening
                    if not isinstance(body,dict) or set(body)-{'top_n','mc_room','run'}:raise ValueError('후보 선택 요청 오류')
                    if type(body.get('run',False)) is not bool:raise ValueError('run은 참/거짓입니다')
                    with lock:
                        external=screening.payload().get('progress') or {}
                        if state['busy'] or external.get('state')=='running':return self.json({'error':'현재 계산 중입니다. 완료 후 선택하세요.'},409)
                        data=screening.select(body.get('top_n'),body.get('mc_room'))
                        if not body.get('run'):return self.json(data)
                        state.update(busy=True,kind='lite_screening',error=None,started=time.monotonic())
                    def work():
                        try:screening.compute(body['top_n'])
                        except Exception as exc:
                            with lock:state['error']=str(exc)
                        finally:
                            with lock:state['busy']=False
                    pool.submit(work)
                    return self.json({'started':True,'workers':1,'MC_started':False},202)
                if request_path=='/cfbt/lite/doors':
                    from pyrocast_lite.door_classification import classify_doors
                    if not isinstance(body,dict) or set(body)!={'id','door_class'}:raise ValueError('문 분류 요청 오류')
                    raw=json.loads((SIM/'results/room_rule_r8_20261025/source-scenario.json').read_text('utf-8'))
                    saved=SIM/'config/lite-door-overrides.json'
                    with lock:
                        overrides=json.loads(saved.read_text('utf-8')) if saved.exists() else {}
                        overrides[body['id']]=body['door_class']
                        _,report=classify_doors(raw,overrides)
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
                        destination=SIM/'results/cad_r8_review'/identity
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
                    elif selected_case in saved_cases:base_path=saved_cases[selected_case][1].with_name('result.json')
                    if not base_path or not base_path.is_file():raise ValueError('기준 계산 결과가 없습니다.')
                    base=json.loads(base_path.read_text('utf-8'))
                    outdoor_ids={f"CAD_{f['name']}_{r['id']}" for f in building['floors'] for r in f['rooms'] if 'outdoor' in r.get('tags',[])}
                    if any(r['id'] in outdoor_ids for r in base['scenario']['rooms']):raise ValueError('테라스 분류 정정 전 계산입니다. 새 구획으로 기준 계산을 먼저 실행하세요.')
                    options=body
                else:options=checked_options(body)
                identity=execution_key(options,sha,engine)
                with lock:
                    if state['busy']:return self.json({'error':'현재 계산이 진행 중입니다'},409)
                    state.update(busy=True,error=None,started=time.monotonic(),folder=None,request_id=identity,kind='ignition' if base_path else 'run',cache_hit=False)
                if base_path:pool.submit(compute_comparison,base_path,options,identity)
                else:pool.submit(compute,options,identity)
                return self.json({'request_id':identity},202)
            except (ValueError,TypeError,json.JSONDecodeError) as exc:return self.json({'error':str(exc)},400)
        def log_message(self,*_):pass

    print(f'http://127.0.0.1:{args.port}/cad-result/{job}/model.html',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()


if __name__=='__main__':main()
