"""Input provenance, separate from numerical physical-validity checks.

Missing inventories/fan measurements cannot be repaired by inventing values.
Keep the applied assumptions visible and versioned, including MC samples.
"""
import json
from pathlib import Path
from .physics_config import defaults


def growth_for(use):
    table=json.loads((Path(__file__).resolve().parents[1]/'pyrocast_lite/fire_load_table.json').read_text('utf-8'))['classes']
    cfg=defaults('source_input')
    cls=use.get('usage_class',use.get('class','default'))
    row=table.get(cls,table['default'])
    seconds=row.get('t_alpha') or cfg['fallback_growth_time_s']
    return dict(growth_kW_s2=cfg['reference_growth_kW']/seconds**2,
                growth_time_s=seconds, growth_basis=row.get('basis') or '프로젝트 임시 용도 기준 · 실측 미확인')


def describe(raw):
    cfg=defaults('source_input');uses=raw.get('approved_input',{}).get('room_uses',{})
    origin=next((g['room'] for g in raw.get('fuel_groups',[]) if 'initial_time_s' in g),None)
    review=[]
    for rid,use in uses.items():
        evidence=use.get('classification_basis',{})
        if isinstance(evidence,dict) and evidence.get('review_required'):
            review.append(dict(room=rid,kind='mixed_usage',detail=evidence['reason']))
        elif isinstance(evidence,dict) and evidence.get('basis') in ('floor_use','default','ai'):
            review.append(dict(room=rid,kind='estimated_usage',detail='층 용도·자동 추정 분류 · 실제 실 용도 미확인'))
        if 'table_basis' in use and not use['table_basis'] and use.get('load_MJ_m2',0)>0:
            review.append(dict(room=rid,kind='provisional_fuel',detail='연료 기준량 출처 미확인'))
    fans=raw.get('mechanical_vents',[])
    assumptions=raw.get('ventilation_assumptions',{})
    ventilation='사용자 환기 조건' if assumptions else '기계 급배기 입력 있음' if fans else '기계 급배기 미입력 · 자연환기·누기만 계산'
    if origin in assumptions and 'ach' in assumptions[origin]:
        ventilation+=f" · 화점실 급기·배기 각각 {assumptions[origin]['ach']:g} ACH"
    group=next((g for g in raw.get('fuel_groups',[]) if g.get('room')==origin and 'initial_time_s' in g),{})
    use=uses.get(origin,{})
    return dict(revision=cfg['revision'],origin_room=origin,origin_use=use,
        growth_kW_s2=group.get('growth_kW_s2'),growth_basis=growth_for(use)['growth_basis'] if use else '저장 입력',
        ventilation=ventilation,mechanical_vent_count=len(fans),review_rooms=review,
        source_basis=('사용자 지정 화원' if raw.get('fire_input') else '면적·용도 기준의 지정 화원' if uses else '저장 입력의 지정 화원')+' · 실제 물품별 시험곡선 미확인',
        chemistry_basis='입력 연료 조성·발열량·수율 사용 · 실제 재료 대조 별도',
        numerical_validation_is_input_validation=False)
