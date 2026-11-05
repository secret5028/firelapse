"""One calculation of an explicitly fixed MC input, never another MC search."""
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import re
import sys
import threading
import time
import uuid
from result_catalog import read, atomic_json
from lite_mc_service import process_alive

ROOT = Path(__file__).resolve().parents[1]
JOBS = ROOT/'simulation/results/fixed-calculations'
ENGINE = ROOT/'simulation/build/baseline/cfast-baseline.exe'


def fingerprint(value):
    return hashlib.sha256(__import__('json').dumps(value, sort_keys=True).encode()).hexdigest()


def context(sha, ident=None):
    if ident:
        import model_mc
        config = model_mc.config_path(ident)
        jobs = model_mc.JOBS/ident
    else:
        from lite_fixed_openings import CONFIG, JOBS as mc_jobs
        config, jobs = CONFIG, mc_jobs
    fixed = read(config, {}).get('fixed_state')
    if not fixed or fixed.get('building_sha256') != sha:
        raise ValueError('MC 최악 개폐 상태를 먼저 적용하세요')
    job, sample = fixed.get('job_id', ''), fixed.get('sample_id', '')
    if not re.fullmatch(r'mc-\d+-[a-f0-9]+', job) or not re.fullmatch(r'S\d+', sample):
        raise ValueError('확정 급기 출처 오류')
    folder = jobs/job/sample
    saved = read(folder/'sample.json')
    if not saved or not read(folder/'summary.json', {}).get('complete'):
        raise ValueError('완료된 MC 표본이 없습니다')
    if fingerprint(saved) != fixed.get('sample_sha256'):
        # apply_worst uses execution_evidence.digest's canonical encoding.
        from execution_evidence import digest
        if digest(saved) != fixed.get('sample_sha256'):
            raise ValueError('확정 표본의 저장 증거가 변경되었습니다')
    model = saved['scenario']
    from lite_fixed_openings import fixed_for
    fixed_for(model, {'fixed_state': fixed})
    for vent in model['openings']:
        if vent['schedule'] != [[0., fixed['states'][vent['id']]['effective_fraction']]]:
            raise ValueError('확정 개방률과 저장 입력 불일치')
    request = read(folder.parent/'request.json')
    return folder, fixed, request, model


def prepare(sha, body, ident=None):
    if not isinstance(body, dict) or set(body) != {'engine', 'room', 'floor', 'duration_s'}:
        raise ValueError('계산 방식·화점·층·시간을 지정하세요')
    if body['engine'] not in ('lite', 'cfast'):
        raise ValueError('지원하지 않는 계산 방식')
    folder, fixed, req, model = context(sha, ident)
    if body['room'] != req['room'] or body['room'] != fixed['source_room']:
        raise ValueError('화점이 변경되었습니다. 해당 화점의 MC 급기를 확정하세요')
    if not isinstance(body['floor'], str) or not body['room'].startswith('CAD_'+body['floor']+'_'):
        raise ValueError('확정 화점의 층을 선택하세요')
    if type(body['duration_s']) is not int or body['duration_s'] != req['duration_s']:
        raise ValueError('확정 표본과 계산 시간이 다릅니다. MC를 다시 실행하세요')
    # Never silently use a stale fuel setting when switching engines.
    if ident:
        import model_mc
        _, current = model_mc.prepare_request(ident, dict(room=body['room'], floor=body['floor'],
            duration_s=body['duration_s'], samples=2, selection_mode='candidate'))
    else:
        import lite_mc_service
        _, current = lite_mc_service.prepare_request(dict(room=body['room'], floor=body['floor'],
            duration_s=body['duration_s'], samples=2, selection_mode='candidate'), sha)
    previous = read(folder.parent/'input.json')
    for key in ('approved_input', 'fuel_groups'):
        if current.get(key) != previous.get(key):
            raise ValueError('가연물 설정이 바뀌었습니다. MC를 다시 실행하세요')
    if body['engine'] == 'cfast' and not ENGINE.is_file():
        raise ValueError('순정 CFAST 실행 파일 없음')
    return folder, fixed, req, deepcopy(model)


def paths(sha):
    return sorted((JOBS/sha).glob('calc-*'), reverse=True)


def status(sha):
    rows = paths(sha)
    value = read(rows[0]/'status.json', {}) if rows else {'state': 'idle'}
    running = value.get('state') in ('queued', 'running')
    if running and not process_alive(value.get('owner_pid')):
        value = {**value, 'state': 'interrupted', 'error': '계산 프로세스 종료 · 자동 재실행 없음'}
        running = False
    return {**value, 'available': True, 'cfast_available': ENGINE.is_file(), 'running': running}


def cases(sha):
    return [dict(id=p.name, label=read(p/'playback.json')['label']) for p in paths(sha)
            if read(p/'status.json', {}).get('state') == 'complete' and (p/'playback.json').is_file()]


def playback(sha, case):
    if not re.fullmatch(r'calc-\d+-[a-f0-9]+', case or ''):
        raise ValueError('계산 사례 ID 오류')
    folder = JOBS/sha/case
    if read(folder/'status.json', {}).get('state') != 'complete':
        raise ValueError('완료되지 않은 계산')
    value = read(folder/'playback.json')
    if value['building_sha256'] != sha:
        raise ValueError('다른 건물의 결과')
    return value


def reserve(sha, body, ident=None):
    source, fixed, req, raw = prepare(sha, body, ident)
    folder = JOBS/sha/('calc-'+str(time.time_ns())+'-'+uuid.uuid4().hex[:8])
    evidence = dict(**body, building_sha256=sha, source_job=fixed['job_id'],
        source_sample=fixed['sample_id'], source_path=str(source), input_sha256=fingerprint(raw),
        owner_pid=os.getpid(), automatic_retry=False, started_at_ms=int(time.time()*1000))
    atomic_json(folder/'request.json', evidence)
    atomic_json(folder/'input.json', raw)
    atomic_json(folder/'fixed-state.json', fixed)
    atomic_json(folder/'status.json', dict(state='queued', id=folder.name, **evidence))
    return folder


def compute(folder):
    started = time.monotonic()
    req = read(folder/'request.json'); raw = read(folder/'input.json')
    source = Path(req['source_path'])
    try:
        atomic_json(folder/'status.json', dict(state='running', id=folder.name, **req))
        if req['engine'] == 'lite':
            pb = read(source/'playback.json')
            if not pb or not pb.get('complete'):
                raise ValueError('확정 표본의 완료 결과 없음')
            runs = 0
        else:
            from pyrocast_cfbt.room_rule_r8 import prepare as native_prepare
            from pyrocast_cfbt.deck import make_deck, window_targets
            from pyrocast_cfbt.native import execute, digest
            from fixed_native_playback import package
            model, targets, manifest = native_prepare(raw)
            if window_targets(model):
                raise ValueError('확정 급기는 창 파괴를 실행하지 않습니다')
            deck = make_deck(model, [], targets)
            if '&CFBT' in deck:
                raise ValueError('순정 CFAST 입력이 아닙니다')
            atomic_json(folder/'scenario.json', model)
            atomic_json(folder/'rule_manifest.json', manifest)
            atomic_json(folder/'execution-evidence.json', dict(**req, engine_sha256=digest(ENGINE),
                rule_settings=model.get('rule_settings'), fixed_openings=read(folder/'fixed-state.json'),
                native_budget_s=1800, trigger='native r8 plate sensor'))
            native = execute(ENGINE, folder, deck, '', model['duration_s'], 1800, stall_timeout_s=0)
            pb = package(model, native, read(source/'playback.json'), folder)
            runs = 1
        pb['case_id'] = folder.name
        pb['label'] = f"{req['floor']} {req['room'].split('_')[-1]} · {'순정 CFAST' if req['engine']=='cfast' else '간략 계산'} · 확정 급기"
        fixed = read(folder/'fixed-state.json')
        pb['display_opening_state'] = dict(building_sha256=req['building_sha256'], case_id=folder.name,
            basis='saved_case_input', states=fixed['states'])
        atomic_json(folder/'playback.json', pb)
        atomic_json(folder/'status.json', dict(state='complete', id=folder.name, **req,
            wall_s=time.monotonic()-started, solver_runs=runs, case_id=folder.name))
    except Exception as exc:
        atomic_json(folder/'status.json', dict(state='failed', id=folder.name, **req,
            wall_s=time.monotonic()-started, error=str(exc)))


def start_model(ident, body):
    import model_simulation as sim
    import model_mc
    sha = sim.fingerprint(ident)
    with sim._lock:
        if sim._active or model_mc.status(ident).get('running') or status(sha)['running']:
            raise RuntimeError('현재 계산 중입니다. 직렬 실행만 가능합니다')
        folder = reserve(sha, body, ident)
        sim._active = folder.name
        def work():
            try: compute(folder)
            finally:
                with sim._lock: sim._active = None
        threading.Thread(target=work, daemon=True).start()
    return dict(started=True, id=folder.name)
