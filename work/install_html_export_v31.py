from pathlib import Path
import shutil,json,hashlib
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'outputs/CAD-HTML내보내기-v31'
APP=Path('C:/Users/<user>/Desktop/소방 크로키 업-로컬웹앱')
JOB=APP/'data/d018b4bb75da4475b1fd75447603c1a0/cad-output'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert (OUT/'검증결과.json').exists()
source=OUT/'model.html'
assert 'installHtmlExport' in source.read_text('utf8')
unchanged={n:sha(JOB/n) for n in ['building.json','cfast-demo.json']}
for n,h in unchanged.items():assert h==sha(OUT/n)
backup=OUT/'backup/app';backup.mkdir(parents=True,exist_ok=True)
records=[]
for dest in [JOB/'model.html',APP/'_internal/cad_engine/integrated_viewer.html']:
    old=sha(dest);b=backup/dest.name
    if not b.exists():shutil.copy2(dest,b)
    shutil.copy2(source,dest);assert sha(source)==sha(dest)
    records.append(dict(destination=str(dest),backup=str(b),before=old,after=sha(dest)))
assert unchanged=={n:sha(JOB/n) for n in unchanged}
(OUT/'설치기록.json').write_text(json.dumps(dict(files=records,unchanged=unchanged),ensure_ascii=False,indent=2),'utf8')
print('Installed two viewer files with backups; model and simulation data unchanged')
