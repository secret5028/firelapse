# 개발·배포 검증

Python 3.12와 Node.js, Chrome을 준비합니다. 루트 `requirements.txt`를 설치하고 JS 시험에는 Playwright와 AJV 8이 필요합니다.

```powershell
python -m pip install -r requirements.txt
npm install --no-save playwright ajv
python PyroCast/tools/test_all.py --output E:/FireLapse-tests
```

Node 패키지가 별도 위치에 있으면 `PYROCAST_PLAYWRIGHT`, `PYROCAST_AJV`에 모듈 경로를 지정할 수 있습니다. 장면 fixture는 `PYROCAST_BROWSER`로 Chrome 경로를 지정합니다. 일부 과거 화면 비교 스크립트는 Windows 기본 Chrome 경로를 사용합니다.

시험 도구는 `saved_results`의 압축된 입력·재생 자료를 `simulation/results`에 **없는 파일만** 복원합니다. 기존 결과는 덮어쓰지 않습니다. 시험 중 새 수치 시뮬레이션은 실행하지 않으며 솔버 호출 계약은 모의 호출로 검사합니다. 출력 디렉터리에 각 스크립트의 원문 로그와 `results.json`이 생성됩니다. `FAIL`, `PASS_WITH_SKIPS`, `PASS`를 구분하며 실패가 있으면 전체 명령의 종료 코드는 1입니다.

`--only simulation,risk_index_scene.test.mjs`처럼 필요한 항목만 재실행할 수 있습니다. 전체 시험은 simulation/tests와 app/tests의 Python·JS·PowerShell 시험 파일을 직렬 실행합니다. 테스트가 아닌 옛 측정용 보조 스크립트는 목록에 포함하지 않습니다.

## 별도 배포 검증

- 최신 ZIP을 새 폴더에 풀고 `Check-FireLapse.cmd`, `FireLapse.cmd`를 실행합니다.
- 7개 모델 선택, 강화 screening 200, 완도 calculation 200, 호텔·아이엔테크의 저장 결과 선택/층·실 일치/시간 이동을 검사합니다.
- 단독 HTML을 내보내고 서버를 종료한 뒤 file:// 재생과 외부 요청 0을 검사합니다.
- 코드 파일은 `source-files.json`과 Git 소스로 SHA256 대조합니다. 모든 번들 파일은 `files.sha256.json`, ZIP 자체는 `SHA256SUMS.txt`로 검증합니다.
- `tools/refresh_distribution.py`는 이전 검증 ZIP의 런타임·모델·계산 결과를 보존한 채 추적된 코드와 문서만 갱신합니다. `source-payload-verification.json`에 변경 목록과 보호 파일 변경 0을 기록합니다.

## SKIP의 의미

과거 화면 전후 픽셀 비교는 당시 overlay·캡처가 있어야 재현됩니다. 원본 CAD 증거·일부 옛 계산 중간값도 배포 대상이 아닙니다. 폐기된 간략 산소 모드 시험은 현재 CFAST 구현을 검증하지 않습니다. 이런 항목을 성공으로 세지 않습니다. 현재 회귀 시험의 장면 검증은 자체 fixture에서 실제 WebGL 렌더링과 자원 해제를 검사하며, 배포 검증은 최신 실제 앱 화면을 별도로 사용합니다.
