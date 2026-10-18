from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parent.parent
out=root/'outputs/CAD-CFAST기준-v22'
app=Path('C:/Users/예방/Desktop/소방 크로키 업-로컬웹앱')
job=app/'data/d018b4bb75da4475b1fd75447603c1a0/cad-output'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(job/'model.html')==sha(out/'model.html')==sha(app/'_internal/cad_engine/integrated_viewer.html')
assert sha(job/'cfast-demo.json')==sha(out/'cfast-demo.json')
d=json.loads((out/'cfast-demo.json').read_text('utf8'))
assert sha(job/'building.json')==d['building_sha256']
report=dict(status='installed_and_browser_checked',url='http://127.0.0.1:8778/cad-result/d018b4bb75da4475b1fd75447603c1a0/model.html',
    model_sha256=sha(job/'model.html'),results_sha256=sha(job/'cfast-demo.json'),building_sha256=d['building_sha256'],
    mode=d['calculation_mode'],browser_checks=['input HRR and computed HRR chart','secondary ignition section hidden in baseline',
    't=0 no smoke or visible flame','t=1800 all floors: 38 smoke display rooms, one 1000kW fire',
    'no wall clipping, user wall transparency 98% restored','legacy tools and floor controls present','no browser error logs'],
    screenshot='화면-30분.jpg',physical_validation=False)
(out/'설치기록.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
recovery=root/'outputs/작업기준-복구-20261014.txt'
entry='''최신 적용 — CFAST 지침 기반 기본 입력 정리 v22 (2026-10-15)
- 사용자 결정: 기본은 CFAST 지침·매뉴얼에 충실하게 수정. 격자 단위 가연물 제안은 장단점 추가 검토. 따라서 격자 자동 배치 구현은 보류.
- 기본 계산은 사용자 지정 HRR 화재 1개. v21 실당 자동 가연물117개 및 일률적인 표면300°C 추가 착화는 기본에서 제외. CFAST 조건부 착화 기능 자체는 정상 지원 기능이며 work/cfast_all_rooms_scenario.json, cfast_ignition_scenario.json과 --ignition-config로 명시 선택하는 실험 설정으로 보존.
- work/cfast_design_fire.json과 cfast_design_fire.py: t² 성장/유지/감쇠, 끝값, 계산기간, 면적/높이/조성/연소열/복사분율/수율을 선언·검증. 기본은 기존 최초 화점과 같은 300초1MW 이후1800초까지 유지. NIST가 지정한 건물 평균/최악 화재가 아니라 비교용 가정. 입력 적분1600.125MJ, 목재 대리연료 환산88.4047kg; 건물 실제 연료재고가 아님. 감쇠 옵션은 지원하지만 이번 화재는 소진을 가정하지 않음.
- 입력 표 선형보간과 실제 CFAST HRR 출력을 구분. 화면에 입력/계산 HRR 곡선, 총열량, 조건 표시. 추가 착화 영역은 기본 결과에서 숨김. '추가 착화 미계산'을 '다른 실 미착화'로 해석하지 않음.
- 1800초 CFAST 정상 종료93.125초. 동일 최초화재였던 v18의 전체 실 시계열/HRR 차이0. 156개표시/100계산/36층간경로/건물해시 유지. CAD 추출 재개 없음. 전체30분 연기 표시38구획(표시 기준이며 위험 판정 아님).
- 기존 레거시 UI prefix 동일, 자동 벽절개 없음, 벽투명도98% 복원, 0초/30분/실감/전층/콘솔 확인. 건물 실제 물리 검증 아님.
- 기존 웹앱 job model.html/cfast-demo.json 및 _internal/cad_engine/integrated_viewer.html에 설치. 출력·백업·검증·설치기록·화면·격자가연물-검토.txt: outputs/CAD-CFAST기준-v22.
- 격자 검토: 총량 배분/자연어 편집/시각화에는 유리. 다중 불기둥 상호작용 미계산, Target 1차원응답, 격자 의존성, 물성·점화원·위치 불확실성, 동일 열량 중복 산입 위험. 우선 재고/표시 데이터로 검토하고 실험자료 기반 대표 화재 및 격자 민감도 검증 후 채택 판단.
- 재현: work/cad_cfast_multifloor.py --duration 1800 --output CAD-CFAST기준-v22. 기본 output도v22. work/restore_cad_ui.py CAD-CFAST기준-v22. work/verify_cfast_v22.py, record_cfast_v22.py. upgrade_cfast_v22.py는 일회 마이그레이션이므로 재실행하지 않음.

'''
text=recovery.read_text('utf8')
if not text.startswith(entry.splitlines()[0]):recovery.write_text(entry+text,'utf8')
print(json.dumps(report,ensure_ascii=False))
