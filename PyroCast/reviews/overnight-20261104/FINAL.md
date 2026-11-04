# PyroCast 야간 작업 종료 보고 — 2026-11-04

실행 가능한 대표 시나리오와 확인된 앱 버그 수정을 마쳤다. **전체 건물의 계산 성공이나 물리 타당성 검증 완료는 아니다.** 남은 수치 실패·기하 오류는 반복 실행이나 임의 보정 없이 보존했다. 계산 작업은 모두 종료했으며 웹 서버는 사용을 위해 유지한다. 자동 작업은 이 보고 후 종료한다. Git push 없음.

## 실행 범위

- CAD 25층 중 간략 엔진 22회 직렬 실행: **21층 3600 s 완주, 호텔 10F 1층 수치 실패**, 입력 준비 불가 3층은 미실행.
- 각 층의 기존 후보 점수 1위 실을 대표 화점으로 선택했다. 이번 배치는 **MC 최악 급기 탐색이 아니다**. 입력 확정 급기는 유지하고 나머지는 입력 기본 상태를 기록했다.
- 간략 회당 1200 s 예산, 작업자 1개, 자동 재시도 0회. 스캔 건물 2건은 계산 제외.
- 완도 1F는 일반 CAD 변환을 사용하지 않고 기존 전용 CFAST P1 입력을 새 폴더에서 1회 재현했다. CAVITY는 R5 벽의 내부 공동 화원이며 외부 화재로 바꾸지 않았다.
- 완도 native 정상 종료: 엔진 로그 154 s / 전체 157.766 s. CSV는 기존과 같은 **3595 s까지**, 마지막 5 s 미출력. `partial_output`, 보간·외삽 없음. 기존 P1의 compartments/masses/vents CSV와 컬럼·shape·수치 차이 0.

## 실패·미해결

|구분|대상|근거와 남은 작업|
|---|---|---|
|수치 실패|호텔 10F R15|299.406 s 후 `Factor is exactly singular`. 저장 표본 700 s, 마지막 정상 적분구간 끝 704.8065 s. 이는 정확한 실패 시각이 아니다. 실패 내부 상태가 없어 최초 원인 미확정. 완료 playback 게시 없음.|
|입력 blocked|강화 B1 R12|면적 1.1636 m²의 등가 실에 폭 4.12 m W2. CAD 경계·소속 확인 필요. 폭을 잘라 통과시키지 않음.|
|입력 blocked|강화 PH R3|.5599×8.8579 m, 개구부·이름 없음, 고립 공간. 최소 폭 문제와 공간 분류를 확인해야 함. 임의 제외·박스 변형 없음.|
|입력 blocked|호텔 B1 R9|면적 .9512 m²에 승강기 문 6개, 최대 폭 1.719 m. CAD 소속 확인 필요.|
|물리 검증 미완|호텔 미연 연료·FGI/BD|새 5F FGI78/BD75는 입력 기본 개폐 상태의 결과다. 과거 열린 조건의 0을 엔진 수정으로 높인 것이 아니다. 동일 입력 순정 CFAST 대조는 미실행.|

호텔 10F 진단은 로그·저장된 이벤트/구간 통계 조사까지 수행했다. 실패 지점의 전체 y/RHS 덤프, 매 적분 스텝의 분기 추적, 다른 솔버/허용오차 대조 실행은 하지 않았다. 입력 사본은 보존했지만 작은 인접 체적이 원인이라고 확정하지 않았다. 층 질량 0·채터링·야코비안 factor 이월을 원인으로 단정하지 않는다. 임계값·물리식·솔버 변경 없음.

## 수정과 검수

|커밋|항목|검증|
|---|---|---|
|82fc42b|대표 화점 직렬 배치, 입력·엔진 SHA 동결, 잠금·예산|22회 직렬, 중복·자동 재시도 없음|
|3a0a7ff|손상·누락 저장 사례 하나 때문에 전체 사례 목록이 실패하는 문제 격리|8종 입력 합성 시험 통과, 제외 항목 사유 기록|
|6cb32d2|닫힘 상태와 작은 누설 fraction을 분리|관련 4시험 통과. 실제 강화3F boolean 수정 대상 0건. 표시 필드 보강 외 계산 배열 동일|
|843dbb3|완도 후처리 증거의 Windows 경로 구분자 정규화|2시험 통과. 엔진·덱·model 위변조 거부 유지. 코드 +8/−2줄, 시험 +15줄. 후처리만 재실행|
|a8dd416 / 6ff6c88|층별 집계·실패 진단 및 완도 재현 보고|성공21건 입력/엔진SHA·3600s·유한 시계열·게시 사본 오류0|

실제 Claude 데스크톱의 기존 야간 중계 대화에서 6회 검토를 받았다(`claude-review-1.txt`~`6.txt`). 파일 동시 수정은 요청하지 않았다. 증거 해시, null 보존, 실패/미실행 분리, 원본 보호 의견을 채택했다. 근거 없는 기하 보정·물리 원인 단정은 채택하지 않았다. Claude 최종 의견의 ‘모든 HTML/AI 경로도 검증됨’ 또는 ‘모든 원본 폴더 해시 불변’은 이번에 전수 입증하지 않았으므로 이 보고서의 사실로 채택하지 않는다. 기존 결과를 덮어쓰지 않았고 직접 대조한 범위는 별도 증거에 한정한다.

## 운영 검증

- 호텔 14건 + 견본주택 3건 저장 사례 HTTP 재열기: **17건 오류 0**. 이 중 2건은 기존 60 s 시범 결과, 15건은 3600 s 결과이며 모두 이번 밤 신규 결과라는 뜻은 아니다.
- Chrome 호텔 운영 화면: 최신 PH 결과 로드, 5F 선택 후 결과 탭 유지, 계산 범위 PH는 별도 표시, 선택 실 없는 상태의 지수·계산값 `—` 확인.
- 표시 스위치 24개 OFF/ON 왕복 후 상태 완전 일치. 해당 탭 콘솔 error 0. 새 계산 버튼은 누르지 않았다.
- `result_scope.test.mjs`, `calculation_status.test.mjs` 통과: 미평가와 실제0, 다른 화점·오래된 입력과 완료 상태 구분.
- 광범위 기존 시험 결과: app 33파일 중 17PASS/16FAIL(환경 인수·과거 fixture 포함), simulation 252개 중 241PASS/1FAIL/10ERROR. 삭제된 기능 기대와 fixture 누락이 섞여 있으며 **전체 회귀 통과 아님**. 상세는 before 로그와 README 참조.
- 인앱 브라우저 제어 연결이 불가하여 최종 점검은 별도 Chrome 탭에서 했다. 사용자 기존 탭·결과를 바꾸지 않았다.

## 상세 증거

- 입력·엔진·급기·화점 장부: `simulation/results/overnight-20261104/progress.json`, `plan.json`
- 정상 출력 검증: `result-validation.json`
- 실패·기하: `hotel-10F-failure.json`, `blocked-geometry.json`
- 완도 비교: `wando-reproduction.json`; 새 P1의 `nightly-status.json`, `postprocess-evidence.json`
- 계산 지수는 조건표 버전에 종속된다. 완도 후처리 SHA를 별도로 기록했고, 값이 높아졌다는 이유로 물리 검증 성공이라고 보지 않는다.


## 층별 실행·시간·지수

간략 엔진, 3600 s, 기존 후보 점수 1위. 최악 급기 탐색 결과가 아닌 대표 시나리오. 미실행/실패는 —. 최고값은 평가된 표본 범위만 사용하며, 일부 미평가 시각과 셀은 JSON의 partial_conditions에 기록.

|건물|층|화점|상태|적분 s|전체 s|연소 실 수|FO 최고|FGI 최고|BD 최고|
|---|---|---|---|---:|---:|---:|---|---|---|
|ganghwa|3F|CAD_3F_R1|complete|37.12|46.64|1|39.7 @ 3600s (CAD_3F_R1)|0.0 @ 10s (CAD_3F_R1)|0.0 @ 10s (CAD_3F_R1)|
|parkmarine|5F|CAD_5F_R16|complete|51.42|58.06|1|134.3 @ 470s (CAD_5F_R16)|78.1 @ 690s (CAD_5F_R16)|74.9 @ 700s (CAD_5F_R16)|
|ganghwa|1F|CAD_1F_R9|complete|974.71|983.70|4|104.3 @ 1870s (CAD_1F_R0)|114.7 @ 1020s (CAD_1F_R31)|176.8 @ 2300s (CAD_1F_R17)|
|ganghwa|2F|CAD_2F_R7|complete|328.44|337.00|1|108.8 @ 910s (CAD_2F_R7)|78.3 @ 1570s (CAD_2F_R7)|79.4 @ 1410s (CAD_2F_R7)|
|ganghwa|4F|CAD_4F_R0|complete|68.31|78.51|1|52.2 @ 1770s (CAD_4F_R0)|46.3 @ 1970s (CAD_4F_R0)|41.6 @ 2040s (CAD_4F_R0)|
|ganghwa|5F|CAD_5F_R12|complete|24.21|32.69|1|118.6 @ 2510s (CAD_5F_R12)|69.4 @ 2940s (CAD_5F_R12)|56.1 @ 2950s (CAD_5F_R12)|
|ganghwa|6F|CAD_6F_R2|complete|121.40|133.42|1|87.8 @ 1840s (CAD_6F_R2)|59.0 @ 1980s (CAD_6F_R2)|59.0 @ 1980s (CAD_6F_R2)|
|ganghwa|7F|CAD_7F_R0|complete|46.93|55.75|1|58.4 @ 1140s (CAD_7F_R0)|58.9 @ 1290s (CAD_7F_R0)|55.3 @ 1330s (CAD_7F_R0)|
|ganghwa|B1|—|blocked|—|—|—|—|—|—|
|ganghwa|PH|—|blocked|—|—|—|—|—|—|
|parkmarine|10F|CAD_10F_R15|failed|—|299.41|—|—|—|—|
|parkmarine|1F|CAD_1F_R3|complete|8.91|14.06|1|49.7 @ 180s (CAD_1F_R3)|0.0 @ 10s (CAD_1F_R5)|0.0 @ 10s (CAD_1F_R5)|
|parkmarine|2F|CAD_2F_R1|complete|23.28|27.55|1|96.1 @ 880s (CAD_2F_R1)|101.1 @ 1190s (CAD_2F_R3)|69.2 @ 1210s (CAD_2F_R1)|
|parkmarine|3F|CAD_3F_R1|complete|20.10|24.36|1|87.0 @ 1570s (CAD_3F_R1)|80.6 @ 1640s (CAD_3F_R3)|59.1 @ 1690s (CAD_3F_R1)|
|parkmarine|4F|CAD_4F_R11|complete|42.36|47.72|1|133.9 @ 480s (CAD_4F_R11)|75.1 @ 690s (CAD_4F_R11)|73.3 @ 740s (CAD_4F_R11)|
|parkmarine|6F|CAD_6F_R16|complete|42.09|47.66|1|133.9 @ 480s (CAD_6F_R16)|77.3 @ 690s (CAD_6F_R16)|74.1 @ 690s (CAD_6F_R16)|
|parkmarine|7F|CAD_7F_R16|complete|41.57|47.06|1|133.9 @ 480s (CAD_7F_R16)|77.1 @ 690s (CAD_7F_R16)|74.2 @ 690s (CAD_7F_R16)|
|parkmarine|8F|CAD_8F_R11|complete|42.51|48.03|1|133.6 @ 480s (CAD_8F_R11)|73.9 @ 710s (CAD_8F_R11)|73.9 @ 710s (CAD_8F_R11)|
|parkmarine|9F|CAD_9F_R15|complete|41.76|46.92|1|134.0 @ 480s (CAD_9F_R15)|79.0 @ 700s (CAD_9F_R15)|76.9 @ 710s (CAD_9F_R15)|
|parkmarine|B1|—|blocked|—|—|—|—|—|—|
|parkmarine|B2|CAD_B2_R5|complete|44.15|49.95|2|100.2 @ 850s (CAD_B2_R5)|73.1 @ 1040s (CAD_B2_R5)|85.2 @ 1010s (CAD_B2_R5)|
|parkmarine|B3|CAD_B3_R6|complete|68.42|72.95|1|17.4 @ 3150s (CAD_B3_R6)|7.4 @ 3600s (CAD_B3_R6)|5.5 @ 3600s (CAD_B3_R6)|
|parkmarine|PH|CAD_PH_R4|complete|1.87|5.06|1|87.2 @ 2920s (CAD_PH_R4)|0.0 @ 10s (CAD_PH_R0)|0.0 @ 10s (CAD_PH_R0)|
|showroom|1F|CAD_1F_R6|complete|164.97|170.88|3|55.0 @ 760s (CAD_1F_R6)|68.2 @ 940s (CAD_1F_R6)|62.7 @ 960s (CAD_1F_R6)|
|showroom|2F|CAD_2F_R27|complete|14.04|20.16|1|56.6 @ 850s (CAD_2F_R27)|51.7 @ 1080s (CAD_2F_R27)|43.5 @ 1130s (CAD_2F_R27)|

완도 추가: 1F / CAVITY(P1 벽체 공동) / stock CFAST / 전체 157.766 s / 정상 종료, CSV3595 s partial_output.

## 층별 급기·고립 입력 기록

|건물|층|급기 상태 출처|고립 공간 수|
|---|---|---|---:|
|ganghwa|3F|confirmed_subset_and_input_default|4|
|parkmarine|5F|input_default|1|
|ganghwa|1F|input_default|2|
|ganghwa|2F|input_default|2|
|ganghwa|4F|input_default|2|
|ganghwa|5F|input_default|2|
|ganghwa|6F|input_default|2|
|ganghwa|7F|input_default|2|
|ganghwa|B1|준비 불가|—|
|ganghwa|PH|준비 불가|—|
|parkmarine|10F|input_default|2|
|parkmarine|1F|input_default|3|
|parkmarine|2F|input_default|3|
|parkmarine|3F|input_default|2|
|parkmarine|4F|input_default|2|
|parkmarine|6F|input_default|1|
|parkmarine|7F|input_default|1|
|parkmarine|8F|input_default|1|
|parkmarine|9F|input_default|2|
|parkmarine|B1|준비 불가|—|
|parkmarine|B2|input_default|10|
|parkmarine|B3|input_default|4|
|parkmarine|PH|input_default|2|
|showroom|1F|input_default|2|
|showroom|2F|input_default|4|

고립 공간은 입력 경고이며 자동으로 문을 만들지 않았다. 상태 출처 confirmed_subset_and_input_default는 사용자 확정 부분만 유지하고 나머지 원 입력 상태를 썼다는 뜻이다.
