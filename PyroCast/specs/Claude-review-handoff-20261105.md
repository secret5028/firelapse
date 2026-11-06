# FireLapse 전체 검토·수정 인계 — 2026-11-05

## 시작점과 현재 범위

- 제품명: **FireLapse / -compartment fire timeline-**. 저장소 이름은 기존 `secret5028/3d_fire` 유지.
- 작업 브랜치: `codex/ui-refactor-layer-building`. 최신 사용자 요청은 전체 앱 오류를 먼저 검토·수정한 후 GitHub에 업로드하고 Claude가 후속 검토·수정할 수 있게 준비하는 것.
- 저장소 루트의 10월 CAD 체크포인트와 `SESSION_HANDOFF.txt`의 오래된 화면 설명은 역사 기록이다. 현재 앱 소스는 저장소의 **PyroCast/** 아래에 있다. 이 문서와 최신 코드/사용자 지시를 우선한다.
- 이 문서는 Claude 검토 요청 준비물이다. Claude가 실제 검토했다고 표시하지 않는다.

## 로컬 환경과 실행

운영 루트: `C:\Users\<user>\Documents\ChatGPT\PyroCast`

Git 체크아웃: 운영 루트 아래 `simulation\results\github-publish-20261026\PyroCast`.
두 폴더는 자동 동기화되지 않는다. 로컬 운영 파일에서 수정했다면 검증 후 변경 파일만 Git 체크아웃에 반영한다. 과거 결과·사용자 설정을 통째로 덮어쓰지 않는다.

이 PC의 실행 예:

```powershell
Set-Location 'C:\Users\<user>\Documents\ChatGPT\PyroCast'
& 'C:\Users\<user>\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -X utf8 tools/serve_model_library.py --port 8841
```

새 PC에서는 Python 환경과 `requirements-viewer.txt`를 준비하고 프로젝트 작업 디렉터리에서 `python tools/serve_model_library.py --port 8841`을 사용한다. 이식 전체 동작은 별도 검증 필요. 기존 프로세스와 포트가 있는 상태에서 서버를 중복 실행하지 않는다.

| 주소 | 용도 |
| --- | --- |
| `http://127.0.0.1:8780/model.html` | 강화 운영 화면. 별도 재생 서버 |
| `http://127.0.0.1:8841/models/new` | 새 DWG/DXF 업로드·자동보정 |
| `http://127.0.0.1:8842/model.html` | 파크마린호텔 운영 화면 |
| `http://127.0.0.1:8843/model.html` | 견본주택 운영 화면 |
| `http://127.0.0.1:8844/model.html` | 아이엔테크놀로지 운영 화면 |
| `http://127.0.0.1:8832/data/wando-coldstore/model.html` | 완도 전용 서버 화면. 위 모델 서버와 별개 |

- 모델 서버 하나가 8841 및 등록된 8842/8843/8844를 제공한다. 새 CAD는 사용 가능한 운영 포트를 자동 등록한다.
- CAD 변환기 경로는 `config/cad-import.example.json`을 참고해 **로컬 전용** `config/cad-import.local.json`에 설정한다. DWG 변환기·원본 CAD·전 계산 결과는 Git 저장소만으로 전부 제공되지 않는다.
- 실제 AI 키는 앱의 AI 연결 또는 서버 환경변수로만 제공한다. `config/ai.json`, 키, 세션 인증 정보는 커밋하지 않는다. 예시 모델명은 계정에서 사용 가능한 모델인지 확인해야 한다.
- 저장소의 강화 건물 경로는 운영 폴더의 중첩 경로가 포함되지만 `tools/model_library.py:model_path()`에 `cad-project/building.json` 대체 경로가 있다.

## 전체 흐름과 코드 지도

| 기능 | 주 진입점 |
| --- | --- |
| 새 CAD → 원본 보존 → 층 범위 검사 | `app/model-library/cad-new.*`, `tools/cad_import.py` |
| 반복 기둥 정렬·문 호·고립 영역 공리·AI 후보 검토 | `tools/cad_completion.py`, `cad_model_axioms.py`, `cad_autocorrect.py`, `prepare_building_graph.py`, `config/cad-completion.json` |
| 모델 등록·운영 서버·사례 목록·계산 전 화면 | `tools/model_library.py`, `model_operation.py`, `serve_model_library.py` |
| 가연물 기본/실별 설정·점수·대표 화점 | `app/web/panels/fuel_settings.js`, `explore.js`, `tools/lite_fuel_settings.py`, `model_simulation.py` |
| MC·최악 급기 확정·간략/순정 CFAST | `tools/model_mc.py`, `fixed_calculation.py`, `run_lite_mc.py` |
| 상태·결과 선택·패널·호스트 | `app/web/controller.js`, `state/`, `adapters/`, `panels/`, `scene/` |
| 건물·개구부·코어·연기/불·위험·선택·수관 | `app/web/layers/`, `app/web/route/` |
| 실감 셰이더 | `simulation/viewer/legacy_real_view.js`, `legacy_real_bridge.js` |
| 번들 | `python tools/build_ui_bundle.py` → `simulation/viewer/overlay.js` (생성물 직접 수정 금지) |
| AI 연결/대화·도구/브리핑 | `tools/ai_connection.py`, `lite_ai_tools.py`, `lite_ai_briefing.py`, `app/web/panels/assistant.js` |
| 물리 엔진·수치 적분 | `simulation/pyrocast_lite/{adapter,core,numerics,runner}.py` |

사용자 흐름: 건물 선택 → 1단계 층 선택 → 2단계 가연물 → 3단계 후보 상위 5개·화점 선택 → MC 급기 탐색 → 최악 개폐 상태 적용 → 간략/순정 CFAST 선택·계산 → 결과 목록 클릭·재생.
MC는 엔진 이름이 아니라 개구부 조합 탐색이다. 현재 보는 층/실과 계산 사례의 층/화점은 별도로 관리한다.

## 유지할 결정

1. CAD만 신규 생성 입력으로 사용. 스캔 경로는 미래용 보존, 시뮬레이션 금지.
2. 층 누락·심각한 형상 결측은 생성 차단. 확실한 보정은 자동, AI 판단/애매한 연결은 추정 표시. 근거 없이 층·문·연결을 만들지 않는다.
3. 수직 연결은 근거가 있는 계단·승강기만. 현재 새 CAD의 계산 가능 표시는 **층별** 로더 통과이며, 전층 연기 전파 검증이 아니다.
4. FO·FGI·BD 3개 지수. 롤오버는 FGI 부속 상태. 미평가는 `—`, 실제 계산된 0과 구분한다. 발생 확률로 표현하지 않는다.
5. 다중 셀 방 합성 시계열은 `null/aggregation:none`; 셀 원값 보존. 임의 평균 금지.
6. 벽 투시·얇은 실제 모서리·문창 사각 표시 유지. 문/창 위아래 벽은 보존한다. 수관은 흰색·얇게, 실제 차량/구조물과 깊이 관계 유지.
7. 결과 선택 시 해당 층·화점·결과 탭을 함께 선택하고 현재 결과만 강조. 새로고침 뒤 결과와 시각 복원. 오래된 결과를 새 입력의 결과로 표시하지 않는다.
8. AI는 숫자/실명/시각을 만들어 넣지 않는다. 가연물 값은 출처 있는 표를 사용. API 미연결을 실제 AI 완료로 표현하지 않는다.
9. 모든 계산 직렬, 표본당 1200초 예산, 동일 실패 자동 반복 금지. 기존 결과 보존. 완도는 전용 순정 CFAST 입력/사례 유지.
10. 작은 값의 수치 불안정에는 사용자가 하한값 적용을 허용했다. **단위·허용오차·재현 근거와 전후 비교가 필요**하다. 물리 값을 임의로 높여 지수/성공 결과를 맞추지 않는다. 유효한 0과 NaN/미평가를 구분한다.

## 우선 검토할 미해결 항목

| 우선 | 항목 | 확인된 사실 / 필요한 검증 |
| --- | --- | --- |
| 완료 | 아이엔테크놀로지 MC 수치 실패 | 누적 Jacobian 차분 계수 overflow 재현·수정. 기존 실패 2표본과 동일 입력 MC10 모두 완주(218.0283초). `reviews/mc-export-fix-20261105/numerical-report.md` 참조. |
| 완료 | 호텔 10F 동일 계열 수치 실패 | 기존 입력 그대로 3600 s 완주. 적분 904.0708 s, 전체 906.9183 s, 연소 2실·최초 FO 230 s. 결과 경로: `simulation/results/mc-numerical-fix-20261105/hotel-10F/status.json`. 긴 적분 시간 원인 분석은 별도이며 결과에 맞춘 조정 없음. |
| 2 | 입력 불합격 3층 | 강화 B1/PH, 호텔 B1. 작은 실과 넓은 개구부의 CAD 소속/분류 검토. 단순히 문 폭을 잘라 통과시키지 말 것. |
| 2 | 새 CAD의 운영 기능 차이 | HTML 내보내기는 복구하여 아이엔테크놀로지·호텔 실제 저장 및 API 없는 재생 검증 완료. AI 대화 등 나머지 capability 일관성은 별도 점검. |
| 2 | API AI 실검증 | 키 미연결. 원본 근거 후보 허용목록·거부·기하 검증은 시험했지만 실제 API와 새 원본 업로드부터 전체 과정은 별도 확인 필요. 모의 분기는 시험 코드에만. |
| 3 | UI 미감 | 설정 단계 박스/간격, 결과 목록 3행, 글자 대비, 축약된 결과 패널, 모델 점검 위치 표시, 좁은 화면/터치. 이미 삭제 요청한 설명/HUD/중복 메뉴를 재도입하지 말 것. |

수관 누락은 이번 사전 검토에서 재현·수정: 중복 경첩의 첫/마지막 좌표가 같아 법선 계산이 NaN이 됨. 서로 다른 경첩 사이 실제 span으로 변경, 원본/물리/연결망은 불변. 1F R3 경로 56.3439566m·4본, 실제 운영 캡처 포함.

## 검증 자료와 수정 절차

- 최근 CAD 검증: `reviews/cad-auto-pipeline-20261105/report.txt` (관련 시험 29건).
- 새 모델 계산 연결: `reviews/cad-simulation-connect-20261105/report.txt`.
- 업로드 전 내부 점검: `reviews/prepublish-review-20261105/` (시험 결과·수관 캡처·수치 진단).
- 야간 전 건물 계산: `reviews/overnight-20261104/FINAL.md`.
- 로컬 MC 실패 사례: `simulation/results/lite_mc_jobs/models/cad-aabf1346d0e54c94b45ad7d7db7137d4/mc-1793861778317776500-40960b77` (원본 결과 Git 미포함).

먼저 읽기 전용으로 재현과 우선순위를 보고한 뒤, 현재 사용자 승인 범위 안의 버그를 항목별 1커밋으로 수정한다. 서버 재시작 전에 실행 중인 계산과 CAD 작업을 확인한다. 다른 에이전트와 같은 파일/엔진을 동시에 수정하지 않는다. 엔진 실행 중에는 물리/수치 소스 변경을 피하고 입력·엔진 SHA를 보존한다.

회귀 최소 목록:

- 새 CAD: 누락 층 차단, 보정 후 재검사, 추정 표시, 모델 선택 목록/운영 주소, 계산 전 미평가.
- 설정: 층 선택 전 비활성, 가연물 변경→후보 순위, 개별 실 설정 유지, 후보 선택→3D 선택.
- 계산: 중복 실행 차단, 실패/부분 완료 구분, 완료 사례만 게시, 엔진 종류 구분.
- 결과: 목록 클릭→정확한 층/실/사례, 새로고침 유지, 시간 이동, 미평가 `—`.
- 경로: 새 CAD/호텔/강화, 중복 경첩·단일문·미닫이문, 차량 이동·회전·지면 제한, 선택 층 아래 경로, 미확인 연결을 가짜로 잇지 않음.
- 화면: 벽/문/창/코어/연기/불/선택 토글, 긴 이름/작은 패널, 모바일, 콘솔 오류.

검증하지 않은 것은 미검증으로 적는다. 통과한 작은 시험을 전체 물리 타당성이나 모든 CAD 범용성 확보로 확대하지 않는다. 후속 push/배포는 해당 세션의 사용자 승인 범위를 확인한다.
