# AI 가연물 배치

`ai.example.json`을 `ai.json`으로 복사하고 `base_url`, `model`, `api_key_env`를 설정합니다. JSON 주석 대신 `_comment`와 `_vllm_example`을 사용합니다. vLLM은 예시 객체의 세 필드를 최상위로 복사합니다. 실제 API 키는 서버 프로세스의 환경변수에만 설정하고 서버를 재시작합니다. `ai.json`에는 키 값 필드를 넣을 수 없으며 Git에서 제외합니다.

서버는 `base_url + /chat/completions`로 OpenAI 호환 요청을 보냅니다. Anthropic 호환 경로는 [공식 문서](https://platform.claude.com/docs/en/cli-sdks-libraries/libraries/openai-sdk)를 참조했습니다. 예시 모델의 계정 사용 가능 여부·실제 API 호출은 이번 검증 범위에서 미검증입니다. 원격 HTTPS와 로컬 HTTP만 허용하며 리다이렉트는 따르지 않습니다.

- `GET /cfbt/lite/ai/fuel`: 설정 여부·전층 실 목록·표 클래스. 키·설정 원문 반환 없음.
- `POST /cfbt/lite/ai/fuel`: `{message, history:[{role,content}]}`. 대화는 브라우저 세션 메모리에만 유지합니다. 서버 시스템 메시지는 현재 건물 실 ID·CAD 라벨·면적·용도 및 표 클래스로 만듭니다.
- 응답은 순수 JSON 배열만 허용합니다. 설명·코드펜스·임의 클래스·실 ID·중복 ID는 거부하고 한 번만 재요청합니다. 서버는 수치 생성을 허용하지 않고 표에서 하중·HRRPUA를 읽습니다.
- 제안은 적용되지 않습니다. 표의 체크된 행을 적용하면 `POST /cfbt/lite/fuel-overrides`가 서버 메모리의 제안을 검증하여 `simulation/config/fuel-overrides.json`에 저장합니다. 제안은 30분 만료·1회 적용·동일 입력 조건입니다.
- 현재 ①·② 입력은 3F입니다. 전층 용도표와 1F·2F 정정 저장은 지원하지만, 그 층의 시뮬레이션 입력 확장은 포함하지 않습니다. 3F 정정은 ① 점수·②/MC 화원 입력에 우선 적용합니다. ②는 자동 실행하지 않고 재실행 필요를 표시합니다.
- 타이어 전용 클래스는 없습니다. warehouse를 제안하면 일반 창고 대용임을 근거로 표시하며, 타이어 실측 연료하중으로 해석하지 않습니다.
- 미설정 시 “API 미설정 — config/ai.json”. 내보낸 단독 HTML에서는 “보기 전용”. 운영 코드에 모의 응답 분기는 없습니다. `app/tests/ai_fuel_fixture.py`는 별도 포트·별도 정정 파일만 쓰는 UI 검증용입니다.
