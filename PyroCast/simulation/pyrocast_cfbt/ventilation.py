"""Explicit mechanical flow and ramp assumptions. Parking ventilation is never invented."""
import math
import re
from .physics_config import defaults


def validate_ventilation(model):
    rooms={r['id']:r for r in model['rooms']};cfg=defaults('ventilation');seen=set()
    for v in model.get('mechanical_vents',[]):
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,45}',v['id']) or v['id'] in seen:
            raise ValueError('Invalid mechanical vent identity')
        seen.add(v['id'])
        if v['comp'] not in rooms:raise ValueError('Unknown mechanical vent compartment')
        v.setdefault('orientation','VERTICAL');v.setdefault('direction','supply');v.setdefault('cutoffs',cfg['cutoffs_Pa'])
        if v['direction'] not in ('supply','exhaust') or v['orientation'] not in ('VERTICAL','HORIZONTAL'):
            raise ValueError('Invalid mechanical vent direction/orientation')
        for key in ('flow_m3_s','area','height'):
            if type(v[key]) not in (int,float) or not math.isfinite(v[key]) or v[key]<0:
                raise ValueError('Invalid mechanical ventilation quantity')
        if v['area']<=0 or v['height']>rooms[v['comp']]['size_m'][2]:raise ValueError('Invalid vent area/height')
        if len(v['cutoffs'])!=2 or not 0<=v['cutoffs'][0]<v['cutoffs'][1] or not all(math.isfinite(x) for x in v['cutoffs']):
            raise ValueError('Invalid fan pressure cutoffs')
    from .basement_pressure import below_grade
    below=[r['id'] for r in rooms.values() if below_grade(r,model)]
    if below:
        note='지하층 환기 조건: 외부 창이나 급배기 가동을 자동 가정하지 않음. 0 ACH는 설비 정지이며, 최소 누기는 생략된 건물 연결의 등가 가정입니다.'
        if note not in model.setdefault('limits',[]):model['limits'].append(note)
    parking=[r['id'] for r in rooms.values() if r.get('use')=='parking' or r.get('fuel_default',{}).get('usage')=='parking']
    if parking and not model.get('mechanical_vents') and not any(v.get('kind')=='ramp' for v in model.get('openings',[])):
        note=f"주차장 환기 미지정: 실제 급·배기 또는 램프를 입력하세요. 예시 {cfg['suggested_parking_ach']:g} ACH는 자동 적용하지 않습니다."
        if note not in model.setdefault('limits',[]):model['limits'].append(note)


def deck_lines(model):
    # CFAST 7.7.7 read_vent namelist uses FLOW, not the handoff example's FLOWRATE.
    rows=[]
    for v in model.get('mechanical_vents',[]):
        ends=['OUTSIDE',v['comp']] if v.get('direction','supply')=='supply' else [v['comp'],'OUTSIDE']
        height=v['height'];area=v['area'];orientation=v.get('orientation','VERTICAL')
        cut=v.get('cutoffs',defaults('ventilation')['cutoffs_Pa'])
        rows.append(f"&VENT TYPE='MECHANICAL' ID='{v['id']}' COMP_IDS='{ends[0]}','{ends[1]}' AREAS={area:g},{area:g} HEIGHTS={height:g},{height:g} FLOW={v['flow_m3_s']:g} CUTOFFS={cut[0]:g},{cut[1]:g} ORIENTATIONS='{orientation}','{orientation}' /")
    return rows
