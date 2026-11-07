
FireLapse 물리·로직 수정 지시서 (Codex 인계용)
대상 저장소: secret5028/firelapse, 검토 기준 커밋 26cb3d7 (2026-11-08)
모든 경로는 저장소 루트 기준이고, 라인 번호는 위 커밋 기준이다. 코드가 바뀌었으면 함수 이름으로 다시 찾을 것.
증거 데이터: 사용자 PC에서 실제로 돌린 계산 결과 두 건 (%LOCALAPPDATA%\FireLapse\results\fixed-calculations\c3f428a9…\calc-*)
대상: 파크마린호텔 B3 지하주차장, 화점 CAD_B3_R6, CFAST 엔진
run1 calc-1794062661…: 최대 열방출률 약 1.4 MW
run2 calc-1794063121…: 요청값 7 MW
0. 작업 규칙 (Codex에게)
우선순위 순서(P0 → P3)로 진행한다. 항목 하나당 커밋 하나로 하고, 커밋 메시지에 항목 ID(예: P0-1)를 넣는다.
고친 동작마다 회귀 테스트를 PyroCast/simulation/tests/나 PyroCast/app/tests/에 추가한다.
현재 테스트는 unittest로 돈다. 상태는 Lite 13개 모듈 기준 68개 실행, 51개 통과, 8개 에러, 9개 건너뜀.
에러 8개는 모두 simulation/results/room_rule_r8_20261025/source-scenario.json 고정 데이터가 빠져서 생긴 FileNotFoundError다. P3-6에서 함께 정리한다.
지수 정의를 바꾸면 기존 저장 결과와 호환이 깨진다. 그러므로:
condition_version 또는 *_REVISION 상수를 올리고, 옛 버전으로 만든 playback은 UI에서 "구버전 지수"로 표시한다.
지수를 다시 계산하는 경로가 있으면(tools/refresh_*.py) 함께 고친다.
물리 상수나 가정을 새로 넣을 때는 근거를 주석으로 남기고, 설정 파일(config/*.json, rule_settings)로 뺀다. 숫자를 코드에 박아 넣지 않는다.
PyroCast/simulation/viewer/overlay.js는 빌드 결과물이다. 원본은 PyroCast/app/web/** 이므로 원본을 고치고 다시 빌드한다.
1. 사용자가 본 증상과 원인 요약
증상: 환기가 거의 없는 지하주차장 화재인데 백드래프트·FGI 지수가 너무 낮게 나온다(FO 17, FGI 15, BD 13 / 최고 FGI 36, BD 33). 연기가 고여 산소가 떨어지고 미연소 연료가 쌓이는 지하 화재라면 BD·FGI가 높아야 한다.

핵심 증거 (run2, 연료·산소 조건은 이미 충족했는데 온도 요소가 점수를 깎은 경우):

실	표시 최대	연료·산소 모두 ≥1인 시간	온도 요소를 빼면	그때 상층 온도
R6_C1 (화점) BD	33	635 s	336	35 ℃
R6_C1 (화점) FGI	36	1380 s	129	62 ℃
R6_C0/C2 FGI	31	1945 s	128	52 ℃
R0_C0/C1 FGI	13–14	770–905 s	134	26–27 ℃
R3 FGI	11	685 s	131	24 ℃
즉 점수가 낮은 주원인은 Tu[℃]/300 온도 요소다(P0-4). 아래의 밀폐 문제(A)는 점수를 낮추는 원인이 아니라, 결과 수치(압력 45 kPa, 연료 78 %)의 신뢰성 문제다.

원인은 두 층으로 겹쳐 있다.

A. 계산 입력 자체가 물리적으로 불가능한 상태다 (CFAST 경로).

B3 계산 입력(deck)에서 17개 구획이 모두 LEAK_AREA_RATIO=0,0이다. 외기(OUTSIDE)로 나가는 벤트가 0개이고 기계환기(MVENT)도 0개다. 즉 완전 밀폐 상자다.
그 결과 CFAST 구획 압력이 +28 ~ +45 kPa 까지 오른다. 실제 건물이라면 수백 Pa에서 문과 창이 파손된다.
처방된 열분해는 계속 공급되는데 산소가 부족해 타지 못한다. 그래서 상층 미연소 탄화수소 질량분율이 0.78까지 쌓인다. 처방 발열 22.1 GJ 중 실제 연소는 3.8 GJ뿐이다.
이런 결과도 아무 검증 없이 complete로 표시된다.
B. 지수 공식이 물리적으로 틀렸다 (공통).

지수는 degree = min(온도비, 연료비, 산소비)다. 그런데 온도비가 ℃끼리의 비(Tu[℃]/300)다.
FGI와 BD가 모두 같은 온도 요소 Tu/300에 묶여 있어서, 두 지수가 사실상 같은 숫자가 된다. 실측에서 1200 s 이후 FGI = BD였다.
FGI는 차갑게 고인 예혼합 연기 현상인데 온도가 높을수록 점수가 오른다. 또 불이 타고 있는 셀 자체에도 FGI를 매긴다.
롤오버는 FGI 점수를 빌려서 정의했고, 게다가 원래 롤오버가 일어나는 발화실을 오히려 제외한다.
C. 안전 측면에서 더 위험한 반대 문제도 있다.

run2, 화점 셀 3300 s: 열방출률 0, 상층 온도 35 ℃, 상층 산소 3 %, 연료 질량분율 0.78. 전형적인 백드래프트 직전 상태다.
그런데 BD 지수는 온도 요소(35/300) 하나 때문에 11.7에 머문다.
그래서 전술 규칙 C-1(FO, FGI, BD 모두 70 미만)이 맞아떨어져 "전진"을 권고한다.
P0 — 결과 신뢰성 차단 (최우선)
P0-1. 밀폐 계산 영역에 최소 누기 자동 적용 (계산 차단 아님)
사용자 결정 (2026-11-08): 지하처럼 외기 경로가 없는 계산도 허용한다. 다만 완전 밀폐(누기 0)는 압력이 수만 Pa로 오르는 비물리적 상태이므로, 최소 누기를 넣어서 계산한다. 저환기 상태(산소 저하, 연료 축적)는 그대로 유지해야 한다. 목적은 압력만 현실 범위로 두는 것이다.

파일:
PyroCast/simulation/pyrocast_cfbt/model.py:88-97: 지하층은 누기를 0으로 강제한다.
pyrocast_cfbt/cad.py:193-194: 단일층 계산에서 계단과 승강로를 닫힌 경계로 둔다.
cad.py:259: 램프→외기 연결을 not selected_floor일 때만 넣는다. 이 건물은 모든 층에 model_ramps가 0개다.
cad.py:272-288: 도달 가능성을 실↔실 연결로만 본다.
수정:
model.normalize의 마지막 단계에서 화점실을 출발점으로 연결 그래프를 만든다. 간선은 다음 세 가지다.
max(schedule)>0인 벤트
누기 > 0
MECHANICAL 벤트
이 그래프에 OUTSIDE까지 가는 경로가 없으면 계산을 막지 않는다. 대신 최소 누기 경로를 자동으로 추가한다.
위치: 실제로 건물 다른 곳과 이어지는 곳. 계단실과 승강로 구획이 우선이고, 없으면 화점과 연결된 구획 중 가장 큰 실이다. 흙에 닿은 지하 외벽 전체에 고르게 누기를 주지 않는다.
형태: CFAST &VENT TYPE='WALL' COMP_IDS='<구획>','OUTSIDE'의 작은 틈새 벤트. 기준은 "닫힌 계단 방화문 틈새"이고, 절대 면적(m²)으로 넣는다.
기본값 예: 계단실 문 1개당 0.02 m², 승강로 1개당 0.06 m². 이 값은 이미 pyrocast_lite/core.py PRM의 shaft_floor_leak, elev_leak에 있으므로 같은 설정값을 공유한다.
높이: 바닥에서 2.1 m 문 높이 전체.
값은 config/rule_settings(또는 새 leakage_defaults)에서 읽고, 사용자가 화면에서 바꿀 수 있게 한다.
결과의 limits와 화면 상단에 "최소 누기 가정 적용: <구획 목록>, 총 X m²"를 표시한다.
Lite(간이) 엔진에도 같은 가정을 적용해, 두 엔진의 경계 조건을 같게 한다.
지하층 기본 누기 0 처리(벽 전체 누기 비율 대신)는 유지한다. 단, 판정 기준을 층 이름 정규식 대신 floor['below_grade'] 또는 z < grade로 바꾼다.
지금 정규식은 P1, B-1, Basement 1, -1F를 놓친다.
어떤 층을 지하로 판정했는지 경고 목록에 남긴다.
최소 누기를 넣어도 P0-2의 압력 검사(예: |PRS| > 1000 Pa)에 걸리면 physically_invalid로 표시한다. 누기 값을 키워 다시 계산하라는 안내를 함께 띄운다.
완료 기준:
B3 단일층(외기 경로 없음)을 계산하면 최소 누기가 자동으로 붙고, 그 사실이 화면에 표시된다.
구획 압력이 1000 Pa 이하로 유지된다.
화점 셀 상층 산소가 여전히 저하된다(저환기 특성 유지). 이를 확인하는 테스트를 추가한다.
P0-2. CFAST 결과의 물리 타당성 검증
파일: pyrocast_cfbt/native.py:154-167(지금은 종료코드와 "NORMAL EXIT"만 확인), tools/fixed_calculation.py:267-279, tools/fixed_native_playback.py:37-107
수정: validate_native(result, model)를 새로 만든다.
호출 위치: completed.json을 쓰기 직전, 그리고 playback을 패키징할 때.
아래 중 하나라도 맞으면 physically_invalid로 표시한다.
max|PRS_i| > 1000 Pa (기준값은 설정 가능하게)
질량 수지 오차 > 5 %: case_masses.csv 화학종 합의 증가량 대비 (∫ΣPYROL + ∫외부 유입)
참고: run2에서 +1551 kg 증가했는데 열분해 적분은 1220 kg으로 약 27 % 불일치(Plausible)
처방 화재가 진행 중인데 ∫HRR/∫HRR_E < 0.5
상층 TUHC 질량분율 > 0.3
표시는 status.json과 playback의 limits에 기록한다. UI는 이 결과를 정상 결과처럼 보여주지 말고 상단에 붉은 배너와 지수 비활성화로 처리한다.
완료 기준: 현재 run2를 다시 패키징하면 physically_invalid(사유: 압력, 미연소 연료)가 나온다.
P0-3. 지하주차장 환기 모델링 지원
파일: pyrocast_cfbt/deck.py:129-141(WALL/FLOOR 벤트만 출력), cad.py:259-271(램프)
수정:
model['mechanical_vents'] 스키마를 추가한다: id, comp, flow_m3_s, area, height, orientation, cutoffs.
출력 형식: &VENT TYPE='MECHANICAL' COMP_IDS='OUTSIDE','<room>' AREAS=… HEIGHTS=… FLOWRATE=… CUTOFFS=200,300 ORIENTATIONS='VERTICAL'
use=='parking'인 층에는 기본 배기량(사용자 입력, 기본 예시 6 ACH)과 급기 또는 램프 개구부를 제안한다. 없으면 경고한다.
램프는 단일층 범위에서도 외기 연결로 유지한다.
모양은 주차장 천장 FLOOR 벤트가 아니다. 램프 입구 높이에 둔 외기 WALL 벤트다.
램프 데이터가 없으면 UI에서 입력받는다.
완료 기준: 환기를 지정한 B3 계산에서 구획 압력이 ±200 Pa 이내에 머문다.
P0-4. 위험 지수 공식 재정의 (공통 모듈 하나로)
현재 정의가 4~5벌로 갈라져 있다.

경로	FO	BD	FGI
Lite pyrocast_lite/core.py:515-519	Tu≥600	Yf≥0.10 ∧ O2<12 ∧ deep	Yf≥LFL(T) ∧ O2≥12 ∧ Tu<T_ai ∧ deep
공유 불리언 pyrocast_cfbt/conditions.py:172-192	own_fire ∧ (Tu≥600 ∨ flux≥20)	Yf≥0.1 ∧ Tu≥300 ∧ O2<10	Yf≥0.005 ∧ O2≥10 ∧ no_solid ∧ no_bulk
공유 점수 conditions.py:229-253	min(Tu/600, Q/Q_Thomas, O2하층/12)	min(Tu/300, Yf/0.1, 10/O2)	min(Tu/300, Yf/LFL≈0.06, O2/10)
네이티브 tools/fixed_native_playback.py:84-87	점수만(불리언 없음)	점수만	점수만
MC pyrocast_lite/montecarlo.py:136	–	Yf≥0.1 ∧ O2<12 ∧ Tu≥hot_C	–
수정: pyrocast_cfbt/criteria.py(새 파일) 하나로 통일한다. Lite core, conditions.evaluate, 네이티브 패키저, MC가 모두 이 모듈을 쓴다. 임계값은 model['criteria'] 한 곳에서만 읽는다. 각 현상은 gate(해당 여부)와 proximity(근접도), 그리고 occurred(불리언)를 함께 낸다.

공통 규칙:

층 두께 H − h < d_min(0.3 m)이면 전부 null(미평가)로 둔다. 현재 공유 경로에는 이 조건이 없다.
근거: run2 3000-3600 s에 상층이 약 6 cm 두께인데 Yf 0.78로 평가됐다.
온도비는 p_T = max(0, (Tu − T_amb)/(T_crit − T_amb))로 계산한다. ℃끼리의 비는 금지한다. T_amb = model['ambient_C'].
산소 기준은 솔버의 하한 산소 농도(native_lower_oxygen_limit_mass_fraction)에서 부피%로 환산해 맞춘다.
FO

gate      = own_fire ∨ 수용 화염(문 제트)              # 물리 실(parent_room) 단위로 평가 (P1-4)
proximity = max(p_T(600℃), q_floor/20 kW/m²)        # 불리언의 OR과 일치
occurred  = gate ∧ (Tu≥600 ∨ q_floor≥20)
Thomas Q/Q_FO와 하층 산소비는 근접도에서 뺀다. 별도 진단값으로만 남기고 "셀·대공간에서는 무효" 표시를 붙인다.
FGI

gate      = ¬own_solid ∧ ¬bulk ∧ room∉origins ∧ Tu < gas_ignition_C ∧ deep
p_F       = Yf / Y_LFL(T)   (Yf > Y_UFL(T) 이면 0 으로 두고 'too_rich' 플래그)
p_O       = X_O2 / X_LOC
proximity = gate ? min(p_F, p_O) : null    # 온도 요소 없음
occurred  = gate ∧ p_F≥1 ∧ p_O≥1
원격 점화원(인접 화염실, 수용 문 제트)은 점수에 넣지 않고 별도 플래그로 둔다.
연료 임계값은 불리언(0.005)과 점수(LFL≈0.06)가 약 12배 다르다. 하나로 통일한다.
BD

potential = deep ? min(Yf/0.10, (20.9−X_O2)/(20.9−X_def)) : null   # 온도는 표시용 보조값
occurred  = potential≥1 ∧ [t−W, t] 안에 해당 실 개구부 개방률 증가 또는 창 파손
개구부를 고정한 계산(fixed_native_playback.py:50-52)에서는 BD가 실제로 일어날 수 없다. 이 경우 라벨을 "BD 잠재(개방 시)" 로 한다.
롤오버: FGI와 분리한다.

rollover = (Qbulk > q_min ∨ 화염높이 ≥ 천장 ∨ (Tu ≥ gas_ignition_C ∧ LFL≤Yf≤UFL ∧ X_O2≥X_LOC)) ∧ deep
발화실도 포함한다. 지금은 conditions.py:38-40에서 excluded_origin으로 빠져 있다.
현재 rollover_states는 이름을 "인접실 원격점화 FGI 조건"으로 바꾼다.
완료 기준:

run1과 run2의 B3 화점 셀에서 FGI가 null(gate false)로 나온다.
run2 3300 s의 화점 셀은 BD potential ≥ 1이다. P0-1의 최소 누기를 넣고 다시 계산해도 BD potential ≥ 1이 유지돼야 한다.
상온 무연기 실의 모든 지수가 0 또는 null이다.
P0-5. 전술 규칙의 위험 과소 평가 수정
파일: PyroCast/config/tactic_rules.json, tools/d5_match.py:47-55
문제 1: C-1(scope null, FO<70 ∧ FGI<70 ∧ BD<70 → "전진")이 산소 3 %, Yf 0.78인 화점 셀에도 맞는다.
문제 2: X-1, G-1, E-2는 "차가운 가스"를 전제한 규칙이다. 그런데 현재 점수로 FGI≥70이 되려면 Tu≥210 ℃가 필요하다. G-1은 아예 온도 상승을 조건으로 요구해 FGI 물리와 정반대다.
수정:
C-1에 BD.potential<1 ∧ FGI.proximity<1 ∧ (P0-2 유효성 통과)를 추가한다. 무효 결과에는 어떤 전술도 권고하지 않는다.
온도와 무관한 규칙을 추가한다: Yf≥0.10 ∧ X_O2<X_def → "개방 금지 / BD 잠재".
X-1, G-1, E-2를 P0-4의 새 FGI와 BD 정의로 다시 쓴다.
완료 기준: run2 3300 s에서 화점 셀이 "전진"에 맞지 않고 "개방 금지"에 맞는다.
P1 — CFAST 입력 생성 오류
P1-1. 셀 분할 때 t² 성장이 면적 비율만큼 느려짐
파일: pyrocast_cfbt/rule_cells.py:49-54 (q=[v*fraction], 시간축은 그대로)
증거: 입력은 α=0.047 kW/s²인데 R6 TABL은 16.711 s에 4.375 kW다. 즉 α=0.0157 = 0.047/3이다. 최대 도달은 386 s가 아니라 668 s에 일어난다. 결과가 셀 개수에 따라 달라진다.
수정: 곡선을 곱셈으로 축소하지 않는다. 다음 둘 중 하나로 한다.
원래 growth_kW_s2를 유지한 채 fire_curve({…, energy_MJ:E·f, peak_kW:P_cell, fuel_area_m2:A·f})로 다시 만든다.
또는 발화 셀에는 축소 전 곡선을 두고, 형제 셀 예비분만 줄인다.
P1-2. "최대 열방출률 7 MW"가 셀마다 적용돼 실 전체로는 21 MW가 됨
파일: tools/fixed_calculation.py:120-123 (peak/area_fraction), rule_cells.py:57-61, room_rule_r7.py:47,62-63
증거: 요청값은 7000이다. 그런데 rule_manifest.json의 unpartitioned_peak_kW는 21000이고, R6_C0과 R6_C2 TABL이 각각 7000 kW다.
수정: fire_peak_kW는 물리 실 최대값으로 정의한다. 셀 최대값은 peak·f, 형제 셀은 peak·share로 둔다. set_fire_input에서 Σ(셀 최대값) ≤ 요청값을 검증한다. UI의 fire_details(fixed_calculation.py:148-157)에도 실 기준 값을 표시한다.
P1-3. 개구부 위치를 CAD 좌표가 아닌 가짜 중앙 오프셋으로 셀에 배정함
파일: cad.py:346 (offset=(w_a-width)/2, 모든 벤트가 FRONT 면), rule_cells.py:82, 85-107
증거:
D0는 CAD상 R0_C1 끝에 있는데 R0_C0/C1로 나뉜다.
EV1/EV2는 R0_C0에만 있어야 하는데 반반으로 나뉜다.
D5는 뒷벽에 있는데 FRONT로 출력된다.
FLOOR/CEILING 벤트는 v['center_m']을 읽는다. 그런데 실제 값은 v['cad_geometry']['center_m']에 있어서 항상 기본값인 중앙 셀이 선택된다.
수정:
a쪽과 b쪽 모두 native_point(original, v['cad_geometry']['center_m'])로 셀을 고른다.
면은 CAD 법선 방향으로 정하고, offset = clamp(p − cell_origin − width/2, 0, L − width)로 둔다.
CAD 개구부 자체가 셀 경계에 걸칠 때만 분할한다.
면마다 Σ(벤트 폭) ≤ 면 길이를 검증한다.
P1-4. FO와 환기 상한을 셀이 아닌 물리 실 기준으로 계산
파일: conditions.py:121-139 (fo_required_hrr: 가상 경계면을 벽 면적으로 셈), fixed_native_playback.py:81-87, room_rule.py:78-92 (ventilation_cap)
증거:
화점 셀의 Thomas Q_FO는 약 5.9 MW, 물리 실 R6 전체로는 약 10.5 MW다. 셀 기준이 약 44 % 낮다.
ventilation_cap이 가상 셀 경계 VC_*와 승강로 문(EV0)으로 113~172 MW 상한을 만든다. 외기와 무관한 개구부들이다.
수정:
parent_room 단위로 Q를 합산한다(외부에서 들어오는 문 제트만 더함).
A_T는 원래 실의 상자 크기, 벤트는 실 둘레에 있는 것만 쓴다. Tu는 체적 가중 평균으로 구한다.
환기 상한에서 virtual_cell_boundary를 제외한다. 밀폐 영역이면 가용 산소 기반으로 상한을 잡거나 unbounded_sealed로 표시한다.
P1-5. 착화 부모 그래프가 같은 실 셀 대신 연료 없는 승강로를 경유함
파일: rule_graph_r7.py:23-25, 36-43, room_rule_r7.py:94-98
증거: CAD_B3_R0_C0의 부모가 CAD_B3_R10(승강로)이다. 트리거는 PC_CAD_B3_R10 SETPOINT=600이다. 즉 연료 없는 승강로 판이 600 ℃가 돼야 같은 주차실의 나머지 절반이 착화된다.
수정: 같은 parent_room의 형제 셀(cell_flame 간선)을 부모로 우선 선택한다. 통로가 아닌 경로가 있으면 통로(passing)를 부모로 삼지 않는다.
P1-6. 중복 개구부 때문에 면적이 두 배가 됨
파일: cad.py:243-258
증거: B3의 EV1과 EV2는 다각형과 접한 실(sides)이 완전히 같은데 둘 다 출력된다.
수정: (frozenset(sides), 반올림한 다각형 해시)를 키로 중복을 제거하고 경고를 남긴다. model.normalize에서는 같은 실 쌍과 같은 중심(0.05 m 이내)을 가진 벤트를 거부한다.
P1-7. 천장 높이 대체값으로 구조 층고 5.9 m를 사용함
파일: ceiling.py:39-44, cad.py:174, 189-190
증거: B3는 ceil_h가 없어서 1.2×0.88 m 방을 포함한 모든 구획이 HEIGHT=5.9 m가 됐다.
수정: ceil_h가 없으면 층 용도별 기본값을 쓴다(주차 2.7 m, 판매 3.0 m 등, 설정 파일로). 코어가 아닌 실에서 height/sqrt(area) > 3이면 경고 또는 거부한다.
P1-8. 연소 화학 상수가 모든 용도에 목재형 하나로 고정됨
파일: deck.py:180 (RADIATIVE_FRACTION=0.35 SOOT_YIELD=0.02), cad.py:369 (hoc=18100), model.py:120
수정: fire_load_table.json에 용도별 hoc_kJ_kg, soot_yield, co_yield, chi_r, 화학식을 추가한다. 차량 예시는 약 25-30 MJ/kg, 그을음 0.05-0.1이다. 이 값을 fuel_groups를 거쳐 deck으로 전달한다.
P1-9. 2차 실 화재가 크기와 무관하게 60 s 만에 최대치에 도달함
파일: room_rule.py:95-113 (supply_curve, 선형 상승 60 s)
증거: R0_C0이 0에서 6.1 MW까지 60 s 만에 오른다. 초고속 t² 성장(ultrafast)보다도 빠르다.
수정: 용도 등급 α를 쓰는 t² 성장으로 바꾼다. 또는 peak/ramp_s² ≤ α_max로 제한한다.
P1-10. 기타 (Medium/Low)
deck.py:123-124: 지상층 내부실에도 외기 누기를 기본 적용한다. 외벽 길이 × 높이로 LEAK_AREA(절대 면적)를 계산하는 방식으로 바꾼다.
cad.py:139-144: 지하층 표고가 지반 기준이 아니다. B3는 z=0인데 1F가 15.7 m다. 지반 높이를 0으로 다시 기준을 잡는다. 외기 정수압 계산에 영향을 준다(Plausible).
rule_cells.py:43: 화원이 가상 경계에서 0.01 m 거리에 놓여 CFAST가 모서리 화원으로 처리할 수 있다(Plausible). 경계에서 √A/2 + 0.05 m 이상 떨어뜨린다. 작은 실(< 20 m²)은 분할하지 않는다.
cad.py:338: 원점이 i*100이라 폭 100 m가 넘는 실은 겹친다. 누적 원점으로 바꾼다.
fixed_native_playback.py:61-62: Yf 분모가 화학종 합이다. 이상기체 질량과 2 % 이상 차이 나면 플래그를 단다.
fixed_native_playback.py:69-76: 초기 화재 시작이 HRR>0인 첫 샘플(5 s)로 잡힌다. initial_time_s를 쓴다.
fixed_calculation.py:267: stall_timeout_s=0이다. 90 s 정도로 두고, 실패 메시지에 마지막 PRS와 시간 간격을 남긴다.
개구부가 0개인 고립실(R2, R7, R8, R9)도 셀 분할, 연료, 센서를 받는다. isolated로 표시하고 제외한다.
P2 — 간이(Lite) 엔진 물리
실사용 경로는 adapter.LiteModel(L1)이다. 독립 core.Model은 CLI와 진단 도구에서만 쓴다.

P2-1. 플룸 유입량 과대 (CFAST와 다름)
파일: pyrocast_lite/core.py:366-371
문제: me = max(entr(z_int), min(inl, entr(Hf))) 때문에 경계면이 낮아도 천장 높이 기준으로 신선 공기를 유입한다. 게다가 상층 재순환분 meu가 산소 공급원으로 계산된다. 결과적으로 산소 부족 상태가 억제된다. 이미 알려진 편향(KNOWN_BIAS, 상층이 CFAST보다 14-20 % 낮음)과 일치한다.
수정:
me = entr(clip(hl−fire_height, 0, Hf))로 하고, inl 항을 제거한다.
산소 예산에서 meu를 뺀다.
CFAST 비교 사례를 다시 돌려 KNOWN_BIAS를 다시 구한다.
P2-2. Heskestad 원거리장에서 가상원점 z0가 빠짐
파일: core.py:359-363
증거: z=L에서 1 MW일 때 −12.6 %, 3 MW일 때 −20.7 % 불연속이 생긴다. 해석기(BDF)의 우변이 불연속이 된다.
수정:
0.071·Qc^{1/3}(z−z0)^{5/3} + 0.0018·Qc, z0 = 0.083Q^0.4 − 1.02D로 계산한다.
하한 가드는 max(L,0.1) 하나로 통일한다.
P2-3. 유입과 화염이 공급 HRR 기준이고, 직경 계산이 500 kW/m²로 고정됨
파일: core.py:356-363
수정: 직전 단계의 실제 연소량 Q를 쓴다. 직경은 그룹의 fuel_area_m2와 HRRPUA(단위면적당 열방출률)로 계산한다.
P2-4. 단위 오류
파일: core.py:367 me = min(me, 0.5*ml). 질량(kg)으로 유량(kg/s)을 제한하고 있다.
수정: ml/tau_mix(PRM의 명시적 시간척도)로 바꾸거나 제거한다.
P2-5. 벽 복사 모델
파일: pyrocast_lite/shared_inputs.py:100-108
문제: 하층의 맑은 공기도 흑체(ε=1)로 복사를 교환한다. 상층도 두께와 관계없이 ε=1이다.
수정: 하층은 대류만 남긴다. 상층은 ε_g = 1−exp(−κL)을 적용한다(gas_radiation_enabled 사용).
P2-6. 밀폐 구획에서 에너지가 보존되지 않음 (Plausible)
파일: core.py:278-279, 473-474, adapter.py:121-134
수정: 화원이 있는 밀폐 구성요소에는 P0-1과 같은 최소 누기 경로(외기 노드로 가는 작은 틈새 유량)를 자동으로 추가한다. 엔진 간 경계 조건을 맞추기 위해서다.
P2-7. 몬테카를로 판정과 집계
파일: montecarlo.py:113, screening.py:135
문제 1: FO 판정에 점수의 all_met(Thomas 비와 하층 산소 포함)을 쓴다. 원래 판정 기준인 불리언이 아니다.
문제 2: montecarlo.py:170-178: 실패한 샘플을 분모에서 빼서 발생률이 과소 추정될 수 있다. 신뢰구간도 없다. 기본 20개 샘플이면 표준오차가 최대 ±0.12다.
문제 3: montecarlo.py:49/66: 추정 방화문 확률이 0.35로 하드코딩돼 있다.
문제 4: score_median이 연기 도달 전의 0까지 포함한 중앙값이라 의미가 없다.
수정: P0-4의 occurred로 집계한다. Wilson 95 % 신뢰구간을 내고, 실패한 샘플은 상한과 하한 양쪽으로 반영한다. 확률은 설정값을 쓴다. score_median은 제거한다.
P2-8. 발화실 성장률 하드코딩
파일: screening_v8.py:31, screening_v8_approved.py:94,118
문제: 모든 용도에 α=0.047을 쓴다. 창고는 4배 과소, 숙박과 사무실은 4배 과대다.
수정: 1000/t_alpha²(fire_load_table.json)를 쓴다.
P2-9. 기본 외기 0 ℃로 숨은 연돌 효과 (레거시 경로)
파일: core.py:28 (T_out=273.15), core.py:171-180 (지하층 승강로 누기가 외기로 연결됨)
수정: 기본값을 T_out=T_in으로 하고, 겨울 조건은 별도 시나리오로 둔다. 지하층 누기는 "건물 나머지" 노드로 연결한다.
P2-10. 기타 레거시 경로
복사분 χr·Q가 그냥 사라진다.
하층 벽 손실에 근거 없는 *0.3이 곱해진다.
hk에 1/π가 빠졌다.
감쇠가 지수 꼬리라 끝나지 않는다. EN 1991-1-2 E.4는 70 % 소진 후 선형 감쇠다.
열분해 기체가 CP*T_pyro 엔탈피를 공짜로 들여온다.
P3 — 표시, 브리핑, 인프라
P3-1. 지수 표시 문구와 색상
파일: app/web/panels/results.js:20-26, 91-96, panels/display.js, panels/legacy_lite_panel.js:36, adapters/read.js:62-75
수정:
"위험 지수"를 "조건 근접도(선별, %)" 로 바꾼다.
gate가 false면 "해당 없음"으로 표시한다.
주의 수준 미만이면 회색으로 처리하고, 현상 색은 기준 미만에서 쓰지 않는다.
병목 요소를 물리 단위로 함께 보여준다(예: "상층 114 ℃ / 기준 600 ℃").
"최악 시각"을 "최고 근접 시각"으로 바꾸고 해당 셀 ID를 함께 표시한다.
P3-2. 셀, 현상, 시간, 샘플 전체에 걸친 최대값 집계
파일: results.js:20-26, route/risk.js:11-29, layers/risk.js:66-90
수정: 값마다 "셀 최대(셀 ID)" 라벨을 붙인다. 물리 실 값은 P1-4 기준으로 계산한다.
P3-3. 롤오버 UI가 표시 임계값으로 상태를 다시 계산함
파일: app/web/adapters/fgi_rollover.js:2-11, read.js:111-112, layers/risk.js:78
문제: 표시 리본 임계값을 낮추면 "롤오버 조건 충족"이 나타난다.
수정: 저장된 rollover.active를 그대로 쓰고, 표시 임계값은 스타일에만 적용한다.
P3-4. 브리핑 문구
파일: tools/d5_briefing.py:9, 122-142, 172, 192, tools/lite_ai_briefing.py:16, 29
수정:
"FO 100 미도달 · 최고 FO 18.95"를 "FO 기준 미도달 (상층 최고 114 ℃/600 ℃, 바닥 복사 Y/20 kW/m²)"로 바꾼다.
gate가 false인 FGI/BD 줄은 생략한다.
전조 징후(SIGNS) 문구는 근접도가 주의 수준 이상일 때만 출력한다.
무효 결과(P0-2)에는 브리핑 대신 무효 사유를 출력한다.
P3-5. 보안: 메인 POST의 Host 허용목록 누락
파일: PyroCast/tools/serve_cfbt_building.py:417
문제: Origin만 Host와 비교하고 Host 값 자체는 검사하지 않는다. 그래서 DNS 리바인딩으로 계산 실행 엔드포인트를 호출할 수 있다.
storage_cleanup.py:160-162와 lite_ai_http.py:12에는 허용목록 검사가 있다.
수정: Host를 127.0.0.1:<port>와 localhost:<port>로 제한하는 같은 검사를 공통 함수로 빼서 모든 POST에 적용한다.
P3-6. 저장소 위생
.github/workflows가 없다. Windows 러너에서 unittest를 돌리는 CI를 추가한다.
빠진 고정 데이터(room_rule_r8_20261025/source-scenario.json)를 저장소에 넣거나, 해당 테스트를 skip 처리한다.
경로 길이: 최장 288자다. 깊은 경로에서 git clone하면 Windows에서 "Filename too long"으로 실패한다. PyroCast/specs/의 긴 한글 파일명을 줄인다. README에는 git config core.longpaths true를 안내한다.
버전별 중복 모듈 정리: room_rule.py, room_rule_r6.py, room_rule_r7.py, room_rule_r8.py, screening.py, screening_v7.py, screening_v8.py. 쓰지 않는 버전은 legacy/로 옮기고 import 경로를 명시한다.
라이선스가 "All rights reserved"다. 공개 저장소에 맞게 라이선스를 정한다. CFAST(공공 도메인)와 three.js(MIT) 고지도 확인한다.
검증 시나리오 (모두 끝난 뒤)
B3 밀폐 입력(외기 경로 없음): 최소 누기가 자동 적용되고 화면에 표시된다. 압력은 1000 Pa 이하이고 산소 저하는 유지된다. BD와 FGI 근접도가 온도 요소 없이 계산돼 높게 나온다. 기존 run2 수치로 보면 BD는 약 300 %, FGI는 약 130 % 수준이다.
B3에 램프와 기계배기 추가: 압력이 ±200 Pa 이내다. 화점 셀의 FGI는 null이다. 인접 셀 FGI는 Yf/LFL과 O2 기준으로만 계산된다.
상온 무연기 실: 모든 지수가 0 또는 null이다.
셀 분할 수와 성장률: 같은 실을 1, 2, 3개 셀로 나눠도 실 전체 열방출률 곡선이 ±5 % 이내로 같다.
간이 대 CFAST 비교: 기존 비교 사례(호텔 등)로 상층 온도와 O2 편향을 다시 구하고 README/KNOWN_ISSUES에 반영한다.
