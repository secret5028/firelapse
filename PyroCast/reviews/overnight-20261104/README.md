# 야간 작업 인계 · 2026-11-04

사용자 요청: 실제 Claude와 검토를 주고받으며 앱 버그 수정, 건물별 각 층 대표 화점 1개 계산. 자동 후속 작업 `pyrocast`는 11월 5일 09:00 KST까지 30분 간격. 임계값/물리 모델 변경·기존 결과 삭제·push 금지.

## 현재 실행

- 기본 간략 엔진. 엔진 선택 질문에는 아직 답변 없음. 최신 사용자 답변이 오면 그것을 우선한다.
- `simulation/results/overnight-20261104/progress.json`이 유일한 작업 장부. `plan.json`의 입력/엔진 SHA 고정. `prepare` 재실행 금지.
- 직렬 배치 unified exec session **42392**, worker PID **18000** (재개 시 worker.json의 현재 PID 재확인). 서버 밖 CLI이므로 웹 서버 재시작과 독립적이다.
- `run_overnight_floors.py run`은 잠금으로 중복 실행 차단. 작업자가 살아 있으면 새로 실행하지 않는다. 작업자 사망 시 child도 남아 있는지 먼저 확인한다. 이미 시도한 사례는 자동 재시도하지 않는다.
- 강화 9층·호텔 14층·견본주택 2층 = 25층. 준비 성공 22층, blocked 3층. 방은 기존 후보 점수 1위, 각 3600 s, 출력 10 s, 내부 예산 1200 s/외부 1260 s.
- 완료: 강화 3F R1 46.641 s, 호텔 5F R16 58.062 s. 이 값은 전체 경과시간이며 적분 시간은 각 summary.json에 별도. 강화 3F R1은 S09(R2) 회귀 앵커가 아니다.
- 나머지는 progress.json을 확인할 것. 스캔 2건은 계속 계산 금지.
- 완도는 일반 CAD 경로에서 제외했다. **다음 후속 작업에서 전용 P1 입력을 새 날짜 폴더에 복사해 1회 실행할 준비를 검토**한다. 기존 P1–P5 파일 덮어쓰기 금지. 일반 배치와 동시 계산 금지. 사용자가 전 건물을 요청했으므로 완도는 미실행 상태를 숨기지 말 것. 기존 run_wando_c11_p1.py는 OUT 하드코딩이므로 그대로 실행 금지; 모듈 OUT을 새 폴더로 지정하고 덱/모델 사본만 사용. 엔진/입력은 그대로. 새 native 실행을 한다면 lite 결과와 같은 엔진인 것처럼 비교하지 않는다.

## 준비가 막힌 층

| 건물 | 층 | 오류 |
|---|---|---|
| 강화 | B1 | Opening wider than usable equivalent room: CAD_B1_R12 |
| 강화 | PH | Invalid room box |
| 호텔 | B1 | Opening wider than usable equivalent room: CAD_B1_R9 |

폭 잘라내기·임의 면적/높이 수정으로 통과시키지 않는다. 원인 조사와 근거 있는 변환 오류 수정만 가능. 미실행은 0이 아니다. 각 층 고립실도 request.json에 보존했다.

## 수정·검증

- `82fc42b`: 직렬 배치/동결 입력/잠금/타임아웃 도구. 엔진·조건표 SHA 불변.
- `3a0a7ff`: 모델별 저장 목록에서 잘린 status, 누락 request, 복사 중인 결과 1건이 정상 결과 목록 전체를 실패시키는 문제 격리. 완료 결과만 카탈로그에 포함하던 기존 정책 유지. 진행 상태는 별도 MC status 경로. 제외 사유는 경고 로그와 catalog.warnings. UTF-8 BOM 지원.
- `6cb32d2`: 새 야간 wrapper에서 확정 닫힘과 누설 fraction을 분리. closed+0.001 회귀 시험. **실제 완료된 강화 3F의 수정 대상 boolean은 0건**. 그 입력의 닫힌 개구부는 이 문제에 영향받지 않았다. 별도 저장 상태 메타데이터를 playback에 보강했고, 추가 필드를 제외하면 보강 전/후 전체 객체 동일. input SHA와 계산 배열 그대로, 원 playback 사본과 정정 장부 보존. 기존 과거 결과는 수정하지 않았다.
- catalog 합성시험 1건(8종 입력) PASS; nightly opening 시험 4건 PASS.
- JS 집중 검사 6파일 중 5 PASS: results, explore, timeline_risk, display_gains, c8_defaults. building_panel.unit은 과거 screening fixture와 현재 savedAttention 증거 불일치(null 대 기대2), 테스트 부채로 남김. 기대값을 강제로 수정하지 않음.
- 광범위 app glob 33파일: 17 PASS/16 FAIL. Playwright 경로·Three 인수 누락 등 환경 오류가 섞여 있어 앱 버그 16건이라는 의미가 아님. app-tests-before.log 참조. 옛 캡처를 덮어쓰는 integration test를 무작정 재실행하지 말 것.
- simulation/tests 252: 241 PASS, 1 FAIL, 10 ERROR. historical fixture 누락 3, 삭제된 독립 rollover 기대 1, 제거된 실 산소 모드 기대 5, 삭제된 visualization import 1, 산소 모드 예외 문구 기대 1. python-tests-before.log 참조. 엔진 복원/물리 조정으로 테스트를 맞추지 않는다.

## 운영 반영

호텔/견본 MC idle 확인 후 모델 라이브러리 서버만 재시작. 현재 서버 unified exec **40997**, 명령 `python -B -X utf8 tools/serve_model_library.py --port 8841` (8842/8843 포함). 배치 PID 18000 생존 확인. API hotel cases=3 warnings=0, showroom cases=1 warnings=0.

IAB 검증 tab 65(`nightHotel`)에서 호텔 새 5F 결과 재생/층 선택/결과 탭 로드 성공, console error 0. 현재 선택과 계산 범위 별도 표시, 계산하지 않은 경로 실은 미평가/—. 새 결과 UI 최고 FO134·FGI78·BD75. **이것은 입력 기본 상태로 새로 계산한 결과이며, 옛 열린 조건의 FGI/BD=0을 엔진 수정해서 높인 것이 아니다.** 물리식 불변. B1 선택은 후보 계산 불가 오류가 표시되고 실행 비활성.

## 실제 Claude 검수

Claude 데스크톱 대화 `73181e32-dbf5-8712-946f-bf957b48152e`, 제목 PyroCast 야간 자동중계. 검수만 요청, 파일 조작 금지. 2회 답변을 claude-review-1/2.txt로 저장.

수용: 입력/엔진 추적, 직렬 타임아웃, 고립실 기록, CAD 폭 임의 자르기 금지, null 보존, 손상 항목 격리 및 경고, BOM, 표시 정정 장부.
정정/미채택: 첫 강화 R1은 S09 앵커 아님; 이번 카탈로그는 건물 범위이고 진행 상태는 별도 경로; 저장은 기존 원자적 교체 사용; 표시 boolean 확인을 위해 같은 물리 계산을 재실행하지 않음(배열 동일 비교로 확인). Claude의 추측을 검증 없이 실제 원인으로 쓰지 않는다.

## 다음 후속 작업

1. progress/worker 확인, 살아 있는 배치 중복 금지. 새로운 실패와 각 층 시간·연소실·3지수 최고/시각 표 작성. 09:00 이후 새 계산 시작 금지.
2. 테스트 환경 문제와 실제 버그를 분리. 다른 건물 결과 주입 거절, 저장→재생 일치, 탭/층 전환·토글·미평가 —·화원/급기 상태 점검. 계산 버튼을 무작정 눌러 추가 작업 만들지 않음.
3. Claude에 실제 diff/관측값을 보내 재검토. 필요 없는 재설계·물리 변경 금지. 버그별 1커밋, 운영/별도 git 체크아웃 동기화, push 없음.
4. native 완도 P1 추가 실행은 위 지침대로 직렬·새 폴더만. 호텔 native 대조는 엔진 선택 답변과 현재 요청 범위를 확인한 후 실행. lite FGI/BD 물리 타당성은 아직 검증 완료라고 쓰지 말 것.
5. 최종 보고서에 성공/실패/미실행·engine/input/state·제외 사유 구분. 완료되거나 09:00에 automation을 중지. 상태 불변 시 알림 반복 금지.

## 19시 전후 후속 확인

- 강화 1F 983.703 s, 2F 337.004 s 완료. 4F 계산으로 자동 진행. 실제 최신 시각/값은 progress 및 `tools/report_overnight_floors.py`로 갱신하는 floor-status.md/json 참조.
- 층별 보고는 부분 평가된 조건의 **알려진 표본 최고값**도 포함한다. unknown 표본은 제외하되 partial_conditions에 셀/현상/coverage 기록. 호텔 5F BD 최고 74.9223은 부분 평가 배열에 있으므로 status=evaluated인 실만 골라 54로 과소집계하면 안 된다.
- blocked-geometry.json은 입력 변경 없이 예외 프레임에서 추출한 치수. 강화 B1 작은 실 R12(1.1636 m²)에 폭 4.12 m W2, 호텔 B1 R9(.9512 m²)에 승강기 문 6개(최대 1.719 m)가 연결됐다. **잘못된 소속이라는 Claude 의견은 아직 추정**. 도면 경계/개구부 형상을 검증하기 전 이동·삭제 금지.
- 강화 PH R3은 .5599×8.8579 m, 면적 4.9592 m². 기존 등가화가 depth만 최소 .61 m로 조정하고 width의 대칭 경우를 처리하지 않는 현상 확인. 그러나 원본에도 이름 없음·개구부 없음·unresolved_isolated. 이 공간을 사람이 쓰는 실/이송 공간으로 단정하거나 임의 제외하지 않는다. 면적 보존으로 박스만 바꾸더라도 열손실 둘레는 변하므로, 원본 CAD의 공간 정체 확인 전에는 blocked 유지. 현재 배치의 engine SHA도 유지.
- Claude 3차 의견은 claude-review-3.txt. 전처리 분류/치수 진단만, 이번 후속에서 엔진/건물 입력 수정 없음. Claude가 언급한 일반 종횡비 한계·손실 무시 가능성은 검증된 근거로 채택하지 않음.
