# C-2 사용자 화점 지정 — 2026-11-02

C-0(7799ae3)·C-1(3a7b170) 완료 상태에서 C-2만 추가했다. C-3 이후 미착수. 1항목 1커밋, push 없음.

## 구현

- 3D 실 클릭 → HUD “이 실을 화점으로” → 탐색 ③ 원래 방 선택. R2_C0 선택은 CAD_3F_R2로 연결한다.
- ③ “선택 실 2상태 실행”을 추가했다. 기존 POST /cfbt/lite/screening에 rooms:[원래 방 ID] 1개를 전달한다. 기존 상위 N 실행도 유지한다.
- 수동 최초 화점만 자동 후보 제외 기준과 분리한다. R11은 화장실 40 MJ/㎡로 자동 후보에서는 계속 제외되고, 수동 최초 화원으로만 허용한다. R14/R28 및 공급/연료 없는 공간은 허용하지 않는다. 기존 물리 엔진과 전이 규칙에는 변경이 없다.
- 기존 CLI를 직렬 2상태 실행하며 결과 playback, root/attempt index-summary.json을 저장한다. 완료 후 목록만 갱신하고 현재 3D 장면은 바꾸지 않는다.
- HUD의 기존 pointer-events:none 상속을 버튼에서만 해제했고, 탐색 자료가 늦게 도착하면 버튼의 사용 가능 여부도 갱신한다.

## 실제 운영 UI 검증

POST는 운영 UI의 “선택 실 2상태 실행” 버튼으로 1회 요청했다. 원래 방 CAD_3F_R11, workers=1, duration=3600 s, 각 사례 기존 적분 예산 1200 s. 추가 MC/CFAST 실행 없음.

| 상태 | 적분 | 계산·후처리 기록 | 종료 시각 | 연소 실 | 주의 ≥70 실 | 최초 FO |
|---|---:|---:|---:|---:|---:|---|
| 확정 방화문 제외 열림 | 22.55 s | 30.68 s | 3600 s | 1 | 0 | 없음 |
| 전부 닫힘 | 23.14 s | 31.17 s | 3600 s | 1 | 1 | 없음 |

전체 배치 68.43 s(직렬, 파일 저장 포함). 두 상태 모두 최초 화원 상한 1385.009 kW, 연료 하중 40 MJ/㎡ 그대로. 배치 도중 입력·엔진 코드 SHA 불변 확인 true. 상태별 주의 수는 저장된 index-summary에서 읽었으며, 닫힘의 주의 실은 R11이다.

- 운영 화면의 기존 S06/00:00 유지 상태에서 계산 완료, 새 결과 2개가 목록에 자동 추가됐다.
- 결과 탭에서 두 사례 모두 읽혔고 fire_key=CAD_3F_R11, 60:00까지 데이터가 있다.
- 3D에서 R2 선택 상태 → R11 위치 클릭 → HUD R11로 바뀜 → 화점 지정 버튼으로 ③ R11 반영 확인.
- 셀 R2_C0 → 화점 지정 버튼 → ③ R2 확인(셀 ID로 실행하지 않음).
- 브라우저 콘솔 오류 0. 기존 R2 시나리오 생성 데이터가 수동 경로와 동일함을 단위 검사로 확인(선택 출처 메타데이터 제외).
- 자동 제외 R11의 **MC 실행은 기존 적격 제한을 유지**하고, 이번 범위에서는 2상태 실행만 제공한다. MC 버튼에 사유를 표시한다.
- 새 screening 결과도 기존 MC 전용 동등성 증거와 혼동하지 않는다. saved-case에서 동등성을 증명하지 못하면 기존 정책대로 “과거 결과 재사용” 표시다.

## 화면·동결 검증

S09 · 1420 s · R2 · 비스듬히, clock=180000 ms, 595×700 WebGL 버퍼 전체 비교: **변경 0픽셀**. HUD 버튼은 DOM이므로 3D 버퍼 비교에서 제외한다. 기존 위험 레이어 포함. 엔진·조건표·셰이더·render_order 등 55개 동결 SHA 전부 동일.

테스트: manual_origin.test.py 3건, explore.unit.mjs 통과. 잘못된/복수/셀/제외 미세공간 ID 거부, 자동 순위 불변, R2 기존 시나리오 불변 확인.

## 파일 변경 줄 수

아래는 코드 및 테스트의 실제 Git numstat다. 보고서·캡처는 별도다. 서버 라우팅 파일은 +3/-3이며 새 엔드포인트는 없다.

| 파일 | 추가 | 삭제 |
|---|---:|---:|
| `app/tests/explore.unit.mjs` | 2 | 2 |
| `app/web/controller.js` | 6 | 6 |
| `app/web/panels/display.js` | 5 | 3 |
| `app/web/panels/explore.js` | 11 | 8 |
| `app/web/state/store.js` | 2 | 1 |
| `simulation/viewer/overlay.js` | 24 | 18 |
| `tools/lite_screening_service.py` | 14 | 8 |
| `tools/run_lite_screening_v8_approved.py` | 23 | 9 |
| `tools/serve_cfbt_building.py` | 3 | 3 |
| `tools/lite_manual_origin.py` | 26 | 0 |
| `app/tests/manual_origin.test.py` | 32 | 0 |

## 증거

- `simulation/results/ui_C2_20261102/`: UI 캡처, 전후 3D 버퍼, SHA·시각·결과 요약.
- `simulation/results/lite_screening_ui_1793581362271399500/`: 실제 실행 input/result/playback/manifest/summary/index-summary와 배치 로그.
- `reviews/ui_C2_20261102/`: Git 검토용 소형 증거 복사본(계산 원본은 로컬 유지).

다음 항목은 C-3이다. C-9는 명세대로 C-8 뒤에 유지한다.
