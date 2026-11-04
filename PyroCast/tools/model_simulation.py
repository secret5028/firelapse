"""Building-scoped lite execution for the model library; existing engine unchanged."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid
from copy import deepcopy
from functools import lru_cache
from model_library import ROOT, entries, model_path

sys.path[:0] = [str(ROOT/'simulation'), str(ROOT/'simulation/deps')]
RESULTS = ROOT/'simulation/results/model-library'
PARAMS = dict(remove_cumulative_state=True, smooth_state_bounds=True,
              upper_combustion_enabled=True, door_jet_enabled=True)
STATES = ('open_except_confirmed', 'closed')
_lock = threading.Lock()
_active = None

def read(p):
    return json.loads(Path(p).read_text('utf8'))

def save(p, data):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, allow_nan=False), 'utf8')
    tmp.replace(p)

def entry(ident):
    row = next((r for r in entries() if r['id'] == ident), None)
    if not row or row['source_kind'] != 'cad':
        raise ValueError('스캔·비 CAD 모델은 이 계산 경로를 사용할 수 없습니다')
    if row.get('execution_mode') != 'library_lite':
        raise ValueError('이 건물은 전용 운영 화면의 계산 경로를 사용합니다')
    return row

def fingerprint(ident):
    return hashlib.sha256(model_path(entry(ident)).read_bytes()).hexdigest()

def prepared(ident, floor, digest):
    from pyrocast_lite import fuel_quantity as q
    settings=q.load(digest)
    return _prepared(ident,floor,digest,json.dumps(settings,sort_keys=True))

@lru_cache(maxsize=32)
def _prepared(ident, floor, digest, quantity_json):
    from pyrocast_cfbt.cad import adapt, cad_key
    from pyrocast_cfbt.model import normalize
    from building_rules import usage_class
    from pyrocast_lite import screening_v7 as v7
    from pyrocast_lite.screening_v8_approved import origin_budgets
    path = model_path(entry(ident)); building = read(path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError('건물이 변경되었습니다. 입력을 다시 확인하세요')
    f = next((f for f in building['floors'] if f['name'] == floor), None)
    if not f: raise ValueError('도면에 없는 층')
    candidates = [r for r in f.get('rooms', []) if 'outdoor' not in r.get('tags', []) and r.get('area', 0) > .4]
    if not candidates: raise ValueError('계산 가능한 실이 없는 층')
    raw = adapt(ROOT, dict(building_path=str(path), fire_floor=floor, scope_floor=floor,
                           fire_room=candidates[0]['id'], duration_s=3600))
    table = read(ROOT/'simulation/pyrocast_lite/fire_load_table.json')['classes']
    original = {cad_key(floor, r['id']): r for r in f['rooms']}
    records = {}
    for r in raw['rooms']:
        rid = r['id']; src = original[rid]; cls, evidence = usage_class(src.get('names', []), f.get('use'))
        values = table[cls]; core = bool(r.get('core_kind')); area = r['area_m2']
        from pyrocast_lite.fuel_quantity import ratio
        load = r['fuel_default']['load_MJ_m2'] if core else values['mean']*ratio(json.loads(quantity_json),rid)
        hrrpua = r['fuel_default']['hrrpua_kW_m2'] if core else values['rhrf']
        records[rid] = dict(room=rid, usage_class=cls, label=values['label'],
            classification_basis=evidence, area_m2=area, load_MJ_m2=load,
            hrrpua_kW_m2=hrrpua, coverage=.5, automatic=True)
        if core: continue
        r['fuel_default'].update(usage='passage' if cls=='transport' else cls,
            load_MJ_m2=load, hrrpua_kW_m2=hrrpua, occupancy_fraction=.5,
            basis='building-rules.json classification / fire_load_table.json')
        for g in raw['fuel_groups']:
            if g['room'] != rid: continue
            g.update(energy_MJ=area*load, hrrpua_kW_m2=hrrpua, fuel_area_m2=.5*area, coverage_fraction=.5)
            for u in g.get('fuel_units', []): u['energy_MJ'] = g['energy_MJ']*u['budget_fraction']
    raw = normalize(raw)
    raw['approved_input'] = {'room_uses':records, 'classification':'automatic, not user-approved', 'source_building_sha256':digest,'quantity_settings':json.loads(quantity_json)}
    budgets = origin_budgets(raw); adjusted = deepcopy(raw)
    for g in adjusted['fuel_groups']: g['peak_kW'] = budgets[g['room']]['Q_origin_peak_kW']
    scored = v7.score(adjusted, 1)
    scored['classified_model']['fuel_groups'] = deepcopy(raw['fuel_groups'])
    scored.update(origin_budgets=budgets, revision='model_library_automatic_v1')
    for r in scored['ranked']: r['origin_budget'] = budgets[r['room']]
    return raw, scored

def capabilities(ident):
    row = entry(ident); digest = fingerprint(ident); b = read(model_path(row)); floors = []
    for f in b['floors']:
        item = dict(floor=f['name'], enabled=False, rooms=[], error=None)
        try:
            raw, score = prepared(ident, f['name'], digest)
            item['rooms'] = [dict(id=r['room'], label=f"{f['name']} {r['room'].removeprefix('CAD_'+f['name']+'_')} · {raw['approved_input']['room_uses'][r['room']]['label']}",
                Q_origin_peak_kW=r['origin_budget']['Q_origin_peak_kW'], score=r['score'])
                for r in score['ranked'] if r['origin_budget']['Q_origin_peak_kW'] > 0]
            item['enabled'] = bool(item['rooms'])
            item['error'] = None if item['enabled'] else '연료·개구부 조건을 만족하는 화점 없음'
            item['warnings'] = raw.get('warnings', [])
        except Exception as exc: item['error'] = str(exc)
        floors.append(item)
    return dict(building=ident, building_sha256=digest, floors=floors,
        engine='pyrocast_lite', budget_s=1200, states=list(STATES),
        limits=['단일 층 계산. 수직 전파·창 파괴 OFF.',
                '미확인 연결·용도는 도면 표시와 같은 추정 상태. 자동 용도 분류와 기존 연료표 사용.',
                '강화 기존 운영 화면의 사용자 승인 연료 설정과 별개인 자동 분류 입력입니다.'])

def request_data(body):
    if not isinstance(body, dict) or set(body) != {'building','floor','room','duration_s','opening_state'}:
        raise ValueError('건물·층·화점·시간·개구부 상태를 지정하세요')
    ident = body['building']; entry(ident)
    if type(body['duration_s']) is not int or not 60 <= body['duration_s'] <= 3600 or body['duration_s'] % 10:
        raise ValueError('계산 시간은 60~3600초, 10초 단위')
    if body['opening_state'] not in STATES: raise ValueError('지원하지 않는 개구부 상태')
    digest = fingerprint(ident); raw, score = prepared(ident, body['floor'], digest)
    from pyrocast_lite.screening_v8_approved import scenario
    data = scenario(score, body['room'], body['opening_state'], body['duration_s'])
    data['cad']['fire_key'] = body['room']
    return data, digest

def job_path(ident, job):
    entry(ident)
    if not isinstance(job, str) or len(job)!=32 or any(c not in '0123456789abcdef' for c in job):
        raise ValueError('잘못된 작업 ID')
    path = RESULTS/ident/job
    if not path.is_dir(): raise ValueError('작업 없음')
    return path

def start(body):
    global _active
    data, digest = request_data(body)
    with _lock:
        if _active: raise RuntimeError('계산 중입니다. 직렬 실행만 가능합니다')
        job = uuid.uuid4().hex; folder = RESULTS/body['building']/job
        _active = job
        try:
            save(folder/'input.json', data)
            save(folder/'request.json', {**body, 'building_sha256':digest, 'created_at':time.time()})
            save(folder/'status.json', dict(state='queued', job=job, building=body['building']))
        except Exception:
            _active = None; raise
    threading.Thread(target=_work, args=(folder,), daemon=True).start()
    return dict(job=job, building=body['building'], state='queued')

def _work(folder):
    global _active
    started = time.monotonic()
    try:
        save(folder/'status.json', dict(state='running', job=folder.name, building=folder.parent.name))
        env = {**os.environ, 'OPENBLAS_NUM_THREADS':'1', 'OMP_NUM_THREADS':'1', 'MKL_NUM_THREADS':'1'}
        with (folder/'console.txt').open('w', encoding='utf8') as log:
            subprocess.run([sys.executable,'-B','-X','utf8',str(Path(__file__)),str(folder)],
                cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, check=True,
                timeout=1260, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    except Exception as exc:
        save(folder/'status.json', dict(state='failed', error=str(exc), wall_s=time.monotonic()-started))
    finally:
        with _lock: _active = None

def execute(folder):
    from pyrocast_lite.adapter import prepare
    from pyrocast_lite.runner import run, results
    from pyrocast_lite.visualization import package
    from pyrocast_lite.screening_v8_approved import summarize
    from export_ui_attention import summarize as attention
    start_time = time.perf_counter(); data = read(folder/'input.json'); request = read(folder/'request.json')
    model, manifest = prepare(data, PARAMS); prep = time.perf_counter()-start_time
    save(folder/'rule_manifest.json', manifest)
    run(model, request['duration_s'], 10, 1200, method='BDF')
    result = results(model); save(folder/'result.json', result)
    if not result['ok']:
        save(folder/'status.json', dict(state='failed', error=model.integration['failure'], integration=model.integration)); return
    summary = {**summarize(model,result), **attention(result), 'preprocess_s':prep,
        'integration_s':model.integration['wall_seconds'], 'wall_s':time.perf_counter()-start_time}
    save(folder/'summary.json', summary)
    pb = package(model,result,data,f"{request['floor']} · {request['room']} · {request['opening_state']}")
    for r in pb['rooms']:
        cls = data['approved_input']['room_uses'].get(r['original_room'], {})
        r.update(display_name=cls.get('label','용도 미확인'), approved_fuel_class=cls.get('usage_class'))
    save(folder/'playback.json', pb)
    save(folder/'index-summary.json', attention(result))
    save(folder/'status.json', dict(state='complete', job=folder.name, building=request['building'],
        wall_s=time.perf_counter()-start_time, summary=summary))

if __name__ == '__main__':
    target = Path(sys.argv[1]).resolve()
    if not target.is_relative_to(RESULTS.resolve()): raise ValueError('Output outside model jobs')
    execute(target)
