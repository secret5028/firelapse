"""Bounded-cost exploration preset. These are project assumptions, not NIST defaults."""
from .model import merge
from building_rules import load_rules


LIMITATIONS = [
    '혼합물 모드는 같은 상층에서 FUEL+실제CO에 공통 반응률을 적용하는 프로젝트 근사다. 성분별 속도/수소/그을음 산화/외기배출 CO의 추가 산화는 미평가다. NIST가 검증한 확장 모델은 아니다.',
    '공급 에너지는 총가능열이라는 명시적 가정으로 1차열과 CO 잔여열로 나눈다. 기존 미연연료 bulk와 혼합물 bulk는 동시에 실행하지 않는다.',
    '추가 반응 원천항의 질량·원소·산소 수지를 검사했다. 순정 CFAST의 성분 재정규화에 따른 전역 성분량 오차는 남으며, 원소별 전역 수지의 정밀 보존을 보장하지 않는다.',
    '천장제트는 원본 함수의 소수 표본을 CAD에 매핑한 표시다. 전체 공간 속도장/실제 연기 선단이 아니며 표시속도 상한은8m/s다.',
    '2층 존 평균값이다. 실내 화염 전파·폭연 압력·국부 온도는 해석하지 않는다.',
    '가스 추가연소는 임계값과 대표 반응률에 따른 근사다. 실제 FGI·백드래프트 발생 확률이나 폭발 강도를 뜻하지 않는다.',
    'FGI 보라색은 사용자 연료 질량분율·산소 기준의 위험 선별이다. 실측 LFL이나 발생 확률이 아니다. 점화 가정은 기존 연료·산소만 사용한다.',
    '고체는 대표 연료군과 소수 노출면으로 평가한다. 가구의 실제 배치·개별 착화는 재현하지 않는다.',
    'FO는 사용자 임계값 이후 유한 연료 공급을 확대하는 처방이다. 실 전체 동시 착화를 예측한 결과가 아니다.',
    'FO 후 분산 복사는 후처리 근사다. CFAST 내부 플룸·실내 복사는 대표 화원 위치를 계속 사용한다.',
    '열전달 보충은 단방향이다. 개구부를 통한 복사 에너지의 완전한 건물 수지를 풀지 않는다.',
    '실행·사건 상한, 후보 오류, 도면 연결 누락으로 미평가 구역이 남을 수 있다. 미평가를 안전으로 해석하지 않는다.',
    '일괄 반복은 매 회차 전체 구간을 재계산한다. 일정 안정과 조건 재확인을 구분하며, 앞당긴 착화를 유지하는 근사가 모든 위험의 보수적 상한을 보장하지 않는다.',
    '상층 추가연소 표시량은 프로젝트 bulk 반응 항이며 native 플룸 내 상층 연소 전체나 롤오버 발생 확정값이 아니다. 개구부 연소량은 별도의 문·방향별 native 결과다.',
    '도면에서 추출한 구획·개구부 데이터가 필요하다. 모든 DWG·PDF·이미지의 자동 인식을 보장하지 않는다.',
]


def execution_limits(duration_s=1800.):
    """Wall-clock budgets; hour scenarios have twice the 30-minute allowance."""
    factor = 2 if duration_s >= 3600. else 1
    return {'max_runs':3, 'max_passes':3, 'run_timeout_s':600.*factor,
            'wall_time_budget_s':1800.*factor}


def bound_execution(settings, duration_s=1800.):
    """Bound cost independently of room count, without capping fire spread extent."""
    limits=execution_limits(duration_s)
    result=dict(settings)
    for key, ceiling in limits.items():
        result[key]=min(result.get(key,ceiling),ceiling)
    result['automatic_retry']=False
    result['stall_timeout_s']=90.
    result['budget_policy']='bounded_batch_v2_duration'
    return result


def apply_profile(raw, profile='practical'):
    if profile == 'legacy':
        return merge(raw, {'execution_profile': 'legacy'})
    if profile != 'practical':
        raise ValueError('Unknown execution profile')
    preset = {
        'duration_s': 1800., 'output_step_s': 5., 'max_time_step_s': 1.,
        'gas': {'mixture_enabled': True, 'jet_enabled': True, 'energy_basis':'total_potential_assumption', 'vent_gate_enabled': False, 'activation_J_mol': 0.,
                'rate_ref_s_inv': .1, 'pilot_assumed': False,
                'profile_id': 'practical_constant_rate_v1',
                'basis': 'project_constant_rate_and_oxygen_stock_limit; not_flame_propagation'},
        'flashover': {'enabled': True, 'area_basis': 'fuel', 'occupancy_fraction': .31,
                      'radiation_points': 4},
        'spread': {'iteration_mode':'fixed_point', 'max_passes':3,
                   'max_runs': 3, 'max_added_ignitions': 4, 'wall_time_budget_s': 1800.,
                   'run_timeout_s': 600., 'quadrature_n': 4, 'plate_nodes': 17, 'plate_dt_s': .2},
    }
    preset['spread'].update(execution_limits(raw.get('duration_s',1800.)))
    result = merge(preset, raw)
    result['execution_profile'] = 'practical'
    result['spread']=bound_execution(result['spread'], result['duration_s'])
    return result


def room_defaults(room, building):
    """Use recognized text conservatively; mixed labels fall back to ordinary fuel."""
    text = str([room.get('usage', ''), room.get('names', []), room.get('name', '')]).lower()
    rules = load_rules()['native_usage']
    process = any(w in text for w in rules['process_tokens'])
    passage = any(w in text for w in rules['passage_tokens'])
    if passage and not process:
        usage, load, fraction, hrrpua = 'passage', 30., .05, 150.
    elif process:
        usage, load, fraction, hrrpua = 'process_or_storage', 600., .4, 250.
    elif any(w in text+str(building.get('usage','')).lower() for w in rules['lodging_tokens']):
        usage, load, fraction, hrrpua = 'lodging', 310., .31, 250.
    else:
        usage, load, fraction, hrrpua = 'ordinary_room', 400., .31, 250.
    return {'usage': usage, 'load_MJ_m2': load, 'occupancy_fraction': fraction,
            'hrrpua_kW_m2': hrrpua, 'basis': 'project_representative_default_from_room_text; not_surveyed_or_statutory'}


def wall_default(structure):
    text = str(structure).lower()
    light = any(w in text for w in ('철골', 'steel', '목조', 'wood'))
    return {'conductivity_W_mK': .25 if light else 1.75,
            'density_kg_m3': 800. if light else 2200., 'specific_heat_kJ_kgK': 1.,
            'thickness_m': .025 if light else .15, 'emissivity': .94, 'assumed': True,
            'basis': 'project_light_lining_proxy' if light else 'project_concrete_proxy; structure_unconfirmed_if_absent'}
