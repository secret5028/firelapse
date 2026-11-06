PyroCast CFBT 시뮬레이션 확장 / 2026-10-21

최신: 가스 점화 표시·연기 외곽 위험색·계단실 및 반자고 정정
- 이전 R21 점화 대상은 계단실이었다. 최신 예시는 R25 휴게실→R15 홀2→R4 홀3이다.
  원본 DXF의 세 실 3,000 표기를 확인했고, 구조 층고5.5m와 계산 반자고3m를 구분한다.
- 연기는 기존 회색 질감을 유지하고 위험색은 연기 외곽/층 경계·실 윤곽으로 표시한다.
- 사용자 요청으로 FGI 가스 화염 표현은 끈다. 가스 추가연소 계산·온도/O2/OD는 유지한다.
  FGI 가정 점화 재생, 직전/5초후, 기준/점화 토글로 동일시각 온도·O2·OD를 비교한다.
  가스 화염 전면/전파속도/폭압은 해석하지 않는다. 고체 화원 표시는 유지한다.
- 원본 CFAST 및 프로젝트 Fortran은 이번 표시·높이 정정에서 변경/재빌드하지 않았다.
- CAD 연결은 여전히 실당 대표 연료군1개다. FO 이후 실 연료 통합/복사 소수점 분산은
  구현되어 있지만 FO 전 분산 연료별 착화는 미구현이다. 이를 완료로 해석하지 않는다.
- 상세 ../specs/GAS_FLAME_VISUAL_20261021.txt, ../specs/CEILING_CORRECTION_20261021.txt

최신 기본 실행: 실용 탐색 모드(practical)
- CLI/CAD 연결은 경량 기본값, 유한 실행 예산, FO 후 소수 복사 방출점,
  용도별 대표 연료와 한계 표시를 사용한다. 이전 설명/결과는 당시 설정이다.
- 정확한 범위·가정·미구현 항목: ../specs/PRACTICAL_SCOPE_20261021.txt
- python -m pip install --target deps -r requirements.txt
- python tools/connect_cad.py C:/path/to/project --building C:/path/to/building.json --output results/new_building
- 이전 설정 재현: --profile legacy. 기존 결과는 자동 덮어쓰지 않는다.
- tests/check_practical.py는 실제 엔진의 새 건물/FO 연결 시험이다.

목적
사용자 임계값 아래의 위험 가능성을 탐색하는 최소 계산 구현이다. 가스 추가연소는 CFAST 내부, 고체 추가 착화는 외부 이벤트 루프로 구분한다. 전체 운영 앱 교체나 전건물 검증 완료를 뜻하지 않는다.

구현 전 조정한 사항
1) 원본 CFAST와 운영 코드는 비교 기준으로 보존한다. 이 폴더에 CFAST-7.7.7 공식 소스의 별도 확장본을 만들었다. 고체 TIME 화원만으로 가스 재연소를 대신하지 않는다.
2) G-ROOM에는 한 종류의 탐색용 반응 프로파일을 사용한다. 논문의 아직 확인하지 않은 계수를 그대로 검증 상수로 복사하지 않았다.
3) 고체는 초기/추가 연료군별 에너지 예산으로 배정하고, 열분해 공급 기준으로 차감한다.
4) 기본 판 흡수율은 native 비교 및 등온 평형에 맞춰 방사율과 같은 0.9로 두었다. 흡수율 1.0의 유효물성 가정은 설정으로 사용할 수 있으며 별도 시나리오로 기록한다.

가스 계산
extensions/cfbt/fortran/declarations.inc와 routines.inc를 빌드용 fire.f90 사본에 연결한다. 원본 fire.f90은 수정하지 않는다. solve.f90의 기존 잔차 계산에서 가스 연료·산소·잠재 생성물 소비율과 열원을 합산한다.

속도 프로파일:
 k(T,Xo2)=k_ref exp[E/R (1/T_ref−1/T)] (Xo2/0.12)
 연료 소모 요구율 = 기존 미연소 연료 질량 × k(T,Xo2)
실제 소비율은 native 순유출/소비 후의 가용 재고와 native chemistry의 산소·화학량론으로 제한한다. 반응 발열은 상층 에너지 방정식에 넣고, 가스 복사는 native 온도·방출 계산으로 이어진다. 추가 점광원 복사분을 따로 중복 생성하지 않는다.

기본 k_ref=0.1/s, T_ref=800K, E=170000J/mol은 명시한 탐색 프로파일이다. 이 조합을 Kudo 논문의 검증 계수나 범용 연기 반응식이라고 주장하지 않는다. 모든 값은 gas 설정에 저장한다. bulk_enabled/vent_gate_enabled와 임계값을 각각 조절할 수 있다.

산소 입력은 oxygen_min_vol_percent의 체적 백분율이다. native 내부 종별 몰수로 판단한다. native_lower_oxygen_limit_mass_fraction은 기존 화학 계산의 별도 질량분율 설정이며 값과 적용 관계를 결과에 남긴다. vent_ignition_C는 vent_gate가 켜졌을 때 문 분출화염 온도게이트에만 적용된다. native 상층 플룸 연소의 온도게이트를 변경한다는 이전 설명은 잘못됐으며 정정한다.

고체 계산
고정된 판정면의 native 노출 + 부호 있는 문 복사 교체 + 직접 화원 복사 + 문별 DJET 복사를 계산한다. 노출 보완은 수동 판정면에 대한 단방향 근사다.
서로 다른 문에 실 DJET 전체를 반복 배치하지 않고 실제 문별·방향별 연소량을 출력해 사용한다. 현재 부분 개방 기하는 CFAST의 유효 폭 감소에 맞춘 중앙 개방 폭 가정이다.

대표 판의 1D 전도·앞뒤 복사·대류로 착화 조건을 평가한다. 실별 여러 후보가 같은 연료군을 관측하며 연료는 한 번만 활성화된다. 고체 성장·감쇠 곡선의 전체 적분은 배정 에너지와 일치한다.
가장 이른 후보를 포함한 다음 실행이 성공하고 인과 검사를 통과한 뒤 이벤트를 확정한다. 실패·상한에서는 마지막 유효 결과와 미확정 후보를 구분한다. 추가 이벤트 3건/전체 실행 4회가 제안 기본값이다.

폴더
 vendor/cfast-7.7.7/Source : 공식 태그 소스, sources.json에 URL과 해시.
 extensions/cfbt/fortran/  : 직접 작성한 추가 반응·진단 코드.
 extensions/cfbt/hooks.py : 원본에 연결할13개 위치·내용·목적의 명시적 정의.
 build/generated/cfbt/    : 원본+확장으로 자동 생성한 빌드 입력과 출처/차이. 직접 수정하지 않는다.
 pyrocast_cfbt/            : 설정, 입력 생성, 실제 실행, 노출, 판, 확산 루프, 결과 분류.
 tests/                   : 보존·게이트·기본 복원·온도 피드백·착화 이벤트 확인.
 examples/three_rooms.json : 실제 건물이 아닌 명시적 3구획 탐색 입력.
 build/                   : 생성 소스·별도 기준 엔진·확장 엔진. 모두 재생성 가능한 산출물.
 results/                 : 이번 구현의 계산과 검증. 원본 결과에 쓰지 않는다.

실행
이 폴더에서 PowerShell:
 .\run_cfbt.ps1
 .\run_cfbt.ps1 -Scenario 'examples\three_rooms.json' -Output 'results\my_case'
 .\run_cfbt.ps1 -Build

현재 호스트의 bundled Python과 작업 폴더의 휴대용 GNU Fortran을 사용한다. 전역 PATH나 프로그램 설치 설정을 변경하지 않았다. 다른 호스트에서는 Python+NumPy 및 gfortran을 준비하고 아래 순서로 빌드한다.
 python tools/fetch_cfast.py       (공식 소스가 없을 때만, 네트워크 필요)
 python tools/build_engine.py cfbt
 python tools/verify_engine_boundary.py
 python -m pyrocast_cfbt examples/three_rooms.json --output results/three_rooms

확인
 python -m unittest discover -s tests -p test_core.py -v
 python tools/build_engine.py baseline
 python tests/run_native_checks.py
기능 시험은 일부 임계값을 의도적으로 낮춰 연소·확산 경로를 작동시킨다. 그 시각이나 온도를 화재 예측 정확도의 근거로 사용하지 않는다. 동일 소스·컴파일러의 baseline과 확장 OFF를 비교한다.

결과
 result.json : 설정·해시·실 시계열·판·개구부 방향 흐름/연소·중성대·현상 분류·고체 재고.
 summary.json : 종료 사유, 유효 실행, 확정/미확정 이벤트.
 각 run_XX 폴더 : 실제 입력, sidecar, native CSV, case.log, 완료 캐시.
 verification/checks.json : 실제 엔진 기능 시험의 결과.

완료 상태 해석
simulation_complete_to_requested_horizon은 마지막 유효 실행의 시간 완료다.
spread_search_complete는 추가 미참여 고체 후보가 더 없을 때만 true다.
max_added_ignitions/max_runs/time_budget은 확산이 끝났다는 뜻이 아니다.

2026-10-20 CAD/3D 연결 추가
- 최신 결과는 results/cad_opening_30min. 실제 개구부의 수신실 쪽 후보28개,3F 연결14실/고체45℃ 탐색 가정/30분이다. 단일 R9 최초 화점에서 추가4건 후 남은 후보 없음. 전 구획 최초 화점 탐색은 기존 간편 계산식으로 유지한다.
- 저장 결과 '개구부 후보 · 30분 · 고체45℃ 가정'을 선택한다. 연결 개구부·후보면은 노란선, 착화 면/화염 기부는 같은0.76m로 표시한다. 검증은 tests/check_opening30_results.py.
- 기존 건물과 연결한 로컬 재생/재계산 화면을 추가했다. 상세는 CAD_CONNECTION.txt.
- .\start_building_view.ps1 실행 후 표시 URL을 연다. 기존 운영 파일은 유지한다.
- 저장된 전건물156실/100구획, 화재층14실, 고체45℃ 기능 시험을 선택할 수 있다.
- '실감 보기'는 기존 v35 입체 연기·화염·상승 플룸·천장 가스 렌더러를 새 결과에 연결했다. '기본 모드'로 전환 가능하며 상세는 CAD_CONNECTION.txt 참조.
- 실제 CAD 좌표와 native 등가 구획 좌표를 분리했다. native 층간 흐름도 진단/표시에 연결했다.

현재 범위와 남은 연결
- 명시적 직사각형 소형 연결망과 실제 엔진 계산으로 시작했다.
- 기존 CAD 등가 덱의 임의 ORIGIN은 복사 노출에 쓰지 않는다. 새 어댑터가 CAD 문/실 위치와 별도 native 좌표를 보존한다. 별도 연결 화면에서 재계산까지 가능하며 기존 운영 앱 자체를 교체하지 않았다.
- G-ROOM은 상층/단일층만 반응한다. 하층은 native 수송을 유지하며 별도 하층 축적가스 재착화는 미지원이다.
- local 대류 노출 하나를 구현했다. exit 전체 분기, 상세 화염 접촉, 문·벽 파괴, 폭압·압력파, 상층 외벽 확산은 포함하지 않는다.
- 현상 분류는 모델의 반응 기록과 이력에 근거한다. 실제 화염전면이나 폭발 재현을 뜻하지 않는다. 고체 연소 참여 확대는 대표 연료군 범위로 표시한다.
- 고체 잔량은 입력 열분해 곡선의 정확한 적분으로 관리한다. 문 흐름과 native 상태를 출력하지만 모든 누설/기계환기 경로의 독립적인 외부 수지 보고서는 아직 없다.
- 반응 프로파일의 실험 검증, 전건물 위험순위, 다른 컴파일러/운영 바이너리와의 동등성은 별도 확인 대상이다.

요구 기준
../specs/CFBT-가스연소-고체확산-통합최종명세-20261020.txt

2026-10-21 FO 연소 상태 전환 추가
- flashover.enabled=true로 온도 임계값 후 남은 연료를 실 단위로 통합하고 공급을 확대한다. 기본OFF이며 criteria.fo_temperature_C=600을 사용자가 바꿀 수 있다.
- 공급 램프/HRRPUA는 탐색 설정이다. 실제 연소량·온도·산소·연기는 기존 CFAST 수지로 계산한다. 고체 상세 열분해/기화 또는 NIST 인증 기능을 뜻하지 않는다.
- 독립 기능 입력 examples/fo_transition_check.json과 실제 결과 results/fo_transition_check, 검사 results/verification/fo_transition_checks.json을 추가했다.
- python -m pyrocast_cfbt examples/fo_transition_check.json --output results/fo_transition_check
- python tests/check_fo_results.py
- CAD용 설정 전달 예시 examples/cad_fo600_30min.json. 기존 R9 저장값은600℃에 미도달이라 전환 후보0건이다. 기존 건물 결과/3D를 덮어쓰지 않았다.
- 상세 수식·NIST 근거·가정·검증 범위: ../specs/FO-연소상태전환-구현검증-20261021.txt.

2026-10-21 원본/확장 코드 분리
- 분리 구조·기능별 출처·작업 규칙: SOURCE_BOUNDARIES.txt.
- vendor 원본28개와 고정sources.json의 해시를 검사한다. 기존 원본은 다운로드 명령으로도 덮어쓰지 않는다.
- baseline 빌드는 vendor 원본만 사용하고, cfbt 빌드는 명시적 연결 규칙에서 생성한28개 빌드 입력을 사용한다.
- 과거 engine/ 전체 사본은 새 생성본과 바이트 일치를 확인한 뒤 제거했다. 과거 native/의 두 추가 코드 파일은 extensions/cfbt/fortran/으로 내용 변경 없이 이동했다.
- MANIFEST.json과 CFAST_DIFF.patch는 build/generated/cfbt/에 자동 생성한다. build.json에는 파일별 원본/수정 구분과 확장 코드 해시를 기록한다.
- 검증용 재빌드는 build/engine-boundary-check에 격리했다. 기존 실행 바이너리·저장 건물 결과·3D 화면은 보존한다.

2026-10-21 일괄 반복 실행·조건 표시
- spread.iteration_mode: earliest_single(기본, 기존 경로) / fixed_point(경고 포함 탐색 옵션).
- fixed_point도 매 회차0초부터 재실행한다. 일괄 사건 추가로 회차를 줄이며 native 상태 복원은 구현하지 않았다.
- max_passes는 초기 실행을 포함한 완료 결과 평가 횟수. max_runs는 재시도 포함 native 시도 횟수.
- 일정 안정과 조건 재확인은 별도이며 later_or_missing/자기 발열 경계 경고가 있으면 완전 탐색으로 표시하지 않는다.
- 실측/한계: results/iteration_benchmark_20261021/REPORT.txt, comparison.json.
- 재현: tools/benchmark_iteration.py --horizon-cost (native 엔진 경로와 출력 폴더를 명시해 별도 측정 가능).
- 실제 소규모 회귀: tests/check_iteration_native.py. 표시 분리: node tests/check_risk_split.mjs.
- 조건표는 기존 criteria/gas 설정을 사용한다. 개구부 연소는 방향별 native 값, 상층은 프로젝트 bulk 항이다.
- UI/API 기간은3600초까지 허용하지만 현재 기본 재생은 기존1800초 계산을 유지한다.
