from pathlib import Path
import shutil,zipfile,json,importlib.metadata as md
root=Path('outputs/소방공간뷰-로컬웹앱');root.mkdir(exist_ok=True)
source=root/'소스';source.mkdir(exist_ok=True)
for n in ['local_app.py','file_tool.py','local_app.spec','prepare_local.py','local_index.html']:shutil.copyfile(Path('work')/n,source/n)
for n in ['folder_review.html','three.core.js','three.module.js']:shutil.copyfile(Path('work/local-resources')/n,source/n)
lic=root/'오픈소스';lic.mkdir(exist_ok=True)
shutil.copyfile('work/libredwg-0.14-source.zip',lic/'LibreDWG-0.14-source.zip')
with zipfile.ZipFile('work/libredwg-0.14-source.zip') as z:
 for n in z.namelist():
  if n.endswith('/COPYING'): (lic/'LibreDWG-COPYING.txt').write_bytes(z.read(n));break
for package in ['ezdxf','numpy','Pillow','pypdfium2','pypdfium2_raw']:
 try:
  d=md.distribution(package)
  for f in d.files or []:
   if any(k in str(f).lower() for k in ['license','copying']) and d.locate_file(f).is_file():
    target=lic/(package+'-'+Path(str(f)).name);shutil.copyfile(d.locate_file(f),target)
 except Exception:pass
samples=root/'기존 검토 모델';samples.mkdir(exist_ok=True)
for n in ['소방공간뷰-강화산업단지-통합.html','소방공간뷰-두산위브-CAD검토.html']:
 shutil.copyfile(Path('outputs')/n,samples/n)
(root/'사용안내.txt').write_text('''소방공간뷰 · 로컬 웹앱

1. 소방공간뷰.exe를 더블클릭합니다. Python이나 Node.js 설치가 필요 없습니다.
2. 브라우저에서 건물 이름과 여러 도면 파일을 선택합니다.
3. 히스토리의 작업 열기를 누릅니다.
4. CAD는 레이어 분류를 확인하고 분류 적용 → 층 도면으로 지정 → 3D 검토를 누릅니다.
   PDF·이미지는 치수를 지정하고 벽·문·창을 보정한 후 같은 3D 화면을 사용합니다.
5. 보정 내용은 10초마다 로컬에 저장됩니다. 작업 저장으로 보정 JSON도 보관할 수 있습니다.
   HTML 저장 버튼으로 보정된 결과를 단독 HTML로 내보냅니다.

지원: DWG, DXF, PDF, JPG/JPEG, PNG, TIFF, BMP. 최대 50파일 / 파일당 50MB / 300페이지.
DWG는 포함된 LibreDWG로 로컬 변환합니다. 특수 객체·외부 참조·일부 DWG 버전은 완전하게 읽히지 않을 수 있습니다.
CAD의 단위가 없으면 mm 임시값을 사용합니다. 층고 기본값 3.6m와 함께 원본 치수로 확인하세요.
같은 동·층의 반복 도면은 하나만 기준 도면으로 지정합니다. 다른 건물은 새 작업으로 만드세요.

저장 위치: 이 폴더의 data. 폴더 전체를 복사하면 히스토리와 원본이 함께 이동합니다.
인터넷 연결·API 키·LLM 호출 없음. 현재 실행 주소는 이 PC 전용 http://127.0.0.1:8778 입니다.
태블릿용 공용 서버와 선택적 LLM 연결은 이 버전에 포함되지 않았습니다.

현재 범위: 입력·히스토리·공통 검토/3D 초안. 모든 새 도면의 실 구획·계단·화점·최단 경로·수관 계산 자동 생성은 아직 연결되지 않았습니다.
기존 검토 모델 폴더에는 이전의 상세 기능을 유지한 강화산업단지·두산위브 결과물을 별도로 보관했습니다.
새 도면이 이전 샘플과 동일한 완성도로 자동 생성되는 배포 완성판은 아닙니다.

종료: 실행 종료.html을 열어 종료 버튼을 누릅니다. 브라우저 창만 닫으면 로컬 서버는 계속 실행됩니다.
배포 시 _internal과 오픈소스 폴더를 포함해 폴더 전체를 전달하세요. 소스도 함께 포함했습니다.
''','utf-8')
(root/'실행 종료.html').write_text('''<!doctype html><meta charset="utf-8"><title>소방공간뷰 종료</title><p>아래 링크에서 실행 중인 앱을 열 수 있습니다.</p><a href="http://127.0.0.1:8778/">소방공간뷰 열기</a><p>앱 화면의 실행 종료 버튼을 사용하세요.</p>''','utf-8')
print(root)
