"""Building-scoped floor defaults and explicit room fuel settings."""
import hashlib,json,math,re
from pathlib import Path
DIRECTORY=Path(__file__).resolve().parents[1]/'config/fuel-quantities'
MIN_RATIO=.1
MAX_RATIO=3.
def path_for(sha):
    if not isinstance(sha,str) or not re.fullmatch('[0-9a-f]{64}',sha):raise ValueError('건물 해시 오류')
    return DIRECTORY/(sha+'.json')
def load(sha):
    p=path_for(sha);value=json.loads(p.read_text('utf-8')) if p.exists() else {}
    if value and value.get('building_sha256')!=sha:raise ValueError('다른 건물의 연료 설정')
    for scope in ('rooms','floors'):
        for row in value.get(scope,{}).values():validate_ratio(row.get('multiplier'))
    return value if any(value.get(k) for k in ('rooms','floors','defaults')) else {}
def revision(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def validate_ratio(v):
    if type(v) not in (float,int) or not math.isfinite(v) or not MIN_RATIO<=v<=MAX_RATIO:raise ValueError('연료량은 기준의 10~300% 범위입니다')
    return v
def resolve(settings,rid,floor,baseline_class,baseline_load,table):
    room=settings.get('rooms',{}).get(rid);f=settings.get('floors',{}).get(floor)
    row=room if room is not None else f or {};scope='room' if room is not None else 'floor' if f else 'default'
    default=settings.get('defaults',{}).get(rid,{});chosen=row.get('usage_class') or default.get('usage_class')
    cls=chosen or baseline_class
    if cls not in table:raise ValueError('알 수 없는 가연물 종류')
    base=table[cls]['mean'] if chosen else baseline_load;factor=validate_ratio(row.get('multiplier',1.))
    return dict(usage_class=cls,base_load=base,multiplier=factor,load=base*factor,hrrpua=table[cls]['rhrf'],scope=scope,
                default_source='ai' if default else 'classification',default_reason=default.get('reason',''))
def ratio(settings,rid):
    floor=rid.removeprefix('CAD_').split('_',1)[0]
    return settings.get('rooms',{}).get(rid,settings.get('floors',{}).get(floor,{})).get('multiplier',1.)
