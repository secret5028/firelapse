"""Building-scoped fuel quantity inputs; does not change combustion equations."""
import hashlib,json,math,re
from pathlib import Path
DIRECTORY=Path(__file__).resolve().parents[1]/'config/fuel-quantities'
MIN_RATIO=.1
MAX_RATIO=3.

def path_for(sha):
    if not isinstance(sha,str) or not re.fullmatch('[0-9a-f]{64}',sha):raise ValueError('건물 해시 오류')
    return DIRECTORY/(sha+'.json')

def load(sha):
    p=path_for(sha)
    value=json.loads(p.read_text('utf-8')) if p.exists() else {}
    if value and value.get('building_sha256')!=sha:raise ValueError('다른 건물의 연료량 설정')
    for rid,row in value.get('rooms',{}).items():validate_ratio(row.get('multiplier'))
    return value if value.get('rooms') else {}

def revision(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def validate_ratio(v):
    if type(v) not in (float,int) or not math.isfinite(v) or not MIN_RATIO<=v<=MAX_RATIO:raise ValueError('연료량은 기준의 10~300% 범위입니다')
    return v

def ratio(settings,rid):return settings.get('rooms',{}).get(rid,{}).get('multiplier',1.)
