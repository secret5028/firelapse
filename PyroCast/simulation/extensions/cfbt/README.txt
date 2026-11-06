FireLapse · CFAST 확장 코드

이 폴더는 FireLapse가 추가한 반응·게이트·진단 코드와 연결 정의입니다.
NIST CFAST 원본과 구분해 관리하며, 확장 실행을 순정 CFAST라고 표시하지
않습니다.

fortran/ : 추가 구현
hooks.py : 고정된 원본에 연결할 위치와 변경 내용

외부 원본: ../../vendor/cfast-7.7.7/Source
생성 입력: ../../build/generated/cfbt (직접 수정하지 않음)
변경 경계: ../../SOURCE_BOUNDARIES.txt

핵심 변경은 이 폴더의 확장 또는 pyrocast_cfbt 모듈에서 수행합니다.
원본이나 연결점을 변경하면 기준 엔진과 확장 비교를 확인해야 합니다.
라이선스·출처 고지는 각 원본을 따릅니다.

첫 공개 배포의 실행과 결과 해석은 프로젝트 루트 README.md 및
simulation/README.txt를 참고하세요.
