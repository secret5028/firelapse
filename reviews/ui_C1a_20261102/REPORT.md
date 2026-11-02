# C-1a — 전 구간 최대 이력 (2026-11-02)

## 결과

C-1a만 구현. 재계산 0회. 운영 8780 페이지에서 S09 0초/R2 실 확대 확인. 1커밋 후 정지, push 없음.

- `index_history_max[cell][type]`: 저장된 전체 0–3600초 최대값 1개. 시간 배열 제거.
- `index_history_peak_s[cell][type]`: 최대값이 최초로 나타난 저장 시각. 동률은 최초, 전부 미평가이면 값·시각 모두 null.
- 이력 ON: 해당 현상의 전 구간 최대가 테두리 기준에 도달하면 원래 방 외곽 점선. 현재 충족은 같은 위치에 실선을 덮어 그린다. FO·FGI·백드래프트·롤오버 독립, 기존 0.14m 간격.
- 주의: 전 구간 최대 70–99인 방은 회색 점선. 기존 정책대로 강한 유형 리본이 있는 방의 회색 주의선은 중복 표시하지 않는다. 표시 탭 임계값 조작 기능은 유지(검증값 100/70).
- 경로 색·요약표: 같은 전 구간 최대값을 읽는다. 시간바 0초와 1420초의 경로 행/지수/색이 동일함을 확인.
- 선택 실 카드: 최악 시각 1줄. 셀 선택 시 해당 셀, 방 선택 시 멤버 셀 최대와 최초 시각. 방 평균 시계열은 만들지 않음. 시각은 저장 표본 기준이며 표본 사이 극값을 추정하지 않는다.

## 합격 확인

| 장면 | FO | 백드래프트 | 주의 |
|---|---|---|---|
| S09 0:00 / 이력 ON | R2 점선 | R2 점선 | 5실 회색 점선 |
| S09 1420초 / 이력 ON | R2 실선, 같은 자리 점선 아래 유지 | R2 점선 | 5실 회색 점선 |

S09 선택 R2_C0 카드: **FO 143 @ 20:50 · FGI 64 @ 25:40 · 백드래프트 100 @ 59:40 · 롤오버 56 @ 16:30**.

S09 경로 R2 최대 FO 지수 142.64545170610427, 0초/1420초 동일. 이력 OFF는 현재 시각 값 사용.

## 이력 OFF 회귀

같은 WebGL 영역 595×700, host clock 180000ms, 변경 전 C-6 번들과 변경 후 번들 비교. 패널 문구 추가는 3D 픽셀 비교에서 제외.

| 장면 | 차이 픽셀 | 최대 채널 차이 |
|---|---:|---:|
| S09 · 1420초 | 0 | 0 |
| S09 · 1800초 | 0 | 0 |
| S06 · 890초 | 0 | 0 |
| 전체 보기 · 코어 ON | 0 | 0 |

## 검증과 불변 범위

- risk_history / risk_index / history_peaks / route_risk / route_layer 단위 검증 통과. 회색 점선 5실, 겹침, toggle, 원래 방 OR, geometry 재생성 없음, 자원 해제 확인.
- 계약 검증 S06/S09/stage4 3건, 12그룹 통과. 사례당 원 시계열 137,180개와 조건값 342,950개 일치, 최대 차이 0.
- 엔진·셰이더·bridge·render_order·서버 등 동결 60파일 SHA 동일.
- 운영 화면 콘솔 error 0. 시뮬레이션/MC 실행 0회.
- npm 레지스트리 접속 실패 후, 기존 설치된 E:/hermes/node/node_modules/ajv/dist/2020.js를 PYROCAST_AJV로 지정해 계약 검증 완료. 패키지 설정 변경 없음.

## 증거

`simulation/results/ui_C1a_20261102/`의 pixel-comparison.json, browser-verification.json, production-verification.json, route-history-verification.json, unit-verification.json, contracts/verification.json, frozen-unchanged.json 및 PNG. 운영 화면 캡처는 production-S09-0-history.png.
