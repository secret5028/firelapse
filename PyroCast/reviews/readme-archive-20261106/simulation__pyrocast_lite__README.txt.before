2026-10-25 §3.0 stage1: oxygen_inventory_mode=True adds one oxygen mass per solver cell.
Experimental only: 3F 139.074s / 9 burning rooms, L3 failed due to additional R17.
Not adopted for operational 3D or MC. Default previous two-layer oxygen mode remains available.
Report: specs/간략산소-3.0-1단계-시험결과-20261025.txt. Stop after stage1 as requested.

L1 experimental — fire_zone.py 기반 간략 엔진

원본: C:\Users\예방\Documents\Codex\2026-09-07\2\CAD3D\fire_zone.py
원본 SHA: e55d7de953c0ae8322e92b93952059ea6b7cb4930b84032282ae0251e0b34f40
원본/정밀 r8/순정 CFAST는 변경하지 않음.

이전 상태(1.4절 기록, 아래 §1.5로 대체): 표준 상층셀300℃/복사OFF 구성을 탐색용으로 채택.
재정의 L3는 통과. 출력 진단 기준은 질량0.5%/에너지0.1%로 사용자 지정 변경.
기준 표준 잔차0.107620%/0.001646%는 이 출력진단 기준을 통과하며 수락스텝 장부는 만들지 않는다.
최신 MC20 결과/진행: simulation/results/lite_l1d_20261025/{status.json,progress.json,aggregate.json}
보고: specs/간략엔진-L1d-채택·MC20표본-시험결과-20261025.txt
MC 표본별 수치실패와 출력진단초과는 분리하고 실패를 안전/0으로 집계하지 않는다.
운영3D 교체는 하지 않는다. 복사 실험항은 OFF로 보관하며 열모델은 L1c와 동일.
3F3600s: 복사전표준118.152s/8실, 복사후표준61.665s/1실, 복사후공격187.332s/10실(60s지속8실).
이전 결과: simulation/results/lite_l1_20261025/ (덮어쓰지 않음)

core.py는 원본의 BDF·층 유동·벽 손실·기존 조건식을 유지하면서 화원 기여 루프를 여러 실로 확장했다.
pyro_feedback=True는 원본 동작 확인용. L1 adapter는 False만 허용하며 r8 공급곡선을 그대로 방출한다.
원본의 열분해 피드백은 '다른 실 착화' 기능이 아니다. OFF는 미연 공급량을 바꾼다.

adapter.py는 r8 prepare의 셀/부모/지연/곡선을 사용한다. manifest에 원래 판 배치 정보가 남지만
판 상태를 만들거나 적분하지 않는다. PC/FC 모두 부모 상층 온도를 쓴다.
실간 temperature_C/셀간 cell_temperature_C를 r8 설정에서 그대로 읽는다(표준600/300℃).
곡선에 지연이 이미 들어 있으므로 조건 시각을 기준으로 평가한다. 지연을 두 번 더하지 않는다.

runner.py는 solve_ivp(BDF, sparse Jacobian, terminal events)를 사용한다.
확정 이벤트 상태와 입력 곡선 절점에서 재시작하며 0초 전체 재계산은 하지 않는다.
BDF 내부 간격은 자동, 결과는 10초. 실제 양수 HRR 지속은 출력표본 기준의 하한이다.

원본에서 없는 기능: rollover 판정, soot/광학농도 수송, 미연 가스 재연소, CO 재연소.
이 항목들은 새로 꾸며내지 않고 미평가/한계로 표시한다. 기존 FO/BD/FGI/피난 판정은 보존했다.
실제 HRR, 공급 HRR, 미연 연료는 분리한다. 질량/에너지 0.1% 관문은 아직 검증하지 않았다.

shared_inputs.py는 생성된 순정 덱에서 MATL/COMP/CHEM/INIT를 읽는다.
실별 벽·천장·바닥 물성 및 두께, 방사율, 연소열/복사분율, 실내외 온도를 공유한다.
벽 물성만 맞춘 B3는737.5℃로 native1035℃보다28.7% 낮아, 승인된 유한두께 1노드 모델로 전환했다.
각 실의 천장/벽/바닥에 열용량 노드1개씩(총3개)이며 BDF 상태에 포함한다. 앞뒤 반두께 열저항과
뒷면 외기 열교환을 쓴다. 직접 화원 복사열은 표면 면적 비례로 벽에 전달한다(형상계수 근사).
기존 코어 호환모드에서는 원본 kpc 식을 유지한다. L1은 유한벽 모델만 적용한다.
600℃ 기준을 낮춰 B2/B3를 통과시키거나 출력에 전이를 추가해서는 안 된다.
실험 radiation.py: kappa0.50/m은 CFAST의 CONSTANT 모드 defabsup 값이며 정상 성분별 absorb()와 다르다.
ON이면 기존 가스-벽 복사항을 제거하고 상층 grey exchange로 대체해 중복을 막는다.
화원 복사는 상층 흡수분+벽 전달분으로 보존 분할한다. 벽↔가스 q는 반대부호, 하층 가스 흡수는 없다.
이 옵션은 비교 시험에서 되돌림 조건에 걸려 OFF이며, 임의로 기본 ON으로 바꾸지 말 것.
창은 초기 비율 고정. LEAK_AREA_RATIO는 CFAST 소스대로 실-외기 별도 벽/바닥 누설로 변환한다.
문/창별 임의 누설은0으로 하여 중복을 막는다. L1은 Cd0.70을 사용한다.
LOL은 덱 질량분율 기준부터 +0.01까지 순정 tanhsmooth 식을 사용(기본0.15~0.16).
원본 호환 core 기본값은 legacy Cd0.68/vol% 선형을 유지하고 L1 adapter에서 명시 선택한다.
감쇠식 일치가 전체 플룸·산소 수송 모델 일치를 뜻하지는 않는다.
r8의 미래 창 개방 기준 공급 상한은
그대로 공유하므로 창 파괴 OFF와 공급 상한이 가정상 다를 수 있음을 결과에 명시한다.
수직 존은 기본 OFF이며 정규화 어댑터는 FLOOR vent를 조용히 WALL로 바꾸지 않고 거부한다.
기존 원본 Model의 수직 존 기능은 보존되어 있지만 다층 r8 어댑터는 이번 관문 뒤 범위다.

실행 환경: Python 3.12, 프로젝트 simulation/deps를 PYTHONPATH에 포함.
requirements.txt는 간략 엔진 전용. OpenCV는 L0 기존 CAD 입력 재현 시에만 필요하다.
tools/run_lite_l1.py는 첫 구현 기록용. 최신은 tools/run_lite_l1d.py(MC20/4프로세스).
montecarlo.py: seed기록, 종류별Bernoulli 또는fixed_count, 사용자고정개구부우선,18무작위+2필수.
조건비율은 완료한무작위표본만을분모로 하며 필수극단사례/실패사례/출력진단합격집계를 구분한다.
현상최악은조건충족원래실수최대→최초충족빠름순. 경계는 원래실최고온도600±30℃; 셀경계도별도저장.
롤오버는 미평가이며 발생률0으로 만들지 않는다. 닫힘의개방위험구간은 기존Yf_backdraft/LOC 및input gas.hot_C로 후처리한다.
tools/report_lite_l1d.py, plot_lite_l1d.py는 저장 결과만 읽으며 새 적분을 실행하지 않는다.
이미 시작한 사례는 재실행을 거부한다. 저장 결과를 삭제해서 자동 재시도하지 않는다.
20표본 파일럿 이후 표본 확대나 수치모델 수정은 결과를 검토한 뒤 결정한다. 자동추가시행하지 않는다.

2026-10-25 §1.5 (L1e) — 위 L1d의 평가·실행 지침을 다음으로 갱신
- tools/run_lite_l1e.py: reaggregate → doors → isolate → validate → mc 단계.
  기존 실패5건은 수치 수정 전 입력으로 격리. 새 MC는 같은 seed의20표본/4병렬,
  BDF600초 예산, singular에만 Radau1회. 시간초과는 재시도하지 않는다.
- smooth_state_bounds/upper_combustion_enabled는 명시 옵션. 상층 추가 반응은
  기존 잔여 연료·산소 재고/τ20초, 공유 LOL tanh와 gas_ignition_C를 쓴다.
  주 플룸의 상층 산소 사용을 예약하고 같은 ξ로 연료·산소·열을 처리한다.
  순정 CFAST 상층·문 분출 반응의 동일 구현이 아닌 혼합 재고 근사다.
- 공통 conditions.py가 표시용 T/F/O 점수, min 정도, 병목·우세 요인을 계산한다.
  FO Thomas 필요발열/하층산소, FGI hot_C/기존 온도의존 LFL 근사를 적용한다.
  3요인 AND와 기존 bool 맥락은 별도로 보존. 점수는 물리 적분·전이 규칙에 영향 없음.
  상층 반응 OFF 결과는 FGI/백드래프트/롤오버 미평가. ON이면 조건과 실제 반응량 별도.
  정보 부족은 unknown. 혼합 Hc에 대한 임의 유효 LFL은 만들지 않는다.
- 출력 잔차 합격은 에너지0.1%만. 질량은 보고용, 수락 스텝 보존 인증이 아니다.
- door_classification.py/door_class_rules.json: 도면·실 용도로 자동 분류.
  3D 목록과 기호로 정정하면 simulation/config/lite-door-overrides.json에 저장.
  규칙상 confirmed는 실제 방화 성능 확인이 아니다. 원본 OCR 명칭 오염의 영향을 받는다.
  r8 규칙은 열린 방화문도 고체 전이 간선에서 제외한다는 한계를 유지한다.
  AUDIT_PASS/가상 셀 경계는 항상 열린다. 같은 seed라도 분류 변경으로 실제 조합이 달라진다.
- refresh_lite_l1e_scores.py와 report_lite_l1e.py는 저장 상태만 후처리한다.
  결과는 simulation/results/lite_l1e_20261025. 3D 기존 화재 재생을 새 MC로 교체하지 않는다.
