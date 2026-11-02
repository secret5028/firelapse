"""C-5 input boundary: saved MC states override future inputs, never playback.

Classification corrections retain their historical flat format. fixed_state is
reserved metadata and is never passed to the simulation classification engine.
"""
from copy import deepcopy
import math
import re
from pathlib import Path
from result_catalog import read, atomic_json

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT/'simulation/config/lite-door-overrides.json'
JOBS = ROOT/'simulation/results/lite_mc_jobs'


def classifications(value):
    return {k: v for k, v in (value or {}).items() if k != 'fixed_state'}


def fixed_for(model, config):
    fixed = (config or {}).get('fixed_state')
    if not fixed:
        return None
    if fixed['building_sha256'] != model['cad']['building_sha256']:
        raise ValueError('확정 급기 상태의 건물이 다릅니다. 해제 후 다시 지정하세요.')
    vents = {v['id']: v for v in model['openings']}
    if set(fixed['states']) != set(vents):
        raise ValueError('확정 급기 개구부 목록이 변경됐습니다. 해제 후 다시 지정하세요.')
    for key, item in fixed['states'].items():
        fraction = item['effective_fraction']
        if (type(item['open']) is not bool or type(fraction) not in (int, float)
                or not math.isfinite(fraction) or not 0 <= fraction <= 1
                or (item['a'], item['b']) != (vents[key]['a'], vents[key]['b'])):
            raise ValueError('확정 개구부 상태가 유효하지 않습니다: '+key)
    return deepcopy(fixed)


def apply_fixed(model, config):
    fixed = fixed_for(model, config)
    if fixed:
        for vent in model['openings']:
            vent['schedule'] = [[0., fixed['states'][vent['id']]['effective_fraction']]]
        model['fixed_openings'] = fixed
    return model


def sample_fixed_states(model):
    fixed = fixed_for(model, {'fixed_state': model.get('fixed_openings')})
    return {key: item['open'] for key, item in fixed['states'].items()} if fixed else None


def ranked_samples(folder, building_sha):
    folder = Path(folder).resolve()
    request = read(folder/'request.json', {})
    if request.get('building_sha256') != building_sha:
        raise ValueError('MC 건물 불일치')
    if read(folder/'progress.json', {}).get('state') != 'completed':
        raise ValueError('완료된 MC 작업만 적용할 수 있습니다')
    from export_ui_attention import result_index
    rows = []
    for path in sorted(folder.glob('S[0-9]*/summary.json')):
        if not re.fullmatch(r'S\d+', path.parent.name):
            continue
        value = read(path, {})
        if not value.get('complete'):
            continue
        index = result_index(path.with_name('result.json'))
        if not index['complete'] or index['unknown_rooms']:
            raise ValueError('주의 지수가 미평가인 표본은 최악 순위를 확정할 수 없습니다')
        first = value['phenomena']['FO'].get('first_s')
        rows.append(dict(sample_id=path.parent.name,
            burning=len(set(value['burning_original_rooms'])),
            attention=index['attention_room_count'], first_FO_s=first))
    return sorted(rows, key=lambda x: (-x['burning'], -x['attention'],
        math.inf if x['first_FO_s'] is None else x['first_FO_s'], x['sample_id']))


def apply_worst(job_id, building_sha, config_path=CONFIG, jobs=JOBS):
    if not isinstance(job_id, str) or not re.fullmatch(r'mc-\d+-[a-f0-9]+', job_id):
        raise ValueError('MC 작업 ID 오류')
    folder = (Path(jobs)/job_id).resolve()
    if folder.parent != Path(jobs).resolve():
        raise ValueError('MC 작업 경로 오류')
    ranking = ranked_samples(folder, building_sha)
    if not ranking:
        raise ValueError('적용할 완주 표본이 없습니다')
    winner = ranking[0]
    sample = read(folder/winner['sample_id']/'sample.json')
    states = {v['id']: {k: v[k] for k in ('a', 'b', 'open', 'effective_fraction')}
              for v in sample['openings']}
    if len(states) != len(sample['openings']):
        raise ValueError('중복 개구부 ID')
    from execution_evidence import digest
    fixed = dict(building_sha256=building_sha, job_id=job_id,
        sample_id=winner['sample_id'], source_room=read(folder/'request.json')['room'],
        states=states, ranking=ranking, sample_sha256=digest(sample),
        priority='burning desc, attention>=70 desc, first FO asc; sample ID tie break')
    fixed_for(sample['scenario'], {'fixed_state': fixed})
    for vent in sample['scenario']['openings']:
        if vent['schedule'] != [[0., states[vent['id']]['effective_fraction']]]:
            raise ValueError('저장 표본 개방률과 입력 일정 불일치')
    config = read(config_path, {})
    config['fixed_state'] = fixed
    atomic_json(config_path, config)
    return fixed


def clear(config_path=CONFIG):
    config = read(config_path, {})
    config.pop('fixed_state', None)
    atomic_json(config_path, config)


def door_report(raw, config):
    from pyrocast_lite.door_classification import classify_doors
    report = classify_doors(raw, classifications(config))[1]
    fixed = fixed_for(raw, config)
    report['fixed_state'] = fixed
    for row in report['rows']:
        row['fixed_state'] = fixed['states'].get(row['id']) if fixed else None
    return report
