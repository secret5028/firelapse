from pathlib import Path
import json,hashlib,shutil
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'outputs/CAD-가연물묶음-v30'
APP=Path('C:/Users/<user>/Desktop/소방 크로키 업-로컬웹앱')
JOB=APP/'data/d018b4bb75da4475b1fd75447603c1a0/cad-output'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
data=json.loads((OUT/'ceiling/cfast-demo.json').read_text('utf8'))
assert data['duration']==1800 and data['fuel_inventory']['unit_count']==20
assert data['building_sha256']==sha(JOB/'building.json')
assert json.loads((OUT/'검증결과.json').read_text('utf8'))['ceiling']['duration']==1800
oldmodel=(JOB/'model.html').read_text('utf8');newmodel=(OUT/'model.html').read_text('utf8')
marker='// Coupled CFAST results on the original CAD scene.'
assert oldmodel.split(marker)[0]==newmodel.split(marker)[0], 'Unexpected legacy UI change'
back=OUT/'backup/app';back.mkdir(parents=True,exist_ok=True)
files=[(OUT/'model.html',JOB/'model.html','model.html'),(OUT/'ceiling/cfast-demo.json',JOB/'cfast-demo.json','cfast-demo.json'),(OUT/'model.html',APP/'_internal/cad_engine/integrated_viewer.html','integrated_viewer.html')]
log=[]
for source,dest,name in files:
 backup=back/name
 if not backup.exists():shutil.copy2(dest,backup)
 before=sha(dest);shutil.copy2(source,dest);assert sha(source)==sha(dest)
 log.append(dict(source=str(source),destination=str(dest),backup=str(backup),before=before,after=sha(dest)))
(OUT/'설치기록.json').write_text(json.dumps(dict(files=log,building_sha256=sha(JOB/'building.json'),legacy_ui_unchanged=True),ensure_ascii=False,indent=2),'utf8')
print('Installed 3 backed-up files; building and engine unchanged')
