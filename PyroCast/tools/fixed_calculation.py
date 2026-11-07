"""One calculation of an explicitly fixed MC input, never another MC search."""
from copy import deepcopy
import hashlib
import math
import os
from pathlib import Path
import re
import sys
import threading
import time
import uuid
from result_catalog import read, atomic_json, playback_origin, playback_coverage
from lite_mc_service import process_alive

ROOT = Path(__file__).resolve().parents[1]
from runtime_storage import RESULTS, locate, result_glob
JOBS = RESULTS/'fixed-calculations'
ENGINE = ROOT/'simulation/build/baseline/cfast-baseline.exe'
FIRE_INPUT_KEYS = {'fire_peak_kW', 'fuel_energy_MJ'}


def fingerprint(value):
    return hashlib.sha256(__import__('json').dumps(value, sort_keys=True).encode()).hexdigest()


def context(sha, ident=None, job_id=None, room=None):
    if ident:
        import model_mc
        config = model_mc.config_path(ident)
        jobs = model_mc.JOBS/ident
    else:
        from lite_fixed_openings import CONFIG, JOBS as mc_jobs
        config, jobs = CONFIG, mc_jobs
    if job_id is not None:
        from lite_fixed_openings import worst_state
        fixed = worst_state(job_id, sha, jobs)
    elif ident and room is not None:
        fixed = model_mc.fixed_inputs(ident).get(room)
    else:
        fixed = read(config, {}).get('fixed_state')
    if not fixed or fixed.get('building_sha256') != sha:
        raise ValueError('MC 최악 개폐 상태를 먼저 적용하세요')
    job, sample = fixed.get('job_id', ''), fixed.get('sample_id', '')
    if not re.fullmatch(r'mc-\d+-[a-f0-9]+', job) or not re.fullmatch(r'S\d+', sample):
        raise ValueError('확정 급기 출처 오류')
    folder = locate(jobs/job/sample)
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
    if not isinstance(body, dict) or set(body)-({'mc_job_id'}|FIRE_INPUT_KEYS) != {'engine', 'room', 'floor', 'duration_s'}:
        raise ValueError('계산 방식·화점·층·시간을 지정하세요')
    if body['engine'] not in ('lite', 'cfast'):
        raise ValueError('지원하지 않는 계산 방식')
    if 'mc_job_id' in body and (not ident or not isinstance(body['mc_job_id'], str)):
        raise ValueError('저장 MC 작업 ID 오류')
    folder, fixed, req, model = context(sha, ident, body.get('mc_job_id'), body['room'])
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
    def leakage(inputs):
        return {r['id']:tuple(r.get('leak_area_ratio',(.00017,.000052))) for r in inputs['rooms']}
    if leakage(current)!=leakage(previous):
        raise ValueError('누기 경계 조건이 바뀌었습니다. MC를 다시 실행하세요')
    if body['engine'] == 'cfast' and not ENGINE.is_file():
        raise ValueError('순정 CFAST 실행 파일 없음')
    raw=deepcopy(model)
    if FIRE_INPUT_KEYS & body.keys():
        set_fire_input(raw,body)
    return folder, fixed, req, raw


def set_fire_input(raw, body):
    from pyrocast_cfbt.room_rule_r8 import prepare as native_prepare
    room=body['room']
    source=next((g for g in raw['fuel_groups'] if g['room']==room and 'initial_time_s' in g),None)
    if source is None:
        raise ValueError('선택한 실의 초기 화원 입력이 없습니다.')
    values={}
    for key,maximum in (('fuel_energy_MJ',1e9),('fire_peak_kW',1e6)):
        if key not in body:
            continue
        value=body[key]
        if type(value) not in (int,float) or not math.isfinite(value) or not 0<value<=maximum:
            raise ValueError('가연물 총량과 화원 최대 발열률은 양수여야 합니다.')
        values[key]=value
    energy=values.get('fuel_energy_MJ',source['energy_MJ'])
    peak=values.get('fire_peak_kW')
    if peak is not None:
        _,_,manifest=native_prepare(raw)
        source['peak_kW']=peak/manifest['initial_source']['area_fraction']
    source['energy_MJ']=energy
    for unit in source.get('fuel_units',[]):
        unit['energy_MJ']=energy*unit['budget_fraction']
    use=raw.get('approved_input',{}).get('room_uses',{}).get(room)
    if use:
        load=energy/use['area_m2']
        use['load_MJ_m2']=load
        if 'fuel_setting' in use:
            use['fuel_setting']['load']=load
        comp=next(r for r in raw['rooms'] if r['id']==room)
        comp['fuel_default']['load_MJ_m2']=load
        budget=raw.get('screening_source',{}).get('origin_budget')
        if budget:
            budget.update(energy_MJ=energy,fuel_load_MJ_m2=load,classification=use)
            if peak is not None:
                budget.update(Q_origin_peak_kW=source['peak_kW'],input_peak_used=True)
    if peak is not None:
        _,_,manifest=native_prepare(raw)
        cell=manifest['initial_source']['room']
        applied=manifest['supplies'][cell]['scaled_peak_kW']
        if not math.isclose(peak,applied,rel_tol=1e-8):
            raise ValueError(f'이 가연물과 화원 면적에서 적용 가능한 최대 발열률은 {applied/1000:.2f} MW입니다.')
    raw['fire_input']=dict(room_id=room,fuel_energy_MJ=energy,requested_peak_kW=peak)


def fire_details(raw, manifest, playback):
    cell=playback['fire_key']
    room=playback_origin(playback)
    input_values=raw.get('fire_input',{})
    fuel=next((g for g in raw.get('fuel_groups',[]) if g['room']==room and 'initial_time_s' in g),{})
    actual=[q for q in playback['solvers'].get(cell,{}).get('Qsolid_kW',[]) if q is not None]
    return dict(room_id=room,cell_id=cell,fuel_energy_MJ=fuel.get('energy_MJ'),
                requested_peak_kW=input_values.get('requested_peak_kW'),
                prescribed_peak_kW=manifest.get('supplies',{}).get(cell,{}).get('scaled_peak_kW'),
                actual_peak_kW=max(actual,default=None),vehicle_count=input_values.get('vehicle_count'))


def paths(sha):
    return sorted(result_glob(JOBS/sha,'calc-*'), key=lambda p:p.name, reverse=True)


def status(sha):
    rows = paths(sha)
    value = read(rows[0]/'status.json', {}) if rows else {'state': 'idle'}
    running = value.get('state') in ('queued', 'running')
    if running and not process_alive(value.get('owner_pid')):
        value = {**value, 'state': 'interrupted', 'error': '계산 프로세스 종료 · 자동 재실행 없음'}
        running = False
    return {**value, 'available': True, 'cfast_available': ENGINE.is_file(), 'running': running}


def cases(sha):
    rows = []
    for p in paths(sha):
        if read(p/'status.json', {}).get('state') != 'complete' or not (p/'playback.json').is_file(): continue
        data = read(p/'playback.json')
        rows.append(dict(id=p.name, label=data['label'], engine_kind=data.get('engine_kind'),
                         origin_room_id=playback_origin(data), complete=data.get('complete') is True,
                         covered_room_ids=playback_coverage(data),
                         duration_s=(data.get('time_s') or [None])[-1],
                         saved_at_ms=int((p/'playback.json').stat().st_mtime*1000), run_id=p.name))
    return rows


def playback_file(sha, case):
    if not re.fullmatch(r'calc-\d+-[a-f0-9]+', case or ''):
        raise ValueError('계산 사례 ID 오류')
    folder = locate(JOBS/sha/case)
    if read(folder/'status.json', {}).get('state') != 'complete':
        raise ValueError('완료되지 않은 계산')
    return folder/'playback.json'


def playback(sha, case):
    file=playback_file(sha,case)
    value = read(file)
    if value['building_sha256'] != sha:
        raise ValueError('다른 건물의 결과')
    if value.get('native_mapping')=='fixed-r8-native-v1':
        from fixed_native_playback import restore_smoke
        try:
            restore_smoke(value,file.parent)
        except (OSError,ValueError,KeyError):
            value.setdefault('limits',[]).append('저장된 CFAST 원본 CSV의 연기 광학밀도를 확인할 수 없습니다.')
    if 'fire_input' not in value:
        value['fire_input']=fire_details(read(file.with_name('input.json'),{}),
                                         read(file.with_name('rule_manifest.json'),{}),value)
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
        if req['engine'] == 'lite' and FIRE_INPUT_KEYS.isdisjoint(req):
            pb = read(source/'playback.json')
            if not pb or not pb.get('complete'):
                raise ValueError('확정 표본의 완료 결과 없음')
            runs = 0
        elif req['engine']=='lite':
            from model_simulation import PARAMS
            from pyrocast_lite.adapter import prepare as lite_prepare
            from pyrocast_lite.runner import run, results
            from pyrocast_lite.visualization import package
            model,manifest=lite_prepare(raw,PARAMS)
            atomic_json(folder/'rule_manifest.json',manifest)
            run(model,req['duration_s'],10,1200,method='BDF')
            if not model.integration['complete']:
                raise ValueError(model.integration['failure'])
            result=results(model)
            atomic_json(folder/'result.json',result)
            pb=package(model,result,raw,'간략 계산')
            runs=1
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
        manifest=read(folder/'rule_manifest.json') or read(source/'BDF/rule_manifest.json') or {}
        pb['fire_input']=fire_details(raw,manifest,pb)
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
