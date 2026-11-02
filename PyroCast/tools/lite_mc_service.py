"""CLI job adapter; shares the server's single-worker admission lock."""
import os
from lite_fixed_openings import classifications, apply_fixed, ranked_samples
from pathlib import Path
import subprocess
import sys
import time
import uuid
from result_catalog import read, atomic_json

ROOT=Path(__file__).resolve().parents[1];RESULTS=ROOT/'simulation/results'
JOBS=RESULTS/'lite_mc_jobs';LATEST=JOBS/'latest.json'


def process_alive(pid):
    if not isinstance(pid,int) or pid<=0:return False
    if os.name=='nt':
        import ctypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.restype=ctypes.c_void_p
        kernel.GetExitCodeProcess.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]
        kernel.CloseHandle.argtypes=[ctypes.c_void_p]
        handle=kernel.OpenProcess(0x1000,False,pid)
        if not handle:return False
        code=ctypes.c_ulong()
        try:return bool(kernel.GetExitCodeProcess(handle,ctypes.byref(code))) and code.value==259
        finally:kernel.CloseHandle(handle)
    try:os.kill(pid,0);return True
    except OSError:return False


def status(building_sha):
    ref=read(LATEST,{})
    folder=JOBS/ref.get('id','missing')
    if not folder.resolve().is_relative_to(JOBS.resolve()):return {'state':'idle','running':False}
    req=read(folder/'request.json',{})
    if req.get('building_sha256')!=building_sha:return {'state':'idle','running':False}
    progress=read(folder/'progress.json',{'state':'queued','completed':0,'total':req['samples']})
    running=progress.get('state') in ('queued','running')
    if running and not process_alive(ref.get('pid')) and not process_alive(ref.get('owner_pid')):
        progress={**progress,'state':'interrupted','error':'MC 실행 프로세스가 종료되었습니다. 자동 재실행하지 않습니다.'};running=False
        atomic_json(folder/'progress.json',progress)
    return {**progress,'id':ref['id'],'room':req['room'],'running':running,'workers':1,'budget_s_per_sample':1200}


def prepare_request(body, building_sha):
    if not isinstance(body,dict) or set(body)-{'room','samples','duration_s','seed','manual'}:raise ValueError('MC 요청 형식 오류')
    count=body.get('samples');duration=body.get('duration_s',3600);seed=body.get('seed',20261025)
    if type(count) is not int or not 2<=count<=1000:raise ValueError('MC 표본 수는 필수 2표본을 포함한 2~1000 정수입니다')
    if type(duration) is not int or duration not in (1800,3600):raise ValueError('MC 시간은 30분 또는 1시간입니다')
    if type(seed) is not int or not 0<=seed<2**32:raise ValueError('seed 범위 오류')
    raw=read(RESULTS/'room_rule_r8_20261025/source-scenario.json')
    if raw['cad']['building_sha256']!=building_sha:raise ValueError('이 건물의 간략 입력이 없습니다')
    from pyrocast_lite.screening_v8_approved import score,scenario
    config=read(ROOT/'simulation/config/lite-door-overrides.json',{})
    scored=score(raw,1,door_overrides=classifications(config))
    room=body.get('room')
    manual=body.get('manual',False)
    if type(manual) is not bool:raise ValueError('manual은 참/거짓입니다')
    if manual:
        from lite_manual_origin import manual_scenario
        model=manual_scenario(scored,room,'open_except_confirmed',duration=duration)
    else:
        if room not in {r['room'] for r in scored['ranked']}:raise ValueError('적격 화점실을 선택하세요')
        model=scenario(scored,room,'open_except_confirmed',duration=duration)
    apply_fixed(model,config)
    # Screening replaces the initial fuel group; keep copied CAD metadata in sync too.
    model['cad']['fire_key']=room
    return dict(room=room,samples=count,duration_s=duration,seed=seed,building_sha256=building_sha,manual=manual),model


def reserve(request, model):
    folder=JOBS/('mc-'+str(time.time_ns())+'-'+uuid.uuid4().hex[:8]);folder.mkdir(parents=True)
    atomic_json(folder/'request.json',request);atomic_json(folder/'input.json',model)
    atomic_json(folder/'progress.json',{'state':'queued','completed':0,'total':request['samples']})
    atomic_json(LATEST,{'id':folder.name,'owner_pid':os.getpid()})
    return folder


def compute(folder):
    with (folder/'console.txt').open('w',encoding='utf-8') as log:
        try:
            process=subprocess.Popen([sys.executable,'-X','utf8',str(ROOT/'tools/run_lite_mc.py'),'--request',str(folder/'request.json'),'--out',str(folder)],
                cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            atomic_json(LATEST,{'id':folder.name,'owner_pid':os.getpid(),'pid':process.pid})
            code=process.wait()
            if code:raise RuntimeError(f'MC CLI 종료 코드 {code}')
            if read(folder/'progress.json',{}).get('state')!='completed':raise RuntimeError('MC CLI 완료 기록 없음')
        except Exception as exc:
            atomic_json(folder/'progress.json',{**read(folder/'progress.json',{}),'state':'failed','error':str(exc)})
            raise


def summary(building_sha, room=None):
    for folder in sorted(JOBS.glob('mc-*'),reverse=True):
        if folder.is_symlink():continue
        data=read(folder/'mc-summary.json')
        if data and data.get('building_sha256')==building_sha and (room is None or data.get('source_room')==room):
            try:
                ranking=ranked_samples(folder,building_sha)
                data.update(job_id=folder.name,ranking=ranking,worst=ranking[0] if ranking else None)
            except (OSError,ValueError,KeyError,TypeError) as exc:data.update(worst=None,worst_error=str(exc))
            return data
    return None
