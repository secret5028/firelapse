from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parent.parent
out=root/'outputs/CAD-조건부전이-v26'
app=Path('C:/Users/<user>/Desktop/소방 크로키 업-로컬웹앱')
job=app/'data/d018b4bb75da4475b1fd75447603c1a0/cad-output'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(job/'model.html')==sha(out/'model.html')==sha(app/'_internal/cad_engine/integrated_viewer.html')
assert sha(job/'cfast-demo.json')==sha(out/'cfast-demo.json')
d=json.loads((out/'cfast-demo.json').read_text('utf8'))
v=json.loads((out/'검증결과.json').read_text('utf8'))
assert sha(job/'building.json')==d['building_sha256']
browser=json.loads((out/'브라우저검증.json').read_text('utf8'))
report=dict(status='installed',url='http://127.0.0.1:8778/cad-result/d018b4bb75da4475b1fd75447603c1a0/model.html',
    model_sha256=sha(job/'model.html'),results_sha256=sha(job/'cfast-demo.json'),building_sha256=d['building_sha256'],
    verification=v,browser_checks=browser,physical_validation=False)
(out/'설치기록.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
summary='\n'.join(f"- {t['room']} {t['name']}: "+('30분 내 미착화' if t['ignition_time'] is None else f"첫 착화 출력 {t['ignition_time']}초")+f", 최고 표면온도 {t['max_surface_C']:.2f}°C" for t in v['targets'])
notes=f'''CFAST 조건부 전이 시나리오 v26 — 2026-10-15

요청: NIST 지침/자료에 근거하여 모델 범위에 맞는 추가 착화 조건을 선택하고 계산.

설정
- 3F_R9 공작실/설비보관실 최초 화재는 v23의 SP1021 그림71 단일 작업대 묶음 HRR 그대로. 최고 입력3.307MW. 실측 원CSV가 아닌 PDF 도표 수치화이다.
- 최초 묶음 외에 같은 방에 작업대 묶음2개, 홀R2와 A/S실R8에 각1개. 실제 비치품 조사가 아닌 밀집 가구 시나리오. 각 면적5.95m², 작업실 중심 간격2.6m/표시 폭2.44m로 약0.16m 이격. 가구 면적은 서로 겹치지 않는다.
- 같은 방 대상은 중심보다 화원에 가까운 서류 노출면(최초 화원 중심에서1.38m, 북측 높이0.75m/남측0.90m)에 PLATE 타깃을 둠. 화원 중심과 착화 판단 표면 위치를 별도로 지정하도록 코드 지원. 홀/A/S는 구획 중심 상향 노출면.
- NCSTAR1-5C 그림A16(인쇄93쪽/PDF129쪽): 종이 적층물의 점화원 존재 착화온도369°C. k=.04184W/mK, rho500kg/m³, cp2.092kJ/kgK, 두께25mm, 방사율.95. 시험 열응답 적합값이며 보편적 종이 상수나 자연발화 온도가 아니다.
- CFAST native FIRE IGNITION_CRITERION=TEMPERATURE, DEVC_ID, SETPOINT=369. 조건 미달은 HRR0. 각 표면의 점화원 존재는 가정이며 점화원 이동을 계산하지 않는다.
- 착화 후 전체 작업대 묶음의 SP1021 지정 HRR 사용. 원 곡선의 초기200초 nominal50kW 버너 기여를 빼고 음수를0으로 절단하여 별도 점화 버너를 중복 넣지 않음. 원 시험 분리 계측값이 아닌 근사. 가구 내부 연쇄 착화를 하나의 지정 화원으로 대리한 설계 가정이다.
- 원 콘 시험 후면 단열/수평 노출과 CFAST 기본 양면 PLATE/작업실 수직 노출은 다름. 원 시험의 재현이나 이 건물의 검증된 전파율로 표현하지 않는다.
- R9 계산 구획만 CAD 경계 종횡비를 유지하는 등면적 직사각형으로 변경하여 3개 묶음의 길이방향 배치를 수용. 실제 CAD 데이터/추출/3D/층고는 변경 없음.
- 일반 실내문100%, 외부문50%, 창닫힘, 승강기문1%누설, 소화설비미작동 유지. 벽/바닥/천장15cm 콘크리트, CO/soot수율·연소열·복사분율은 기존 대리 가정.

동시착화 실행 점검
완전 대칭(양쪽0.75m) 배치에서 두번째 대상의 IGN=1이지만 native 착화 로그/HRR가 없는 불일치를 발견했다. 1구획 진단에서도 재현되어 해당 전층 계산을 중단했고 symmetric-aborted 및 diagnostic-symmetry에 보존했다. 남측 노출면 높이0.90m로 서로 다른 배치를 선택한 진단은 두 대상 로그/HRR 모두 정상. 이 최종 배치에서도 로그·IGN·HRR 일치를 검사한다. 기준온도나 엔진을 수정하지 않았으며, CFAST 자체의 모든 동시착화 문제를 해결한 것으로 표현하지 않는다.

계산 범위
CFAST 같은 구획의 화원 복사열과 구획/경계면 열환경으로 대상 표면 가열을 계산한다. 현재 native target.f90는 화원과 타깃의 구획이 같은 경우만 직접 화원 복사열을 합산한다. 다른 방의 문너머 국소 불꽃/직접 복사열/천장 연속 화염은 이 결과에 포함되지 않는다. R9와R8은 벽의 직접 개구부가 없고 홀R2를 거친다. 미착화 결과는 이 시나리오와 이 모델 범위에 한정된다.

결과
{summary}
- 총 HRR은 등록 화원 + CFAST 개구부 미연소 가스 연소(DJET, 외기 포함). 등록 화원 합 최대{v["registered_fire_peak_kW"]:.2f}kW, 개구부 연소 합 최대{v["vent_jet_peak_kW"]:.2f}kW. 각각의 최대 시점은 다를 수 있다. 개구부 연소 열은 native 계산에 이미 반영되나 국소 화염 형상은 아직 표시하지 않는다.
- 전체 최대 실제HRR {v['actual_total_peak_kW']:.2f}kW. 1800초 정상 종료, 계산 소요 {d['elapsed_seconds']:.3f}초.
- 100계산구획/156표시공간/36수직경로. 열·연기/새 화재는 같은 CFAST 계산 안에서 피드백.
- 5초 간격 출력의 첫 IGN 시각이며 정확한 연속 착화 순간은 아님.
- 기존 UI와 연기보다 화염을 위에 표시하는 v24/v25 렌더링 보존. 작은 화염 최소크기는 식별용 표시 확대.
- 검증결과.json은 정상종료/수치/입력/연동 검사이며 실제 건물 물리검증이 아님.

출처
https://github.com/firemodels/cfast/blob/master/Manuals/CFAST_Users_Guide/Input_File_Chapter.tex
https://github.com/firemodels/cfast/blob/master/Source/CFAST/target.f90
https://nvlpubs.nist.gov/nistpubs/Legacy/NCSTAR/ncstar1-5c.pdf
https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication1021.pdf

재현
python work/build_spread_v26.py
python work/cad_cfast_multifloor.py --duration 1800 --ignition-config work/cfast_spread_scenario_v26.json --output CAD-조건부전이-v26
python work/restore_cad_ui.py CAD-조건부전이-v26
python work/verify_cfast_v26.py
work/install_cfast_v26.ps1
runner 기본 시나리오는 v23 그대로이며 이번 것은 위 명시 옵션으로 선택. 이전결과는 backup 및 v23 폴더에 보존.
'''
(out/'선정근거와-계산결과.txt').write_text(notes,'utf8')
entry=f'''최신 적용 — NIST 근거 조건부 전이 v26 (2026-10-15)
- 사용자 승인: NIST 매뉴얼/관련문서 범위에 맞는 전이조건 선택 후 실행.
- 최초 SP1021 작업대 곡선 유지. R9내 추가2개/홀R2와A/S R8 각1개 작업대 묶음. 밀집 배치/각표면 점화원 존재 가정. 종이369°C(NCSTAR1-5C A16) native 조건부 착화. 표면과 화원중심 위치 분리, R9 등면적 CAD종횡비 반영.
- 서류 조건 충족→전체 묶음 지정HRR은 설계 대리모델, 검증된 내부 화염전파가 아님. 추가곡선 초기200초 nominal50kW 버너 제거 근사. 다른 방 직접 화원복사/문·천장국소 화염은 미계산.
{summary}
- 30분 정상종료 {d['elapsed_seconds']:.3f}초, 실제최대총HRR {v['actual_total_peak_kW']:.2f}kW. 기본문조건/층간경로/건물해시/레거시UI 및 v25화염가시성 유지.
- 완전대칭 동시착화에서 native IGN/로그/HRR 불일치 재현. 남측 서류면0.90m/북측0.75m의 비대칭 배치로 재계산, 불일치 시 출력 적용을 막는 검사 추가. 엔진 자체 수정 아님. 진단과 중단 계산 보존.
- 총 HRR에 native DJET 개구부 연소 포함. 문/천장 연속 화염 형상은 별도 향후작업 유지.
- 현 앱에는 v26결과 적용. runner기본v23와 구별. 재현은 work/cfast_spread_scenario_v26.json 명시. 출력/설치/백업/화면/근거 outputs/CAD-조건부전이-v26. 입력/연동검사이며 물리검증 아님.

'''
recovery=root/'outputs/작업기준-복구-20261014.txt';previous=recovery.read_text('utf8')
if not previous.startswith(entry.splitlines()[0]):recovery.write_text(entry+previous,'utf8')
print(json.dumps(dict(status=report['status'],targets=v['targets']),ensure_ascii=False))
