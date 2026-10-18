from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parent.parent
out=root/'outputs/CAD-NIST가연물-v23'
app=Path('C:/Users/예방/Desktop/소방 크로키 업-로컬웹앱')
job=app/'data/d018b4bb75da4475b1fd75447603c1a0/cad-output'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(job/'model.html')==sha(out/'model.html')==sha(app/'_internal/cad_engine/integrated_viewer.html')
assert sha(job/'cfast-demo.json')==sha(out/'cfast-demo.json')
d=json.loads((out/'cfast-demo.json').read_text('utf8'))
assert sha(job/'building.json')==d['building_sha256']
verification=json.loads((out/'검증결과.json').read_text('utf8'))
report=dict(status='installed',url='http://127.0.0.1:8778/cad-result/d018b4bb75da4475b1fd75447603c1a0/model.html',
    model_sha256=sha(job/'model.html'),results_sha256=sha(job/'cfast-demo.json'),building_sha256=d['building_sha256'],
    mode=d['calculation_mode'],verification=verification,physical_validation=False,
    browser_checks=['NIST 3.31MW curve visible','0s: no smoke or flame','380s: 3257kW and visible flame',
                    '1800s: 45 smoke display rooms and 0 secondary ignitions','legacy controls and wall transparency preserved','no browser error logs'],
    screenshots=['화면-NIST적용.png','화면-30분.png'])
(out/'설치기록.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
summary='\n'.join(f"- {t['room']} {t['id']}: "+('30분 내 미착화' if t['ignition_time'] is None else f"착화 {t['ignition_time']}초")+f", 최고 표면온도 {t['max_surface_C']:.2f}°C" for t in verification['targets'])
notes=f'''NIST 실험자료 기반 대표 가연물 적용 v23 — 2026-10-15

선정
3F 공작실/설비보관실·인접 A/S실은 작업대·전자기기·사무 가구 시나리오로 해석했다. 건물 전체를 사무실로 가정하거나 실제 비치품을 확인한 것이 아니다. 산업공정 원료·창고 고밀도 적재·차량은 별도 연료군이다.

최초 화재: NIST SP1021 그림71(본문54쪽 / PDF59쪽)
https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication1021.pdf
작업대, 컴퓨터, 의자, 서류 등을 포함한 단일 작업대 묶음 개방 연소시험. PDF의 붉은 측정점 중심을 추출하여 시간/HRR로 환산했다. 원 계측 CSV가 아닌 도표 수치화이며 진폭·시간을 확대하지 않았다. 50kW/200초 점화 버너가 포함된 측정값을 그대로 사용하므로 추가 버너를 중복 계산하지 않는다.
입력 최고 {d['design_fire']['peak_kW']:.2f}kW, 379.09초. 30분 입력열량 {d['design_fire']['prescribed_energy_MJ']:.3f}MJ. 원 도표 적분 대비 190점 축약 오차 -0.093%. 마지막 0.9초만 최종 측정점 값 연장. 30분 초과는 근거 없이 외삽하지 못하도록 제한했다.
화원면적5.95m²는 시험 플랫폼 등가 면적이며 실제 순간 연소면적의 측정값이 아니다. 연소열18.1MJ/kg, 원소조성, CO/그을음 수율, 복사분율0.33은 대리연료 가정이다. 따라서 입력 열량에서 환산한 kg을 건물 실제 가연물 질량으로 해석하면 안 된다.

추가 착화: NIST NCSTAR1-5C 표A-2(본문73쪽)·그림A-13(본문91쪽)
https://nvlpubs.nist.gov/nistpubs/Legacy/NCSTAR/ncstar1-5c.pdf
특정28mm 책상 상판의 점화원 존재 시험 온도407±10°C를 채택. 모든 목재 공통값이나 자연발화 온도가 아니다. 열응답 적합값 k0.100416W/(mK), rho700kg/m³, cp5.8576kJ/(kgK), 방사율0.95. 이 값은 1차원 열응답 보정값으로 실제 가구 재고 질량 추정에 사용하지 않는다.
원 콘 시험은 후면 단열이다. CFAST7.7.7의 기본 PLATE는 양면 열전달을 계산하며 이번에는 그 기본 모델로 옮겼다. ADIABATIC_TARGET은 후면 단열 옵션이 아니라 단열표면온도 계산이므로 사용하지 않았다. 시험과 동일한 경계조건 재현 또는 이 건물의 물리 검증으로 표현하지 않는다.
45kW/m² 노출 시험의 총열량212MJ/m²·전체 평균연소시간1739초로 보고서가 설명하는 등가 사각형 HRR을 구성. 별도상판1.2m²당146.29kW,254.4MJ. 착화 후 노출변화에 따른 열분해율을 동적으로 예측하지는 않는다.
별도 대상2개: 3F_R9, 3F_R8. 상판2m×0.6m, 높이0.75m 및 위치는 시나리오 가정이며 최초 묶음의 가구와 별도 재고로 정의했다. 점화원 존재는 가정이고 실제 이동을 계산하지 않는다. 표면407°C 미만이면 착화하지 않으며 연기가 보인다는 이유로 화염을 추가하지 않는다.

계산 결과
{summary}
- 전체 최고 HRR {max(d['total_hrr']):.2f}kW, CFAST 정상 종료 {d['elapsed_seconds']:.3f}초.
- 기존 일반 실내문100%, 외부문50%, 창닫힘, 승강기문1%누설, 소화설비미작동 조건 유지.
- 156표시구획/100계산구획/36층간연결 및 기존 건물 데이터·레거시 UI 유지.
- 검증결과.json은 입력/데이터/연동 검사이며 실제 화재 정확도 검증이 아니다.

재현
python work/build_nist_fuels_v23.py
python work/cad_cfast_multifloor.py --duration 1800 --output CAD-NIST가연물-v23
python work/restore_cad_ui.py CAD-NIST가연물-v23
python work/verify_cfast_v23.py
최초 화재만 계산: --no-secondary. 이전1MW비교조건: --design-fire work/cfast_design_fire.json --no-secondary --output <별도이름>.
apply_nist_v23.py는 일회 마이그레이션이므로 재실행하지 않는다.
'''
(out/'선정근거와-적용범위.txt').write_text(notes,'utf8')
recovery=root/'outputs/작업기준-복구-20261014.txt'
entry=f'''최신 적용 — NIST 대표 가연물 및 조건부 착화 v23 (2026-10-15)
- 사용자 요청: 임의1MW 대신 건물용도에 맞는 NIST실험 대표가연물·화재크기 적용, 근거 있는 추가착화.
- 3F_R9 작업대·전자기기·의자·서류 묶음: SP1021그림71 수치화. 최대3.307MW/379초,30분1583.377MJ. 측정CSV가 아닌 도표 복원. 연소열/수율/조성은 기존 대리 가정으로 명시.
- 별도 상판2개에 NCSTAR1-5C표A2·그림A13의407°C(점화원 존재) 조건. 보정 열물성 및 45kW/m²콘 시험의 전체 평균 등가HRR146.29kW/254.4MJ 적용. 위치·재고·점화원·열경계 전환은 가정, 원 시험 재현 아님.
{summary}
- CFAST1800초 정상종료 {d['elapsed_seconds']:.3f}초. 기존 UI/추출/3D/층간경로 유지, 격자자동배치 재개 없음. 실측구조·물리검증과 자동검사 구분.
- 기본 실행은 work/cad_cfast_multifloor.py, design=cfast_nist_design_fire.json, ignition=cfast_nist_ignition.json, 재료=cfast_nist_desk.json. --no-secondary로 최초화재만. 기존 t²구성도 지원.
- 출력/출처/검증/설치/백업: outputs/CAD-NIST가연물-v23. 상세 '선정근거와-적용범위.txt'. 기존 로컬앱model.html,cfast-demo.json,설치template 갱신.

'''
previous=recovery.read_text('utf8')
if not previous.startswith(entry.splitlines()[0]):recovery.write_text(entry+previous,'utf8')
print(json.dumps(report,ensure_ascii=False))
