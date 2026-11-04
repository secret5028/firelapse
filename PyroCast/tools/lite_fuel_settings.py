"""Manual fuel quantity editing, independent of AI credentials and saved playback."""
import json,threading
from pathlib import Path
from result_catalog import atomic_json
from pyrocast_lite import fuel_quantity as q
ROOT=Path(__file__).resolve().parents[1]
_lock=threading.RLock()

def context(building,sha):
    from building_rules import usage_class,dedicated_core_kind
    read=lambda p:json.loads(p.read_text('utf-8-sig')) if p.exists() else {}
    table=read(ROOT/'simulation/pyrocast_lite/fire_load_table.json')['classes']
    approved=read(ROOT/'simulation/pyrocast_lite/approved_uses_v8.json')
    choices=approved.get('rooms',{}) if approved.get('building_sha256')==sha else {}
    ai=read(ROOT/'simulation/config/fuel-overrides.json');ai=ai.get('rooms',{}) if ai.get('building_sha256')==sha else {}
    saved=q.load(sha);rows=[]
    core_ids={'CAD_'+str(n.get('floor'))+'_'+str(n.get('room_id')) for n in building.get('core_nodes',[]) if n.get('room_id')}
    for f in building['floors']:
        for r in f.get('rooms',[]):
            if 'outdoor' in r.get('tags',[]):continue
            rid='CAD_'+f['name']+'_'+r['id'];choice=choices.get(rid,{});custom=ai.get(rid)
            cls=custom['usage_class'] if custom else choice.get('class') or usage_class(r.get('names',[]),f.get('use'))[0]
            spec=table[cls];base=spec['mean'] if custom else choice.get('load_override_MJ_m2',spec['mean'])
            area=r.get('area');editable=isinstance(area,(float,int)) and area>0 and base>0
            if choices:editable=editable and rid in choices and rid not in approved.get('remove_from_candidate_and_graph',[])
            if not choices and (dedicated_core_kind(r) or rid in core_ids):base=10.;editable=False
            factor=q.ratio(saved,rid)
            rows.append(dict(id=rid,floor=f['name'],name=' / '.join(r.get('names',[])) or spec['label'],usage=spec['label'],usage_class=cls,area=area,
                base_load=base,multiplier=factor,load=base*factor,energy_MJ=base*factor*area if isinstance(area,(float,int)) else None,hrrpua=spec['rhrf'],coverage=approved.get('coverage',.5),editable=bool(editable),
                basis='사용자 선택 배율 × '+('승인 기준량' if choice.get('load_override_MJ_m2') else 'fire_load_table.json 용도 기준량')))
    basis={'rooms':rows,'quantity_settings':saved}
    return dict(editable=True,building_sha256=sha,rooms=rows,revision=q.revision(basis),quantity_revision=q.revision(saved),range={'min':q.MIN_RATIO,'max':q.MAX_RATIO,'step':.1},
                notice='양 표시용 기호 · 실제 적재물 크기 아님',quantity_settings=saved)

def apply(body,building,sha):
    if not isinstance(body,dict) or set(body)!={'building_sha256','revision','rooms'} or body['building_sha256']!=sha:raise ValueError('연료량 설정 요청 오류')
    rows=body['rooms']
    if not isinstance(rows,list) or not rows:raise ValueError('변경할 실이 없습니다')
    with _lock:
        ctx=context(building,sha)
        if body['revision']!=ctx['revision']:raise ValueError('입력이 변경되었습니다. 새로 불러오세요')
        allowed={r['id'] for r in ctx['rooms'] if r['editable']};seen=set();saved=q.load(sha) or {'building_sha256':sha,'rooms':{}}
        for r in rows:
            if not isinstance(r,dict) or set(r)!={'id','multiplier'} or r['id'] not in allowed or r['id'] in seen:raise ValueError('실 선택 오류')
            seen.add(r['id']);q.validate_ratio(r['multiplier'])
        for r in rows:
            if r['multiplier']==1:saved['rooms'].pop(r['id'],None)
            else:saved['rooms'][r['id']]={'multiplier':r['multiplier']}
        atomic_json(q.path_for(sha),saved)
        return {**context(building,sha),'rerun_required':True,'simulation_started':False}
