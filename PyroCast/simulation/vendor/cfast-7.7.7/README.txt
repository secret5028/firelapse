공식 CFAST-7.7.7 원본 보관 구역.

Source/와sources.json은 일반 기능 개발 중 변경하지 않는다.
sources.json의 URL/파일SHA256과 목록 자체의 고정SHA256으로 검증한다.
추가 기능은 simulation/extensions/cfbt/와 simulation/pyrocast_cfbt/에서 작성한다.
전체 모듈의 수정 사본은 build/generated/cfbt/에만 자동 생성한다.

원본은 tools/fetch_cfast.py로 누락 파일만 복원한다. 수정된 원본을 자동 덮어쓰지 않는다.
공식 출처: https://github.com/firemodels/cfast/tree/CFAST-7.7.7/Source/CFAST
