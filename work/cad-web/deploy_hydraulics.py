from pathlib import Path
import shutil,hashlib,json,urllib.request,time
root=Path.cwd().resolve();build=root/'work/hydraulic-dist/소방 크로키 업-로컬웹앱'
targets=[root/'outputs/소방 크로키 업-로컬웹앱',Path('C:/Users/<user>/Desktop/소방 크로키 업-로컬웹앱')]
def hashes(folder):
 return {str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file()} if folder.exists() else {}
for target in targets:
 target=target.resolve()
 if target not in [root/'outputs/소방 크로키 업-로컬웹앱',Path('C:/Users/<user>/Desktop/소방 크로키 업-로컬웹앱')]:raise RuntimeError('Unexpected destination')
 before=hashes(target/'data');target.mkdir(exist_ok=True)
 shutil.copy2(build/'소방 크로키 업.exe',target/'소방 크로키 업.exe')
 shutil.copytree(build/'_internal',target/'_internal',dirs_exist_ok=True)
 (target/'소스').mkdir(exist_ok=True)
 for name in ['local_app.py','local_index.html','file_tool.py','folder_review.html','prepare_local.py','local_app.spec','hydraulic_embed.py','hydraulic-core.js','hydraulic-ui.js','hydraulic-view.js']:
  shutil.copy2(root/'work'/name,target/'소스'/name)
 (target/'기존 검토 모델').mkdir(exist_ok=True)
 for name in ['소방공간뷰-두산위브-CAD검토.html','소방공간뷰-강화산업단지-통합.html']:
  shutil.copy2(root/'outputs'/name,target/'기존 검토 모델'/name)
 for name in ['소방-송수구-수리계산-기능예제.html','송수구-계통-기능안내.md']:
  shutil.copy2(root/'outputs'/name,target/name)
 assert hashes(target/'data')==before,'History files changed during deployment'
 assert (target/'_internal/hydraulic-ui.js').read_bytes()==(root/'work/hydraulic-ui.js').read_bytes()
 print('Updated:',target,'· history files preserved:',len(before))
for name in ['소방공간뷰-두산위브-CAD검토.html','소방공간뷰-강화산업단지-통합.html']:
 dest=Path('C:/Users/<user>/Desktop')/name
 if dest.exists():shutil.copy2(root/'outputs'/name,dest)
