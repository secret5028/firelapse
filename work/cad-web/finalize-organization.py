from pathlib import Path
import json,csv,hashlib,sqlite3,urllib.request
root=Path('C:/Users/예방/Desktop/소방 크로키 업-로컬웹앱');work=root/'개발/work'
changes=[]
replacements={
 'C:/Users/예방/Downloads/도면 (1).pdf':(root/'원본도면/도면 (1).pdf').as_posix(),
 'C:/Users/예방/Downloads/도면.pdf':(root/'원본도면/도면.pdf').as_posix(),
 'C:/Users/예방/Downloads/_1층 평면도.dwg':(root/'data/08e5d677fdd94630b3c967a2222bbda6/f6c33d91b35a40e6a1653b93dbc4f98c.dwg').as_posix(),
 'C:/Users/예방/Downloads/강화역사박물관 소방도면.pdf':(root/'data/08e5d677fdd94630b3c967a2222bbda6/f6a9a150eced4327bf3414ee9aae1cda.pdf').as_posix()}
for rel in ['incoming-1/import.py','new-pdf/import.py','museum/add_1f.py','museum/render.py']:
 p=work/rel;s=p.read_text('utf8');new=s
 for old,target in replacements.items():new=new.replace(old,target)
 if new!=s:p.write_text(new,'utf8');changes.append(rel)
with (root/'문서/원본도면-목록.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f);w.writerow(['작업ID','원본파일명','보관위치','SHA256'])
 for p in (root/'data').glob('*/files.json'):
  for item in json.loads(p.read_text('utf8')):w.writerow([p.parent.name,item['name'],str(p.parent/item['stored']),item.get('sha256','')])
(root/'폴더 안내.txt').write_text('''소방 크로키 업 — 프로젝트 통합 폴더
정리일: 2026-09-10

실행: 이 폴더의 「소방 크로키 업.exe」

개발\\work     최신 개발 소스, 빌드 도구, 테스트, 건물별 판독 작업
개발\\outputs  이전 생성 산출물 및 빌드 보관본
소스           배포용 소스 사본 (최신 개발은 개발\\work 기준)
원본도면       다운로드 폴더에 있던 제공 PDF 원본
결과물         독립 실행 HTML 모델, 사용자 저장 초안
배포본         배포 ZIP과 이전 도면처리 프로그램
문서           기능 안내, 정리 기록, 원본 파일 목록, 다음 작업 계획
data           웹앱의 건물 원본·모델·저장 상태·작업 히스토리
_internal      실행에 필요한 라이브러리 — 현재 위치 유지
기존 검토 모델 / 오픈소스  기존 자료 유지

개발 명령은 이 폴더의 「개발」을 작업 위치로 실행합니다.
이전 Codex 작업 폴더의 work와 outputs는 여기를 가리키는 연결입니다.
실제 파일은 바탕화면의 이 폴더에만 있습니다.
원본 도면은 문서\\원본도면-목록.csv에서도 확인할 수 있습니다.
이전 산출물은 내용 확인 전 삭제하지 않고 보관했습니다.
''','utf8')
(root/'문서/다음 작업 계획.md').write_text('''# 다음 작업

- 우선 UI 정리: 사용자 PPT 시안 반영, 좌측 작업·상단 조작·우측 층/레이어 구성.
- 현재 새 점포 모델은 수동 판독 초안: 개구부 상세, 105개 헤드 전체, 11개 송수구별 배관 연결은 미확정.
- 수조·펌프는 등록된 건물에 기존 표시 기본값 적용. 현재 연결살수 전용 건물은 제외.
- 방화구획, 방화문·셔터 및 개폐 상태 추가.
- 지역/시각별 기압·풍향·풍속과 화재 사진 입력 확장.
- 내부/외부 개구부 선택과 장비 2~3종의 사양·대수·위치·방향으로 가벼운 배연 시나리오 비교.
- 배치 후보 계산: 개구부 치수, 중심 기준 좌우 거리, 벽면 이격거리, 송풍 방향·상하 각도를 표시.
- 배연 결과는 가정에 따른 검토 후보. 검증 전 실제 농도나 안전·최적 배치를 단정하지 않음.
- 4GB급 태블릿 성능 실측 필요.
''','utf8')
checks={}
for job in ['80fe8228ff8c4082bc8bf9f83771895b','1b8e6ebc75a74661b81047d7da38be68']:
 checks[job]={'result_exists':(root/'data'/job/'result.html').exists(),'state_valid':bool(json.loads((root/'data'/job/'state.json').read_text('utf8')))}
with sqlite3.connect(root/'data/history.sqlite') as c:checks['database']=c.execute('PRAGMA quick_check').fetchone()[0]
try:checks['http']=urllib.request.urlopen('http://127.0.0.1:8778/api/jobs',timeout=5).status
except Exception as e:checks['http']=str(e)
checks['updated_paths']=changes
(root/'문서/정리기록/2026-09-10-검증.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),'utf8')
print(json.dumps(checks,ensure_ascii=False))
