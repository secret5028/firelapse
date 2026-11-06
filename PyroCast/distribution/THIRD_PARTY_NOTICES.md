# 타사 구성요소 안내

FireLapse 배포본은 다음 실행 환경과 라이브러리를 함께 제공합니다. 각 구성요소의 저작권·라이선스 고지는 포함된 원문을 따릅니다. FireLapse 자체에 새 오픈소스 라이선스를 임의 부여하지 않습니다.

| 구성요소 | 포함 위치 / 고지 |
|---|---|
| Python 3.12 | `runtime/python/LICENSE.txt` |
| Node.js | `runtime/node/LICENSE` |
| NumPy 및 포함 BLAS 라이브러리 | `app/simulation/plot_deps/numpy-*.dist-info/` 및 NumPy 라이선스 |
| SciPy 및 포함 BLAS 라이브러리 | `app/simulation/deps/scipy-*.dist-info/` |
| Shapely / GEOS | `app/simulation/deps/shapely-*.dist-info/` |
| Pillow | `app/simulation/plot_deps/pillow-*.dist-info/`의 라이선스 파일 |
| Three.js / OrbitControls | `app/cad-project/work/cad-web/local-resources/cad-assets/`의 소스 및 고지 |
| CFAST 7.7.7 기준 소스 / 빌드 | `app/simulation/vendor/cfast-7.7.7/Source/cfast.f90`, `sources.json`, `app/simulation/build/baseline/build.json` |

CFAST 원본과 FireLapse의 간략 엔진·추가 후처리는 구분됩니다. 기준 CFAST 실행 파일과 추가 엔진을 같은 이름으로 표시하지 않습니다. CFAST는 NIST의 공식 출처를 보존한 버전이며, 이 배포 자체가 NIST의 인증·검증 또는 보증을 뜻하지 않습니다.

DWG 변환기와 별도 CAD 추출 도구는 이번 실행 패키지에 포함하지 않습니다. 해당 도구는 사용자가 별도 설치하고 그 라이선스를 확인해야 합니다. 7개 기존 모델과 저장 결과 열람에는 필요하지 않습니다.

CFAST Windows 빌드에 포함된 MinGW-w64 런타임 고지는 `licenses/MinGW-w64-runtime.txt`를 참고하세요.
