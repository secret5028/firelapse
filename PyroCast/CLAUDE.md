# FireLapse 작업 진입점

먼저 `specs/Claude-review-handoff-20261105.md`를 읽으세요.
현재 앱은 이 폴더의 `app/web`, `tools`, `simulation/viewer`, `simulation/pyrocast_lite`입니다.
저장소 상위 폴더와 오래된 README의 10월 화면은 보존된 체크포인트이며 현재 운영 UI가 아닙니다.

- 최신 사용자 지시 우선. 재현 → 최소 수정 → 관련 시험/운영 UI 검증 → 항목별 1커밋.
- 기존 도면·건물·결과 보존. 키/로컬 인증 설정 커밋 금지.
- 계산은 직렬. 실행 중인 작업을 확인하고 서버·엔진을 함부로 재시작/교체하지 마세요.
- 물리 기준을 결과에 맞춰 변경하지 말고, 수치 보정은 근거·전후 수치로 확인하세요.
- `simulation/viewer/overlay.js`는 `python tools/build_ui_bundle.py`로 생성합니다.
- 실제 API/전체 계산 검증과 모의·단위 시험을 구분하세요.
