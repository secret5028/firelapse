# 알려진 문제와 검증 범위

2026-11-11 기준입니다. 시험의 PASS와 미실행(SKIP), 계산 결과의 `unverified`는 구분합니다.

| ID | 상태·현상 | 재현·영향 | 조치 |
|---|---|---|---|
| KI-1 | 완화됨: 원본 PC 밖을 가리키는 옛 비교 결과 | `/cfbt/lite/screening`은 200을 유지하고 `attention_skipped`로 제외 건수 반환. 외부 경로는 읽지 않음 | 보안 경계 유지. 외부 원본 비교에 의존하는 과거 acceptance 5개는 별도 SKIP로 기록 |
| KI-2 | 수정됨: 장면 시험의 개발 서버·고정 URL 의존 | `risk_index_scene.test.mjs`가 자체 HTTPS fixture와 실제 WebGL로 실행됨 | 고정 8780 서버 및 120초 후 성공 처리 제거. 준비·렌더링 실패는 실제 FAIL |
| KI-3 | 수정됨: 수관 레이어의 DOM 의존 | `stage2.test.mjs`의 정적 경계 검사와 50회 장면 생성/해제 시험 | 캔버스 라벨 생성을 host factory로 이동. 수관 모양·색·좌표 유지 |
| KI-4 | 보존: building.json 출처 문자열과 결과 식별 해시 결합 | 출처 문자열만 고쳐도 저장 결과 연결이 달라질 수 있음 | 원본 모델 바이트·결과 ID 유지. 별도 마이그레이션 전 임의 치환 금지 |
| KI-5 | 소스와 실행 ZIP의 자료 구성 차이 | 소스의 `saved_results/*.gz`는 회귀 검증용 보관본. r19 실행 ZIP은 7개 모델, r18의 CFAST 4건, 2026-11-11 층별 CFAST 28건 포함. 과거 간략 엔진 결과는 제외 | `tools/test_all.py`는 보관 입력을 먼저 복원. 실행 패키지의 기존 결과는 변경·재계산하지 않음 |
| KI-6 | 기본 포트 밖의 CORS 제한 | 포트를 바꾸면 모델 라이브러리·AI 연결 조회가 실패할 수 있음 | 기본 loopback 포트 사용. 관련 위치: `PyroCast/config/model-library.json` operation_url, `PyroCast/tools/serve_model_library.py` Handler.send, 클라이언트 8841 참조. 보안 목록 임의 완화 안 함 |
| KI-7 | 호텔 B1 일부 입력 확인 필요 | 저장된 CFAST 결과의 `unverified` 표시 | 입력 증거 확인 전 확정·안전 판정으로 바꾸지 않음. 결과 자체 보존 |
| KI-8 | 과거 개발 환경 전용 증거와 폐기된 모드 시험 | 옛 화면 전후 비교 캡처, 원본 DWG, 구형 산소 모드 등에 의존하는 시험은 SKIP 가능 | 전수시험 보고서에 이름·사유를 그대로 남김. 현재 WebGL·단위시험·배포 UI 검증으로 대체하는 범위는 `docs/TESTING.md` 참조 |
| KI-9 | 견본주택 2F 계산 한도 초과 | r19 계산에서 70분 한도에 걸려 34분 40초 지점에서 중단. 준정상 조건이 아니어서 상수 연장도 적용되지 않음 | 같은 CFAST 입력·같은 실행 파일로 2026-11-10에 끝까지 계산한 결과를 수록. 미연소 연료 축적으로 `unverified` 표시 유지 |
| KI-10 | 계산을 끝내기 위한 단순화 2종 | 밀폐 구역 연료 방출 제한(호텔 B1·B2·B3 4건 적용), 준정상 상수 연장(r19 수록 결과에는 적용 없음) | 적용한 결과에 안내 문구 표시. 상수 연장 결과는 `unverified`로만 표시. 계수는 `PyroCast/config/physics_defaults.json`의 `fuel_release_limit`, `quasi_steady` |
| KI-11 | 저장 결과를 빠르게 연속 전환한 직후의 화면 지연 | 수 초 간격으로 여러 저장 결과를 연달아 넘긴 직후 다른 건물로 바꾸면, 서버가 앞선 요청을 처리하는 동안(최대 약 1분) 새 화면이 열리지 않을 수 있음. 자동 화면 검사에서 관찰 | 잠시 뒤 새로 고침하면 정상 표시. 결과 파일과 계산에는 영향 없음 |

FireLapse 자체 라이선스는 [LICENSE](LICENSE)의 **All rights reserved**입니다. 제3자 고지는 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)를 따릅니다.
