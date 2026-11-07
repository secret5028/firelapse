"""Building-scoped MC boundary. Uses the existing serial runner unchanged."""
import hashlib, os, re, subprocess, sys, threading, time, uuid
from pathlib import Path
import model_simulation as sim
from result_catalog import read, atomic_json, playback_metadata
from lite_fixed_openings import ranked_samples, worst_state
from lite_mc_service import process_alive
ROOT=sim.ROOT
from runtime_storage import DATA_ROOT, RESULTS, locate, result_glob
JOBS=RESULTS/'lite_mc_jobs/models'

def config_path(ident, *, for_write=False):
    name = sim.fingerprint(ident)+'.json'
    writable = DATA_ROOT/'config/model-fixed-openings'/name
    bundled = ROOT/'simulation/config/model-fixed-openings'/name
    if not for_write and not writable.exists() and bundled.is_file():
        return bundled
    return writable

def fixed_inputs(ident):
    config=read(config_path(ident),{})
    legacy=config.get('fixed_state') or {}
    previous={legacy['source_room']:legacy} if legacy.get('source_room') else {}
    return {**previous, **config.get('fixed_by_room',{})}

def folder_for(ident, job):
    sim.entry(ident)
    if not isinstance(job,str) or not re.fullmatch(r'mc-\d+-[a-f0-9]+',job):raise ValueError('MC 작업 ID 오류')
    return locate(JOBS/ident/job)

def case_id(folder,sample):return 'modelmc-'+folder.name+'-'+sample

def case_folder(ident,case):
    match=re.fullmatch(r'modelmc-(mc-\d+-[a-f0-9]+)-(S\d+)',case or '')
    if not match:raise ValueError('MC 사례 ID 오류')
    folder=folder_for(ident,match[1]);req=read(folder/'request.json',{})
    if req.get('building_sha256')!=sim.fingerprint(ident):raise ValueError('MC 건물 불일치')
    path=folder/match[2]
    if not read(path/'summary.json',{}).get('complete'):raise ValueError('완주하지 않은 표본')
    return path

def folders(ident):
    sha=sim.fingerprint(ident)
    return [p for p in sorted(result_glob(JOBS/ident,'mc-*'),key=lambda p:p.name,reverse=True) if read(p/'request.json',{}).get('building_sha256')==sha]

def status(ident):
    rows=folders(ident)
    if not rows:return dict(available=True,running=False,state='idle',server_busy=bool(sim._active))
    folder=rows[0];req=read(folder/'request.json');value=read(folder/'progress.json',{})
    running=value.get('state') in ('queued','running')
    if running and not process_alive(req.get('owner_pid')):
        value={**value,'state':'interrupted','error':'실행 프로세스 종료 · 자동 재실행 없음'};running=False
    return {**value,'available':True,'running':running,'server_busy':bool(sim._active) and sim._active!=folder.name,
            'id':folder.name,'room':req['room'],'floor':req['floor'],'workers':1,'budget_s_per_sample':1200}

def prepare_request(ident,body):
    if not isinstance(body,dict) or set(body)-{'room','samples','duration_s','seed','manual','floor','selection_mode'}:raise ValueError('MC 요청 형식 오류')
    count=body.get('samples');duration=body.get('duration_s',3600);seed=body.get('seed',20261025);floor=body.get('floor')
    if type(count) is not int or not 2<=count<=1000:raise ValueError('표본 수 2~1000')
    if type(duration) is not int or duration not in (1800,3600):raise ValueError('계산 시간 30분 또는 60분')
    if type(seed) is not int or not 0<=seed<2**32:raise ValueError('seed 범위 오류')
    if not isinstance(floor,str) or not floor:raise ValueError('층 하나를 선택하세요')
    sha=sim.fingerprint(ident);raw,score=sim.prepared(ident,floor,sha)
    eligible=[r for r in score['ranked'] if r['origin_budget']['Q_origin_peak_kW']>0]
    if not eligible:raise ValueError('계산 가능한 화점 없음')
    mode=body.get('selection_mode','score_first')
    if mode not in ('score_first','candidate'):raise ValueError('화점 선택 방식 오류')
    chosen=next((r for r in eligible if r['room']==body.get('room')),None) if mode=='candidate' else eligible[0]
    if chosen is None:raise ValueError('선택 층의 적격 후보실을 선택하세요')
    winner=chosen['room']
    if body.get('room')!=winner:raise ValueError('후보 순위가 변경되었습니다. 새로고침 후 실행하세요')
    # Keep a reproducible stream for each fire room, even on the same floor.
    room_seed=int.from_bytes(hashlib.sha256(f'{sha}:{winner}:{seed}'.encode()).digest()[:4],'big')
    from pyrocast_lite.screening_v8_approved import scenario
    model=scenario(score,winner,'open_except_confirmed',duration)
    model['cad']['fire_key']=winner
    # MC explores new combinations; a prior winner must not lock all openings.
    model.pop('fixed_openings',None)
    request=dict(building=ident,building_sha256=sha,floor=floor,room=winner,samples=count,duration_s=duration,seed=room_seed,seed_base=seed,
                 selection_mode=mode,origin_score=chosen['score'],owner_pid=os.getpid())
    return request,model

def start(ident,body):
    with sim._lock:
        if sim._active or status(ident).get('running'):raise RuntimeError('현재 계산 중입니다. 직렬 실행만 가능합니다')
        req,model=prepare_request(ident,body)
        folder=JOBS/ident/('mc-'+str(time.time_ns())+'-'+uuid.uuid4().hex[:8]);folder.mkdir(parents=True)
        atomic_json(folder/'request.json',req);atomic_json(folder/'input.json',model)
        atomic_json(folder/'progress.json',dict(state='queued',completed=0,total=req['samples']))
        sim._active=folder.name
        threading.Thread(target=compute,args=(folder,),daemon=True).start()
    return dict(started=True,id=folder.name,room=req['room'],workers=1,budget_s_per_sample=1200)

def compute(folder):
    try:
        with (folder/'console.txt').open('w',encoding='utf8') as log:
            subprocess.run([sys.executable,'-B','-X','utf8',str(ROOT/'tools/run_lite_mc.py'),'--request',str(folder/'request.json'),'--out',str(folder)],
                cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if read(folder/'progress.json',{}).get('state')!='completed':raise RuntimeError('완료 기록 없음')
    except Exception as exc:atomic_json(folder/'progress.json',{**read(folder/'progress.json',{}),'state':'failed','error':str(exc)})
    finally:
        with sim._lock:sim._active=None

def summary(ident,room=None,duration_s=None):
    for folder in folders(ident):
        req=read(folder/'request.json');value=read(folder/'mc-summary.json',{})
        if not value or (room and room!=req['room']) or (duration_s is not None and req.get('duration_s')!=duration_s):continue
        value['job_id']=folder.name
        from mc_display_summary import rooms_max
        value['rooms_max']=rooms_max(folder,value['rows'],req['building_sha256'])
        value['source_room']=req['room']
        value['duration_s']=req.get('duration_s')
        for i,row in enumerate(value['rows']):row.update(id=case_id(folder,f'S{i:02d}'),sample_id=f'S{i:02d}')
        try:
            ranking=ranked_samples(folder,req['building_sha256'])
            for row in ranking:row['case_id']=case_id(folder,row['sample_id'])
            value.update(ranking=ranking,worst=ranking[0] if ranking else None)
        except (ValueError,KeyError,OSError) as exc:value.update(worst=None,worst_error=str(exc))
        return value
    return None

def apply(ident,body):
    if not isinstance(body,dict) or set(body)!={'job_id'}:raise ValueError('MC 작업을 지정하세요')
    folder=folder_for(ident,body['job_id'])
    with sim._lock:
        if sim._active:raise RuntimeError('계산 중에는 적용할 수 없습니다')
        fixed=worst_state(folder.name,sim.fingerprint(ident),folder.parent)
        config=read(config_path(ident),{})
        by_room=fixed_inputs(ident)
        by_room[fixed['source_room']]=fixed
        config['fixed_by_room']=by_room
        atomic_json(config_path(ident,for_write=True),config)
    return dict(rows=[],fixed_state=fixed,fixed_by_room=by_room,case_id=case_id(folder,fixed['sample_id']))

def playback(ident,case):
    path=case_folder(ident,case);value=read(path/'playback.json');sample=read(path/'sample.json')
    value['case_id']=case
    value['display_opening_state']=dict(building_sha256=value['building_sha256'],case_id=case,basis='saved_case_input',states={r['id']:r for r in sample['openings']})
    return value

def cases(ident):
    rows=[]
    for folder in folders(ident):
        for p in sorted(folder.glob('S*/summary.json')):
            if re.fullmatch(r'S\d+',p.parent.name) and read(p,{}).get('complete') and (p.parent/'playback.json').is_file():
                req=read(folder/'request.json')
                rows.append(dict(id=case_id(folder,p.parent.name),label=f"{req['floor']} {req['room'].split('_')[-1]} · MC {p.parent.name}",
                                 duration_s=req.get('duration_s'),run_id=folder.name,**playback_metadata(p.parent/'playback.json')))
    return rows
