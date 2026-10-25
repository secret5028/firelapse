"""Window policies and one authoritative, ID-based opening history.

The native conditional VENT owns the transition. No event here schedules a rerun.
"""
from copy import deepcopy
from hashlib import sha256
import math
import numpy as np


GLASS = {'conductivity_W_mK': .95, 'density_kg_m3': 2500.,
         'specific_heat_kJ_kgK': .82, 'thickness_m': .006, 'emissivity': .90}
DEFAULT_POLICY = {'enabled': False, 'criterion': 'TEMPERATURE', 'threshold': 450.,
                  'post_fraction': 1., 'material': GLASS,
                  'preset_id': 'ordinary_float_6mm_proxy_v1'}
LIMITATION = ('창은 일반 단판 판유리 6 mm 대용이며 표면온도 450℃ 초과가 기본값이다. '
              '사용자가 변경하는 문헌 참고 근사이며 NIST 공식 파괴온도·실제 탈락 면적 예측이 아니다. '
              '외기 창 타깃은 순정 외기 뒷면 경계를 사용하지만 유리 투과·창틀·복층·균열 과정은 생략한다. '
              '기록은 5초 간격의 개방 변화 관측 구간이며 정밀 파괴 시각이 아니다.')


LIMITATION += ' 불투명 판 근사로 실제보다 일찍 열릴 수 있으며, 실내 유리 파괴는 미평가다.'


def is_window(opening):
    return 'window' in opening.get('kind', '').lower() or opening.get('is_window', False)


def policy(model, opening):
    base = model.get('window_breakage', {})
    override = opening.get('window_breakage', {})
    if not isinstance(base, dict) or not isinstance(override, dict):
        raise ValueError('창 파괴 설정은 객체여야 합니다')
    allowed = set(DEFAULT_POLICY)
    for config in (base, override):
        if set(config)-allowed or not isinstance(config.get('material', {}), dict):
            raise ValueError('지원하지 않는 창 파괴 설정 또는 물성입니다')
    p = {**deepcopy(DEFAULT_POLICY), **base, **override}
    p['material'] = {**GLASS, **base.get('material', {}), **override.get('material', {})}
    if not isinstance(p['enabled'], bool):
        raise ValueError('창 파괴 enabled는 참/거짓이어야 합니다')
    if not p['enabled']:
        return None
    if not is_window(opening):
        if override.get('enabled'):
            raise ValueError('창 파괴는 명시적으로 분류된 창에만 적용합니다')
        return None
    if opening.get('type') == 'FLOOR' or opening['b'] != 'OUTSIDE':
        if override.get('enabled'):
            raise ValueError('현재 창 파괴는 외기 창만 지원합니다. 실내 유리는 미평가입니다')
        return None
    if p['criterion'] not in ('TEMPERATURE', 'FLUX'):
        raise ValueError('창 기준은 TEMPERATURE 또는 FLUX입니다')
    for k in ('threshold', 'post_fraction'):
        if isinstance(p[k], bool) or not isinstance(p[k], (int, float)) or not math.isfinite(p[k]):
            raise ValueError('유효하지 않은 창 설정: '+k)
    if p['criterion'] == 'FLUX' and p['threshold'] <= 0:
        raise ValueError('창 열유속 기준은 양수 kW/m²로 입력하세요')
    if p['criterion'] == 'TEMPERATURE' and p['threshold'] <= -273.15:
        raise ValueError('창 표면온도 기준 오류')
    schedule = opening.get('schedule', [[0, 1]])
    p['pre_fraction'] = float(schedule[0][1])
    if any(f != p['pre_fraction'] for _, f in schedule):
        raise ValueError('화재 창 파괴와 인위적인 중간 개폐 일정을 함께 적용하지 않습니다')
    if not 0 <= p['pre_fraction'] <= p['post_fraction'] <= 1:
        raise ValueError('창 개방률은 0 ≤ 초기값 ≤ 파괴 후 최종값 ≤ 1이어야 합니다')
    for k, v in p['material'].items():
        if k not in GLASS or isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
            raise ValueError('유리 물성 오류: '+k)
    if p['material']['emissivity'] > 1:
        raise ValueError('유리 방사율은 0~1 범위입니다')
    return p


def window_targets(model):
    rooms = {r['id']: r for r in model['rooms']}
    out = []
    for v in model.get('openings', []):
        p = policy(model, v)
        if not p or p['post_fraction'] == p['pre_fraction']:
            continue
        r = rooms[v['a']]; w, d, h = r['size_m']
        along = v.get('offset_m', 0) + v['width_m']/2
        z = (v.get('bottom_m', 0)+v['top_m'])/2
        xyz, normal = {
            'FRONT': ([along, 0., z], [0., 1., 0.]),
            'REAR': ([along, d, z], [0., -1., 0.]),
            'LEFT': ([0., along, z], [1., 0., 0.]),
            'RIGHT': ([w, along, z], [-1., 0., 0.]),
        }[v['face']]
        if not 0 <= xyz[0] <= w or not 0 <= xyz[1] <= d or not 0 < z < h:
            raise ValueError('창 타깃이 구획 경계 범위를 벗어납니다: '+v['id'])
        # Native material IDs are limited to sixteen characters including GLS_.
        suffix = sha256(v['id'].encode()).hexdigest()[:12]
        out.append({'id': 'WIN_'+suffix, 'material_id': 'GLS_'+suffix,
                    'opening_id': v['id'], 'room': v['a'], 'local_xyz': xyz,
                    'normal': normal, 'material': p['material'], 'policy': p,
                    'rear_boundary': 'stock_exterior_at_exact_box_boundary'})
    return out


def device_series(result, target_id, family, legacy_index=None):
    """Use the CSV device ID, never the position of an unrelated target."""
    ids = result.get('devices_ids', {})
    matches = [k for k, v in ids.items() if k.startswith(family+'_') and str(v).strip() == target_id]
    if len(matches) == 1:
        return result['devices'][matches[0]]
    if ids:
        raise ValueError(f'Missing or ambiguous {family} for device {target_id}')
    # Compatibility for old test fixtures/results that predate the ID header map.
    if legacy_index is not None:
        key = family+'_'+str(legacy_index)
        if key in result['devices']:
            return result['devices'][key]
    raise ValueError(f'Missing {family} for device {target_id}')


def realized_fraction(result, opening, times=None, require_native=False):
    t = np.asarray(times if times is not None else result.get('time_s', result.get('zone', {}).get('Time')), float)
    states = result.get('opening_states', {})
    if opening['id'] in states:
        state = states[opening['id']]
        nt = np.asarray(result.get('time_s', result.get('zone', {}).get('Time')), float)
        values = np.asarray(state['fraction'], float)
    else:
        matches = [k for k, v in result.get('native_vents_ids', {}).items()
                   if k.startswith('WF_') and str(v).strip() == opening['id']]
        if len(matches) > 1:
            raise ValueError('Duplicate native opening fraction ID: '+opening['id'])
        if not matches:
            if require_native or opening.get('window_breakage', {}).get('enabled'):
                raise ValueError('Dynamic window requires native WF output: '+opening['id'])
            schedule = opening.get('schedule', [[0, 1]])
            return np.interp(t, [p[0] for p in schedule], [p[1] for p in schedule])
        nt = np.asarray(result['native_vents']['Time'])
        values = np.asarray(result['native_vents'][matches[0]])
    if not np.isfinite(values).all() or np.any(values < -1e-8) or np.any(values > 1+1e-8):
        raise ValueError('Invalid native opening fraction: '+opening['id'])
    return values[np.clip(np.searchsorted(nt, t, side='right')-1, 0, len(nt)-1)]


def histories(model, native):
    t = np.asarray(native['zone']['Time']); targets = {x['opening_id']: x for x in window_targets(model)}
    out = {}
    for v in model.get('openings', []):
        p = policy(model, v)
        if not p:
            continue
        values = realized_fraction(native, v, require_native=True)
        changed = np.flatnonzero(values > p['pre_fraction']+1e-9)
        j = int(changed[0]) if len(changed) else None
        target = targets.get(v['id'])
        out[v['id']] = {'fraction': values.tolist(), 'initial_fraction': p['pre_fraction'],
            'post_fraction': p['post_fraction'], 'criterion': p['criterion'], 'threshold': p['threshold'],
            'threshold_unit': 'C_target_front_surface' if p['criterion'] == 'TEMPERATURE' else 'kW_m2_native_emissivity_weighted_front_flux',
            'material': p['material'], 'preset_id': p['preset_id'],
            'target_id': target['id'] if target else None,
            'changed': j is not None, 'first_observed_change_s': float(t[j]) if j is not None else None,
            'observed_interval_s': [float(t[max(0, j-1)]), float(t[j])] if j is not None else None,
            'sample_interval_s': float(model['output_step_s']), 'opening_reconstruction': 'previous_sample_hold',
            'basis': 'successful_native_WF; threshold_proxy_not_glass_fracture_prediction',
            'rear_boundary': target['rear_boundary'] if target else None}
        if target:
            out[v['id']]['surface_C'] = device_series(native, target['id'], 'TRGSURT').tolist()
    return out
