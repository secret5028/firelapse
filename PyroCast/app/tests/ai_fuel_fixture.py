"""UI-only local mock AI. Isolated override/config files; never calls a provider.
Run manually for C7 screenshots, not part of production startup.
"""
import sys,json,shutil,os,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'simulation'),str(ROOT/'simulation/deps')]
import lite_ai_fuel as ai
from pyrocast_lite import screening_v8_approved as approved
OUT=ROOT/'simulation/results/ui_C7_20261102/mock';OUT.mkdir(parents=True,exist_ok=True)
ai.CONFIG=OUT/'ai.json';ai.OVERRIDES=OUT/'config/fuel-overrides.json'
old=approved.HERE;approved.HERE=OUT/'pyrocast_lite';approved.HERE.mkdir(exist_ok=True)
for f in ['fire_load_table.json','approved_uses_v8.json']:shutil.copyfile(old/f,approved.HERE/f)
ai.CONFIG.write_text(json.dumps(dict(base_url='http://127.0.0.1:1/v1',model='C7-mock-no-network',api_key_env='PYROCAST_C7_FIXTURE_KEY')))
os.environ['PYROCAST_C7_FIXTURE_KEY']=uuid.uuid4().hex+uuid.uuid4().hex

def mock(cfg,key,messages):
    ctx=json.loads(messages[0]['content'].split('\n',1)[1]);message=messages[-1]['content']
    rows=[]
    for r in ctx['rooms']:
        if 'R2' in message:
            if r['id']!='CAD_3F_R2':continue
            cls='shopping'
        else:
            if r['floor'] not in ('1F','2F'):continue
            cls='shopping' if r['floor']=='1F' else 'warehouse'
        rows.append(dict(room_id=r['id'],usage_class=cls,reason='모의 응답 검증 · 사용자 층 용도 요청'+(' · 타이어 전용 클래스 없음: 일반 창고 대용' if cls=='warehouse' else '')))
    return json.dumps(rows,ensure_ascii=False)

original=ai.propose
ai.propose=lambda body,building,sha:original(body,building,sha,transport=mock)
from serve_cfbt_building import main
sys.argv=[sys.argv[0],str(Path('C:/Users/<user>/Documents/Codex/2026-10-14/files-pasted-by-the-user-cad3d')),'--port','8821','--result',str(ROOT/'simulation/results/condition_display_v1/playback.json')]
main()
