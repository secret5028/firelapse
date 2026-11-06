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

## r2 배포본 버전과 출처

아래 버전은 `v2026.11.06-r2` 실행 ZIP의 파일·메타데이터로 확인했습니다. 소스 clone은 Python·Node·수치 라이브러리 실행 파일을 포함하지 않습니다.

| 구성요소 | r2 버전 | 라이선스·출처 |
|---|---|---|
| CFAST | 7.7.7 | NIST 제작 부분은 미국 내 public domain. [NIST 소프트웨어 고지](https://www.nist.gov/copyrights-disclaimers) 및 [공식 프로젝트](https://github.com/firemodels/cfast)를 따르며 제3자 구성요소는 개별 고지 적용 |
| Three.js / OrbitControls | r160 | MIT; `PyroCast/cad-project/work/cad-web/local-resources/cad-assets/LICENSE` |
| NumPy | 2.5.4 | BSD-3-Clause; 번들 dist-info 라이선스 및 BLAS 별도 고지 |
| SciPy | 1.18.1 | BSD-3-Clause; 번들 dist-info 라이선스 및 포함 라이브러리 별도 고지 |
| Shapely | 2.2.0 | BSD-3-Clause; 포함 GEOS는 LGPL, dist-info의 원문 고지 참조 |
| Pillow | 13.0.0 | HPND 계열 Pillow 라이선스; 번들 dist-info 참조 |
| pako | 2.1.0 | MIT **및 Zlib**; `PyroCast/simulation/viewer/vendor/pako-LICENSE.txt`, [원문](https://github.com/nodeca/pako/tree/2.1.0) |
| Python | 3.12.14 | PSF License 및 포함 라이브러리 고지; 실행 ZIP `runtime/python/LICENSE.txt` |
| Node.js | 22.23.1 | MIT 및 포함 라이브러리 고지; 실행 ZIP `runtime/node/LICENSE` |

NIST 연료 참고 자료는 `work/nist-fuels/download-manifest.json`의 원문 URL·SHA256을 유지합니다. [SP 1021](https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication1021.pdf), [NCSTAR 1-5e](https://nvlpubs.nist.gov/nistpubs/Legacy/NCSTAR/ncstar1-5e.pdf), NCSTAR 1-5c 등을 참조합니다. 그림 디지타이징 CSV는 원문과 구분되는 프로젝트 가공 자료이며 공식 CFAST 재료 라이브러리로 간주하지 않습니다.

FireLapse 자체 라이선스는 미결정입니다. 이 고지는 프로젝트 전체에 MIT 또는 Apache-2.0을 부여하지 않습니다.
