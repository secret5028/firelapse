"""Explicit source selection only; automatic eligibility and physics stay unchanged."""
from copy import deepcopy

def origins(scored):
    model=scored['classified_model'];groups=model['fuel_groups'];rows=[]
    for row in scored['ranked']+scored['excluded']:
        rid=row['room'];budget=scored['origin_budgets'][rid]
        if len([g for g in groups if g['room']==rid])!=1 or budget['energy_MJ']<=0 or budget['Q_origin_peak_kW']<=0:continue
        rows.append(dict(room=rid,floor=row['floor'],rank1=row.get('rank1'),automatic_candidate=row['eligible'],
            label=(budget.get('classification') or {}).get('label','용도 미확인'),excluded_reason=row.get('excluded_reason')))
    return rows

def validate_rooms(scored, rooms):
    if not isinstance(rooms,list) or len(rooms)!=1 or not isinstance(rooms[0],str):raise ValueError('rooms는 원래 방 ID 1개 배열이어야 합니다')
    if rooms[0] not in {r['room'] for r in origins(scored)}:raise ValueError('연료와 양의 화원 상한이 있는 원래 방을 선택하세요')
    return rooms

def manual_scenario(scored, rid, state):
    from pyrocast_lite.screening_v8_approved import scenario
    validate_rooms(scored,[rid]);local=deepcopy(scored)
    if rid not in {r['room'] for r in local['ranked']}:
        local['ranked'].append(next(r for r in local['excluded'] if r['room']==rid))
    data=scenario(local,rid,state);data['cad']['fire_key']=rid
    data['screening_source']['selection_mode']='user_designated'
    data['screening_source']['automatic_exclusion']=next(r for r in origins(scored) if r['room']==rid)['excluded_reason']
    return data
