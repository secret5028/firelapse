# 알려진 문제

저장소 정리 PUBLISH-1b(2026-11-06)에서 공개한 제한 사항입니다. 아래 시험 제외는 결함 수정이나 물리 검증 통과를 의미하지 않습니다.

| ID | 현상 | 재현 | 영향 | 예정 조치 |
|---|---|---|---|---|
| KI-1 | **완화됨(응답 유지, 항목 제외)**: 저장 comparison의 원본 PC result_folder가 워크스페이스 밖이면 attention 집계에서 그 항목만 제외 | 다른 경로의 clone에서 /cfbt/lite/screening 조회; attention_skipped 건수 확인 | 보안 경계 유지·외부 결과 미열람; 유효 항목과 기존 응답 유지. 기존 fixture 5개 skip은 유지 | 결과 경로 이식 방식은 별도 검토; 이번에 제외 건수와 파일명만 경고 기록 |
| KI-2 | Headless WebGL 장면 준비가 120초 안에 완료되지 않을 수 있음 | risk_index_scene.test.mjs after | 해당 화면 비교가 실행되지 않음; 앱의 모든 WebGL 동작이 검증됐다는 뜻 아님 | headless 장면 fixture·준비 신호 점검; 대기 초과만 명시적 skip |
| KI-3 | route.js가 host 바깥에서 DOM에 의존 | stage2.test.mjs의 정적 검사 | 레이어 경계 구조 결함; 이번 구조 동결 범위에서 해당 시험 skip | **다음 UI 작업에서 수정**: DOM 처리를 host 경계로 이동하고 시험 복구 |
| KI-4 | 호텔·아이엔테크 building.json의 출처 경로가 전체 파일 SHA256 결과 ID에 묶임 | source 문자열만 바꿔도 SHA와 저장 결과 연결이 달라짐 | 이 두 파일의 원본 PC 경로 유지 | 별도 승인된 identity/출처 분리 설계와 기존 결과 호환 검증; 이번에는 파일 보존 |
| KI-5 | 소스 clone의 저장 결과는 강화 11건·완도 1건 | clone 기동 후 사례 목록 확인 | 다른 건물은 모델 미리보기이며 최신 전체 결과 미포함 | 전체 7개 건물·152개 결과는 Releases 실행 ZIP 사용; 호텔·아이엔테크는 docs/samples의 단독 HTML 제공 |
| KI-6 | 서버 포트를 기본값(8841 등)에서 바꾸면 모델 라이브러리·AI 연결 조회가 CORS로 실패할 수 있음 | 임시 포트에서 models/catalog.json·models/ai/connection 조회 | 해당 연결 조회 실패; 저장 재생과 구분 | 포트 변경 시 허용 Origin 목록에 새 포트를 추가해야 함. 등록 모델의 설정은 PyroCast/config/model-library.json의 operation_url, 고정 허용 목록은 PyroCast/tools/serve_model_library.py의 Handler.send에 있음(독립 CORS 설정 파일은 없음). 클라이언트 8841 고정 참조도 함께 검토. 이번에는 코드·설정 변경 없음 |
