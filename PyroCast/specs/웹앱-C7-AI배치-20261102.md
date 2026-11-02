# C-7 AI 가연물 배치 — 2026-11-02

## 결과

C-7만 구현, 1커밋 후 정지. API 미설정으로 실제 API 호출은 **미검증**. 사용자가 승인한 모의 응답 검증 완료. 모의 구현은 app/tests 안에만 있고 운영 코드에는 모의 분기가 없음. 시뮬레이션/MC 실행 0회, 외부 LLM API 호출 0회.

## 구현

- config/ai.example.json: 요청한 Anthropic URL·claude-sonnet-5-5·PYROCAST_AI_KEY 및 `_comment`/`_vllm_example` 포함. 유효 JSON. 실제 config/ai.json은 .gitignore.
- POST /cfbt/lite/ai/fuel: 사용자 문장+세션 history. 서버가 전층 실 ID·CAD 라벨·면적·용도와 fire_load_table 클래스를 시스템 메시지로 구성. chat/completions 호환 호출. API 키는 서버 환경변수만 참조, 브라우저 미전달.
- 순수 JSON 배열만 허용. 추가 설명·코드펜스·허용되지 않은 실/클래스·중복 ID·중복 JSON 키는 거부. 검증 실패 재요청 1회. HTTP 오류 본문/원 응답을 로그나 오류 응답에 복사하지 않음. 원격 HTTPS, 로컬 HTTP, 리다이렉트 금지.
- 건물 탭 하단 접힘 AI 배치. 실/현재/제안 용도/MJ/m²/근거 표, 행별 체크, 선택 적용. 초기 체크 없음.
- 서버의 30분 유효 제안 토큰에서 선택 행만 저장. 임의 클라이언트 수치/클래스 적용 불가. 동일 입력 확인, 1회 적용, atomic JSON 저장.
- 저장 위치 simulation/config/fuel-overrides.json. 기존 승인 입력 분류보다 우선하며 표의 mean/rhrf를 사용. ① 즉시 재점수, ② 재실행 필요 배지. 현재 playback 자동 교체 없음.
- 실제 API 미설정 안내와 버튼 비활성 확인. 단독 HTML에서는 보기 전용. 대화는 브라우저 세션 메모리만 사용.

## 모의 합격 시험

별도 127.0.0.1:8821 서버, 별도 results/ui_C7_20261102/mock/config/fuel-overrides.json. 운영 정정 파일·설정 파일은 생성하지 않음.

| 항목 | 결과 |
|---|---|
| “1층은 소매점이고 2층은 타이어창고” | 1F·2F 63실 제안 |
| 선택 적용 | 1F R0, 2F R0 두 행만 적용; 미선택 61행 미적용 |
| 1F R0 | 판매시설 600 MJ/m², 250 kW/m² |
| 2F R0 | 창고 1180 MJ/m², 500 kW/m² |
| 3F R2 별도 제안 | 공장→판매시설, 1800→600 MJ/m², 500→250 kW/m² |
| ① R2 순위 | 6위(2.903)→8위(2.772) |
| ② | 기존 결과 유지, 재실행 필요(연료 변경) |
| 운영 API 미설정 | “API 미설정 — config/ai.json”, 요청/적용 비활성 |
| 콘솔 | 운영·모의 오류 0 |

현재 계산용 입력은 3F에만 있다. 1F·2F는 전층 용도표·정정 저장을 검증했고, 순위 변경은 별도 3F R2 제안으로 검증했다. 다른 층의 시뮬레이션 입력 확장은 이번 범위가 아니다. 타이어 전용 클래스가 없어 일반 창고 대용이라는 근거를 명시했으며 타이어 하중을 새로 만들지 않았다.

## 테스트·보안

- app/tests/ai_fuel_test.py 통과: JSON 밖 설명 재요청 1회, 불량 JSON/클래스 거부, 미선택 행 적용 거부, 재적용 거부, 저장 전 무영향, 공급 상한·하중·순위 변경 확인.
- 임의 생성한 모의 키를 반사하는 AI 응답도 거부. 키는 테스트 프로세스 환경변수에만 존재. rg 고정문자열(stdin 패턴)로 테스트 출력/설정/소스 스캔: 일치 0, returncode 1. 직렬화 응답에도 키 없음. 실제 API 키는 미설정이므로 실키 실통신 검증으로 주장하지 않음.
- config·AI 소스·C7 로그/산출물에서 `api_key` 값 및 `sk-ant-...` 패턴 grep 일치 0. 운영 모듈에서 mock/fixture/모의 분기 grep 일치 0.
- building_panel.unit.mjs 통과. stage2.test.mjs는 Playwright 의존성 누락으로 실행하지 못했으며, UI 조작·캡처는 브라우저 도구로 검증했다.
- 기존 동결 목록 56파일 중 55파일 SHA 동일. 다른 1파일은 screening_v8_approved.py의 **용도/연료 입력 준비 부분**(+12/-1): 정정 파일 읽기, 승인 기본값 대체, 출처 기록. 열·산소·유동·조건표·지수·전이 계산식은 변경하지 않았다. 셰이더·레이어·render_order 불변.

## 서버 변경

serve_cfbt_building.py **+16 / -1행**. GET 상태/전층 목록, POST 제안/선택 적용, 로컬 접근·계산중 적용 금지. 별도 helper tools/lite_ai_fuel.py 추가(행 수는 diff-lines.txt). 127.0.0.1 바인딩 유지. 계산을 자동 시작하는 새 경로 없음.

## 증거

simulation/results/ui_C7_20261102/: api-unconfigured.png, proposal-1F.png, proposal-2F.png, applied-fuel-1F.png, applied-fuel-2F.png, ranking-before.png, ranking-after.png, browser-verification.json, unit-verification.json, frozen-verification.json. 테스트 전용 정정 사본 mock-applied-overrides.json.

Anthropic 호환 API 참고: https://platform.claude.com/docs/en/cli-sdks-libraries/libraries/openai-sdk . 계정별 모델 이용 가능성·실제 네트워크 호출은 미검증.
