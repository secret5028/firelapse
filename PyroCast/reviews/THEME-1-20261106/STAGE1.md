# REPORT THEME-1 — 1단계

기존 색·알파 값을 임시 토큰으로 보존했다. 2단계 팔레트는 아직 적용하지 않았다.
JS 소스에서 토큰을 원래 색으로 역치환하면 원본과 텍스트가 일치한다. 동작 조건·DOM·계산식 변경 없음.

## 픽셀 비교
변경 직전 HEAD e3765d2의 현행 UI를 기준으로 동일 데이터·프레임에서 비교했다.
paired-before는 현행 CSS 원값, stage1-paired는 토큰 CSS이다. 화면 일부 마스킹 없이 비교했다.
기존 review2-desktop/mobile의 호텔 결과 장면 유형을 1440×1000 / 375×844에서 다시 검증했다.
과거 PNG와 현재 UI 전체의 동일성을 주장하지 않는다.

- hotel-1440-building: 0 픽셀
- hotel-1440-display: 0 픽셀
- hotel-1440-result: 0 픽셀
- hotel-375-building: 0 픽셀
- hotel-375-display: 0 픽셀
- hotel-375-result: 0 픽셀
- intech-1440-result: 0 픽셀
- intech-375-result: 0 픽셀
- S06-890-3F: 0 픽셀
- S09-1420-3F: 0 픽셀
- S09-1800-3F: 0 픽셀
- S09-1800-전체: 0 픽셀
- wando-1440-result: 0 픽셀
- wando-375-result: 0 픽셀

최초 별도 로드 비교에서 호텔 결과 146픽셀은 MC 요약 S04→S08 비동기 응답 차이였고,
S06 29픽셀은 렌더링 프레임 차이였다. 해당 원본 비교도 before / stage1에 보존한다.
동일 데이터·동일 프레임 연속 비교에서는 모두 0이다.

브라우저 JS 예외 0. HTTP 오류에는 검증기가 의도적으로 차단한 POST 409와 기존 완도 /cfbt/calculation 404가 있다.
완도 404는 변경 전에도 존재하며 CSS 범위에서 서버 계산 경로를 수정하지 않았다. 엄격한 전체 브라우저 오류 0 조건은 미충족이다.
AI 요청·새 계산은 보내지 않았다. AI 연결 서버를 재시작하지 않았다.
패키저 기존 시험 5/5 통과. 단독 HTML 검증 결과는 stage1/offline-check.json에 기록한다.
3D 의미색·셰이더·부제 하이픈 보존. push 없음.
