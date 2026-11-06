# REPORT THEME-1 BLOCKED

운영 UI의 1·2단계 색 토큰 작업은 적용했다. 다만 엄격한 합격 조건 전체를 PASS로 판정하지 않는다.

## 남은 차단 사항
- 완도 저장 결과 뷰어는 변경 전부터 `/cfbt/calculation` GET에 404를 반환한다. JS 예외는 0이지만 HTTP 오류까지 포함한 “브라우저 오류 0”은 충족하지 않는다. CSS 범위 밖의 서버 계산 경로는 고치지 않았다.
- 별도 CAD 모델 점검 페이지의 `app/web/panels/model_review.js`에는 기존 3색(`#9eb2c4`, `#7bd6c4`, `#edbf75`)이 남아 있다. 이 페이지는 운영 shell과 별도 stylesheet/서버 경로를 사용하며 이번 검수 10장면 대상이 아니다. 따라서 **app/web 전체 grep에서 지수·3D만 남았다는 조건은 미충족**이다. AI 연결을 보존하려고 해당 별도 서버의 재시작·범위 확대는 하지 않았다.
- 기존 과거 PNG와 현재 앱 자체의 동일성은 주장하지 않는다. 현행 HEAD e3765d2의 색 원값을 보존한 동일 장면·데이터·프레임 비교를 실시했다. 과거 review2 장면 유형은 현재 호텔 결과 1440/375로 재현했다.

## 1단계 검증
원래 색·알파를 131개 임시 토큰으로 보존. 토큰을 역치환한 JS 소스가 원본과 동일함을 확인했다.
픽셀 마스킹 없음. renderer 프레임과 저장 결과를 고정하고 원래 CSS 값/토큰 CSS를 연속 비교했다.

|장면|변경 픽셀|
|---|---:|
|hotel-1440-building|0|
|hotel-1440-display|0|
|hotel-1440-result|0|
|hotel-375-building|0|
|hotel-375-display|0|
|hotel-375-result|0|
|intech-1440-result|0|
|intech-375-result|0|
|S06-890-3F|0|
|S09-1420-3F|0|
|S09-1800-3F|0|
|S09-1800-전체|0|
|wando-1440-result|0|
|wando-375-result|0|

원본 분리 로드 캡처에서는 호텔 MC 응답 S04/S08 경합 146픽셀과 S06 렌더링 프레임 차이 29픽셀이 있었다.
`before/`, `stage1/`에 이를 보존했고, 데이터·프레임을 고정한 `paired-before/`, `stage1-paired/`는 모두 0이다.
1단계 단독 HTML 호텔·아이엔테크: 외부 요청 0, JS 예외 0, 실제 재생/시간 이동 확인.

## 2단계 검증
- 지정 다크 팔레트 적용, 라이트 변수 블록만 추가. 토글 UI 없음. 기본 dark.
- 본문 13px, 캡션 11px, 제목 14/20px. 검수 장면의 표시 글자 중 11px 미만 0.
- 지수·3D 의미색·흰 수관·청색 코어·문/창/연료 색·셰이더·부제 하이픈 유지.
- 기존 상태 요소에 클래스만 추가. 신규 문구·요소·탭·배치·토글 기본값·계산 경로 변경 없음.
- 표시 토글 24개 왕복 후 layers/realView/openings/risk/displayDetails 상태 동일.
- 14장면 가로 넘침 0, JavaScript 예외 0. 의도적으로 차단한 POST는 별도 기록하며 서버에 보내지 않았다.
- 단독 HTML 호텔 25:00→25:40, 아이엔테크 00:30→01:00 재생 확인. 두 파일 모두 새 `--bg-panel:#0d141c`, 외부 요청 0, 예외 0, 가로 넘침 0.
- 새 기준 4장면: `new-baseline/S06-890-3F.png`, `S09-1420-3F.png`, `S09-1800-3F.png`, `S09-1800-전체.png`.
- Python 패키저 시험 5/5, results.unit / result_list / timeline_risk.unit 통과. 변경 JS 및 번들 문법 확인 통과.
- 보호 파일 검사는 `protected.json`, UI 상태·토글·색·캡처 검사는 `stage2/capture.json`, 단독 재생은 `stage2/offline-check.json`.

### 전후 캡처 10쌍
- hotel-1440-result: [전](paired-before/hotel-1440-result.png) · [후](stage2/hotel-1440-result.png)
- hotel-1440-building: [전](paired-before/hotel-1440-building.png) · [후](stage2/hotel-1440-building.png)
- hotel-1440-display: [전](paired-before/hotel-1440-display.png) · [후](stage2/hotel-1440-display.png)
- hotel-375-result: [전](paired-before/hotel-375-result.png) · [후](stage2/hotel-375-result.png)
- hotel-375-building: [전](paired-before/hotel-375-building.png) · [후](stage2/hotel-375-building.png)
- hotel-375-display: [전](paired-before/hotel-375-display.png) · [후](stage2/hotel-375-display.png)
- intech-1440-result: [전](paired-before/intech-1440-result.png) · [후](stage2/intech-1440-result.png)
- intech-375-result: [전](paired-before/intech-375-result.png) · [후](stage2/intech-375-result.png)
- wando-1440-result: [전](paired-before/wando-1440-result.png) · [후](stage2/wando-1440-result.png)
- wando-375-result: [전](paired-before/wando-375-result.png) · [후](stage2/wando-375-result.png)

### 상태색 요소
- `resultEvaluation`: 계산됨 → status-ok, 미평가는 중립.
- `exploreStatus`: 기존 진행/오류 값으로 status-busy/status-error.
- `exploreEstimate`: 계산 가능한 예상 시간만 status-busy.
- `exploreMCStatus`: 진행 중 status-busy, 완료 status-ok, 실패/시간초과/차단/미완료/오류 status-error.
- `exploreCalculateStatus`: 계산 중 status-busy, 표시가 “계산 완료”일 때만 status-ok, 기존 error가 있으면 status-error.
- `resultMCStatus`: 집계 읽기 status-busy, 완주 집계 status-ok, 미완료 표본·읽기 실패 status-error.
- `exportStatus`: 묶는 중 status-busy, 다운로드 준비 status-ok, 기존 예외 status-error.

## 치환 파일과 diff 줄 수
생성 번들 포함. +추가 / −삭제. CSS 속성·문자열 치환과 기존 상태 클래스 할당만 변경했다.

|파일|1단계|2단계|
|---|---:|---:|
|PyroCast/app/model-library/operation-controls.js|+1 / −1|+1 / −1|
|PyroCast/app/model-library/operation.html|+2 / −1|+1 / −1|
|PyroCast/app/tests/lite_export.test.py|+3 / −1|—|
|PyroCast/app/web/controller.js|—|+3 / −3|
|PyroCast/app/web/entry.js|+1 / −1|+1 / −1|
|PyroCast/app/web/panels/ai_connection.js|+1 / −1|+2 / −2|
|PyroCast/app/web/panels/ai_fuel.js|+1 / −1|+1 / −1|
|PyroCast/app/web/panels/assistant.js|+1 / −1|+1 / −1|
|PyroCast/app/web/panels/building.js|+1 / −1|+1 / −1|
|PyroCast/app/web/panels/display.js|+9 / −9|+9 / −9|
|PyroCast/app/web/panels/explanations.js|+1 / −1|+1 / −1|
|PyroCast/app/web/panels/explore.js|+3 / −3|+6 / −2|
|PyroCast/app/web/panels/export.js|—|+3 / −3|
|PyroCast/app/web/panels/fuel_settings.js|+1 / −1|+1 / −1|
|PyroCast/app/web/panels/legacy_lite_panel.js|+5 / −5|+5 / −5|
|PyroCast/app/web/panels/new_building.js|+2 / −2|+1 / −1|
|PyroCast/app/web/panels/result_list.js|+1 / −1|+1 / −1|
|PyroCast/app/web/panels/results.js|+5 / −5|+5 / −5|
|PyroCast/app/web/panels/route.js|+5 / −5|+4 / −4|
|PyroCast/app/web/panels/shell.js|+26 / −26|+16 / −16|
|PyroCast/app/web/panels/timeline_risk.js|+4 / −4|+4 / −4|
|PyroCast/cad-project/model.html|+6 / −5|+16 / −16|
|PyroCast/data/wando-coldstore/model.html|+2 / −1|+1 / −1|
|PyroCast/data/wando-coldstore/operating.js|+1 / −1|+1 / −1|
|PyroCast/simulation/viewer/overlay.css|+11 / −11|+12 / −12|
|PyroCast/simulation/viewer/overlay.js|+66 / −66|+64 / −60|
|PyroCast/simulation/viewer/theme.css|+150 / −0|+60 / −143|
|PyroCast/tools/lite_export.py|+3 / −0|—|
|PyroCast/tools/serve_cfbt_building.py|+1 / −1|—|

## grep·보존 범위
`hardcoded-colors.json`은 `#[0-9a-fA-F]{3,8}(?![a-zA-Z0-9_-])`로 app/web 전체를 검사한 결과다.
운영 패널 잔여색은 지수·3D와 대응 범례이다. 별도 model_review 3색은 위 차단 사항에 명시했다.
색 값은 theme.css에 모으고 2단계에서 compat 토큰을 모두 제거했다. 외부 웹폰트 없음.
config/display.json 및 renderer/layers/state/adapters/scene 보호 파일 내용 불변.
새 시뮬레이션·AI 호출·기존 결과 수정·GitHub push 없음. AI 연결을 가진 PID 6028은 재시작하지 않았다.

## 커밋
- 1단계: `dccacf3` — exact-value theme tokens and offline CSS packaging.
- 2단계: 이 보고서를 포함하는 후속 단일 커밋(`git log -1`). 최종 응답에 해시를 기록한다.

단독 HTML 파일은 저장소 용량 증가를 피하려고 커밋하지 않았다. 실제 검증 파일 위치:
- `C:\Users\예방\.codex\visualizations\2026\10\19\01a15674-ce4b-7f52-bd4e-fd6c939240ad\theme1/stage2/hotel-offline.html`
- `C:\Users\예방\.codex\visualizations\2026\10\19\01a15674-ce4b-7f52-bd4e-fd6c939240ad\theme1/stage2/intech-offline.html`
