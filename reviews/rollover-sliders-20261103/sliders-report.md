# 농도·밝기 슬라이더 검수

- 3D 우하단: 연기 농도 30~150%, 화염 밝기 50~200%, 각각 기본 100%. 표시 탭과 양방향 동기화.
- smokeOpacity 0.7 유지. 표시 알파 = 기존 연기 알파 × smokeOpacity × smokeGain. 화염 최종 RGB × flameGain. 온도·OD·발열량·화염 크기·조명·계산 결과는 바꾸지 않음.
- 기본 4장면: 3D 픽셀 차이 0. 새 슬라이더 UI는 비교에서 숨겼으며 범례 DOM은 비교 영역에서 제외. 전체 캡처는 3F 3장에서 범례 글자 가장자리 6픽셀/채널 최대 1 차이, 전체 보기 0. pixel-comparison.json에 좌표 전부 기록. 따라서 전체 스크린샷 0이라고 주장하지 않음.
- 30/50 → 150/200 → 100/100 왕복, 표시 탭 80/120 → 우하단 값 반영 통과. 범위 밖·NaN 거부 시험 통과.
- 단독 HTML 8,362,754 bytes (7.98 MiB): file:// 열기, 저장된 80/120 복원, 150/50 조작, HTTP 0·콘솔 오류 0. 첫 검사는 두 3D 페이지를 연 상태에서 30초 로드 제한에 걸렸고, 파일 단독/180초 한도로 재검증 통과. 실제 파일은 gains/PyroCast-S09-gains.html에 로컬 보관(생성 HTML은 커밋 제외).
- 완도 P1 2120초 캡처 포함. smoke uniform 1.05(0.7×1.5), flame uniform .5 확인. UI dispose + 기존 완도 pagehide 후 컨트롤 0·구독 0.
- 서버·엔진·결과 데이터 변경 없음(이 커밋). 기존 export의 realView 전체 스냅샷/복원으로 배율도 포함.

## 수정 줄 수 (+ / −)

```text
1	1	PyroCast/app/web/layers/real_view.js
15	1	PyroCast/app/web/panels/display.js
2	1	PyroCast/app/web/state/store.js
2	2	PyroCast/simulation/viewer/legacy_real_bridge.js
6	5	PyroCast/simulation/viewer/legacy_real_view.js
18	3	PyroCast/simulation/viewer/overlay.js
```
