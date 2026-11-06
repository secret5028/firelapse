# FireLapse 업로드 전 기능 검수 — 2026-11-06

판정: 확인한 운영 흐름 통과. 전체 시험 완전 통과·새 계산 검증 완료를 의미하지 않음.

## 발견 및 수정

1. 외부 데이터 폴더의 결과는 목록에 있지만 강화 재생 API가 옛 simulation/results 경로만 허용하여 재생을 거부하던 결함. 관리되는 두 결과 루트의 최종 playback.json만 허용하도록 수정. 건물 해시 확인과 경로 이탈 거부 유지. AI 조회 도구의 사례·MC 집계 검색도 두 루트를 읽도록 수정. 로컬 커밋 `37c1ca5`.
2. 호텔 5F R16 MC S08, 34:50에서 FGI -0 및 상층 산소 -0.0% 표시 재현. 반올림한 문자열이 0일 때 부호만 정리. 실제 음수·원시 결과·물리 계산은 변경하지 않음. 로컬 커밋 `7c9ff39`.

## 시험 결과

- app JavaScript 비브라우저 시험: 40개 파일 최종 통과. 처음 실패한 8개 중 5개는 AJV/Three/건물 경로 등 실행 인자 보완으로 통과, 3개는 이미 승인된 기본값·전층 차량 표시와 독립 fixture에 맞게 시험 정비.
- app Python 시험: 30개 파일 최종 통과. unittest 집계 179건 및 별도 assertion 스크립트. 실행 증거·Stage5·UI attention의 시험 환경 경로를 보정. 저장소 회귀시험은 12→14건.
- 추가 simulation 시험: CAD 호 자동문 15, CAD 자동보정 8, 공리 11, 연소 표시 3, 개구부 조건 9건 통과(46건).
- 다음 simulation 시험 3파일은 실패 상태로 남김. 계산식을 과거 시험에 맞춰 되돌리지 않았음:
  - test_lite_room_oxygen.py: 5개 오류. 폐기된 oxygen_inventory_mode=True를 호출하며 현재 adapter가 명시적으로 거부.
  - test_lite_montecarlo.py: 7개 중 6통과/1오류. 현재 3현상 집계에 없는 rollover 키를 기대.
  - test_lite_visualization.py: 수집 단계 오류 1개. 제거된 visualization.states를 import. 이 파일의 나머지 시험은 실행되지 않았음.
- 전체 simulation/tests 및 브라우저 자동화 스크립트 전수 실행은 하지 않았음. 실제 UI는 아래 범위에서 직접 검수.

## 운영·화면 확인

- 등록된 7개 건물의 목록 페이지·building.json 및 존재하는 5개 운영 페이지 모두 HTTP 200. 스캔 2건은 simulation_enabled=false 유지. 완도는 전용 사례 열람 경로 보존.
- 호텔 결과 클릭 → 9F R15 객실-9, 이후 5F R16 객실-10 MC S08로 층·실·결과 탭 동기화 확인.
- 9F 결과를 보고 있는 중 7F로 층 변경 → 결과 탭 유지, 실 선택 요청 및 모든 미평가 값 — 확인.
- 호텔 새로고침 → 5F R16, MC S08, 시각2090초 복원. -0 표시 제거 확인.
- 표시 탭 24개 switch의 checked 값 반전·복원을 각각 확인. UI 오류 로그 0.
- 아이엔테크 1F R3 조립실 MC S04 선택·1800초 재생 확인. UI 오류 로그 0.
- 375px 아이엔테크 화면 document/body scrollWidth=375. 가로 넘침 없음. 임시 viewport 복원.
- 외부 저장 경로 HTTP 회귀: 임시 데이터 루트와 별도8897 서버에서 기존 결과 복사본을 카탈로그로 발견하고 재생 HTTP200/complete=true/3600초 확인. solver 실행0회. 임시 서버 종료.
- 운영8780 및8841은 계산 idle·AI 미연결 확인 후 수정 반영 재시작. 기존 결과·계산 입력 삭제나 재계산 없음.

## HTML 내보내기

- 운영 버튼으로 호텔·아이엔테크 HTML 실제 다운로드 성공.
- 호텔 4,286,704 bytes / 아이엔테크 3,959,768 bytes.
- 압축 봉투 검사: 각각 75개 모듈, state12키(camera/route/layers/risk 등), 시각2090초/1800초, 네트워크 차단 CSP 포함.
- 단독 HTML file:// 실행은 도구의 URL 보안 정책으로 차단됨. 우회하지 않았으며 이번 검수에서 단독 HTML의 실제 브라우저 재생은 미확인. 내보내기 단위시험은 통과.

## 미검증·배포 상태

- 새 CFAST/간략 실계산, 실제 외부 AI 연결·CAD 업로드 전체 파이프라인은 이번 검수에서 실행하지 않음. 관련 단위시험은 모의 실행 포함이며 실환경 계산 완료 증거와 구분.
- 계산 과정 정리의 실제 운영 데이터 삭제는 하지 않음. 임시 fixture에서 보호·경로 이탈·실행 중 제외·정리 후 MC 순위 보존 검사 통과.
- GitHub push 및 실행 ZIP 재생성은 하지 않음. 기존 공개 릴리스는 이번 수정 전 버전.
- 프로그램 동작 확인과 물리 모델의 타당성 검증은 별개이며 이 보고서는 물리 모델 인증이 아님.

## 근거 파일

js-final.json, python-final.json: 초기/최종 실행 상태와 로그명.
models-http.json, external-http.json, export-checks.json: HTTP 및 내보내기 검사.
hotel-reviewed.png, ientech-375.png: 실제 운영 화면.
구형 simulation 시험 실패 로그3개 포함. 전체 개별 실행 로그는 검수 scratch/final-review에 보존.
