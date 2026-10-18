from pathlib import Path
import json,hashlib,urllib.request
ROOT=Path(__file__).resolve().parent.parent
p=ROOT/'outputs/CAD-속도검증-v27';sha=lambda b:hashlib.sha256(b).hexdigest()
for path,digest in json.loads((p/'ui-before.json').read_text('utf8')).items():assert sha(Path(path).read_bytes())==digest
url='http://127.0.0.1:8778/cad-result/d018b4bb75da4475b1fd75447603c1a0/cfast-demo.json?v=27'
with urllib.request.urlopen(url,timeout=15) as response:body=response.read()
assert sha(body)==sha((p/'final/cfast-demo.json').read_bytes())
d=json.loads(body);assert d['duration']==1800 and len(d['hrr'])==361
r={'http_result_sha256':sha(body),'http_matches_verified_output':True,'viewer_template_building_unchanged':True,'duration':d['duration'],'samples':len(d['hrr']),'targets':[(f['id'],f['ignition_time']) for f in d['fires']]}
(p/'served-verification.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),'utf8')
recovery=ROOT/'outputs/작업기준-복구-20261014.txt'
entry='''최신 적용 — CFAST 속도 검증 v27 (2026-10-15)
- 사용자 승인: CFAST 계산 방식 유지, 병목 항목별 확인, 속도 개선 및 기존 결과 비교.
- native CFAST7.7.7 바이너리/오차 허용치/모든 물리 입력 유지. 계산100구획·표시156공간·벽개구부133개·수직연결36개 유지. 구획 병합 확대·화재곡선 단순화·물성/착화조건 변경 없음.
- 현재v26시나리오의 최대시간간격0.25초로 제한. 출력PRINT0와-k,-o:CD 사용; UI/연결/착화에 필요한 zone/compartments/devices 및5초간격 유지.
- 전체30분 실행2079.672→809.017초(34분40초→13분29초, 이번기록대비61.10%단축). 같은조건캐시재실행2.278초, 수치데이터동일. 단일전체실행의PC상태변동은포함. 동시점10분통제비교293.004→194.117초(약34%단축).
- 전체시계열 상부층온도최대차0.853°C/경계높이0.003417m/총HRR피크-0.0092%/총열량+0.0023%. 추가착화출력345초·350초 동일. 홀/A/S실미착화유지.
- 예외:3F_R9 바닥위0.1m하부층의26:30 광학밀도0.851232→0.727260/m(약-14.56%). 다른공간하부층최대차0.000738/m. 얇은층수치민감도기록, 완전동일/물리정답보장으로표현하지않음.
- work/cad_cfast_multifloor.py: 출력프로필/최대시간간격/--force 옵션. work/cfast_runtime.py: 입력+엔진+옵션과결과파일해시검증캐시, 완료/실패확인, 진행/CPU/벽시계시간기록. 캐시/손상/변경입력시험통과.
- 현재시나리오재현: work/run_cfast_current.ps1(필요시--force). wrapper는v26가연물설정과0.25초를명시한다. runner의가연물기본v23는그대로이므로 wrapper없이현재시나리오라고단정하지않음.
- 현앱에는개선cfast-demo.json만교체. model.html/설치template/building.json해시유지, HTTP제공결과해시확인. 열린화면은새로고침시새결과를읽음. 자연어변수자동재계산UI를새로구현한것은아님.
- 출력/검증/설치/기존JSON백업/비교보고서 outputs/CAD-속도검증-v27. 기존v26전체계산은그대로보존. 입력/연동/수치일관성검사이며실제건물화재물리검증이아님.

'''
old=recovery.read_text('utf8')
if not old.startswith(entry.splitlines()[0]):recovery.write_text(entry+old,'utf8')
ag=ROOT/'AGENTS.md';s=ag.read_text('utf8')
tag='- 2026-10-15 v27: CFAST 성능 작업은 outputs/CAD-속도검증-v27 및 복구기록 최상단 참조. 원 엔진/물리조건 유지, 현 시나리오 최대시간간격0.25초·검증캐시 적용. 30분 계산34분40초→13분29초, 캐시2.28초. 하부층 농도 예외 포함 비교보고서를 읽고 수치차이0이라고 표현하지 않는다. 현재 재현 work/run_cfast_current.ps1. 기존 UI/건물 유지.\n'
if tag not in s:ag.write_text(s.replace('- 현재 사용자의 지시가',tag+'- 현재 사용자의 지시가',1),'utf8')
(p/'active.json').write_text(json.dumps({'status':'complete','report':'full-verification.json','installed':True}),'utf8')
print(json.dumps(r,ensure_ascii=False))
