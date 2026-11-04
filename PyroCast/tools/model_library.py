"""Explicit local model registry; scan models never enter execution routes."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/'config/model-library.json'
LIBRARY_URL='http://127.0.0.1:8841'
RUN_PATHS={'/cfbt/run','/cfbt/ignite','/cfbt/r8/run','/cfbt/lite/screening','/cfbt/lite/mc'}

def entries():
    return json.loads(REGISTRY.read_text('utf8'))['models']

def model_path(entry):
    path=(ROOT/entry['path']).resolve()
    if not path.exists() and entry['id']=='ganghwa':
        path=(ROOT/'cad-project/building.json').resolve()
    if not path.is_relative_to(ROOT):raise ValueError('Model path outside project')
    return path

def execution_policy(building,source=None):
    meta=building.get('model_provenance',{})
    kind=meta.get('source_kind')
    if kind in ('scan','raster','unknown'):
        return {'allowed':False,'reason':'스캔/출처 미확인 모델: 개구부 정보 미검증으로 시뮬레이션 금지'}
    row=next((e for e in entries() if source and model_path(e)==Path(source).resolve()),None)
    if row is None and source and Path(source).is_file():
        digest=hashlib.sha256(Path(source).read_bytes()).hexdigest()
        row=next((e for e in entries() if e.get('sha256')==digest),None)
    if row:
        return {'allowed':row.get('simulation_enabled',False) and row['source_kind']!='scan','reason':row['execution_note']}
    # Older unregistered drawings need provenance, not an unrestricted execution fallback.
    return {'allowed':False,'reason':'모델 출처·계산 연결 미확인: 열람 전용'}

def catalog():
    return {'models':[{**{k:v for k,v in e.items() if k not in ('path','source_path')},
        'url':LIBRARY_URL+'/models/?id='+e['id'],
        'model_url':LIBRARY_URL+'/models/'+e['id']+'/building.json'} for e in entries()]}
