# 실행과 이식 범위

## 저장된 결과

`python preview.py`는 Python 표준 라이브러리만 사용합니다. 서버는 127.0.0.1에만 바인딩합니다. 저장 결과 재생과 CFAST 재계산은 구분됩니다.

## CAD 웹앱 개발

Windows + Python 가상환경을 권장합니다:

```sh
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python work/cad-web/local_app.py
```

기본 포트는 8778이며 기존 앱이 실행 중이면 먼저 종료하거나 별도 PC에서 실행합니다. 새로운 작업 데이터는 `work/cad-web/local-data`에 생성됩니다. 이 체크포인트는 기존 앱의 작업 DB를 복사하지 않습니다. 저장 모델 보기에는 preview를 사용하세요.

DWG를 새로 처리하려면 별도로 LibreDWG의 Windows `dwg2dxf.exe`와 필요한 DLL을 `work/cad-web/local-resources/cad-tools`에 설치해야 합니다. 기존 PC의 바이너리는 이 체크포인트에서 제외했습니다. DXF 표본은 `sample-input`에 보존했습니다. https://github.com/LibreDWG/libredwg/releases 및 동봉 README를 참고하세요.

requirements는 소스 import에 근거한 의존성 목록이며 완전히 고정·검증된 새 환경 lock 파일은 아닙니다. 깨끗한 집 PC에서 CAD 신규 업로드부터의 전체 실행은 아직 확인하지 않았습니다. 선택적 LLM 기능의 API 키는 환경변수로 별도 설정하며 저장소에 넣지 않습니다.

## 뷰어 재생성

```sh
python work/restore_cad_ui.py rebuilt-viewer
```

기존 PC 바탕화면의 legacy JS 의존성을 `work/legacy`로 복사하여 연결했습니다. 기존 설치된 model.html은 `snapshot/model.html`, 재생성 대상은 `work/cad-web/cad_engine/integrated_viewer.html`입니다.

## 현재 CFAST 시나리오

Windows용 기존 CFAST 7.7.7 native 바이너리를 실행합니다. 30분 재계산은 오래 걸릴 수 있습니다:

```sh
python run_current.py --build-only
python run_current.py
```

`--build-only`는 native 입력 생성까지만 합니다. 출력은 `outputs/home-run`에 생성하며 보관된 v30 원시 결과를 덮어쓰지 않습니다. `--force`는 캐시를 사용하지 않고 재계산합니다. Shapely가 필요합니다. 기존 `work/run_cfast_current.ps1`과 과거 설치/검증 스크립트에는 당시 PC 경로가 남아 있으므로 무작정 실행하지 마세요. 이식된 기본 진입점은 루트 `run_current.py`입니다.

이식 변경은 building.json 위치와 legacy JS 위치뿐입니다. 기존 원문은 `original-machine`에 보존했습니다. CFAST native 방정식·설정·화원·높이·착화 조건은 바꾸지 않았습니다. 현재 입력 생성의 보존 결과 대조는 `CHECKPOINT-VALIDATION.json`에 기록합니다.

## 제외한 파일

- Python 설치본·cad-deps·node_modules·캐시·임시 다운로드
- 기존 설치 EXE와 중복 백업, CEdit GUI의 별도 상용 구성요소
- 계정/인증 설정·API 키·작업 DB
- 옛 버전의 모든 원시 계산과 전체 도면 렌더링 중복본

자체 소스의 과거 보조 스크립트는 작업 이력 확인용으로 함께 남겼습니다. 최신 여부는 CHECKPOINT와 복구 기록을 우선합니다. 외부 프로젝트 자료는 원래 권리와 라이선스를 따르며 이 저장소 전체를 임의로 하나의 오픈소스 라이선스로 선언하지 않았습니다.

공식 CFAST 소스/배포: https://github.com/firemodels/cfast
Three.js 라이선스: `work/cad-web/local-resources/cad-assets/LICENSE`
