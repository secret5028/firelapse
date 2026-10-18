from pathlib import Path
import shutil,datetime,json,hashlib
root=Path(__file__).resolve().parent.parent
app=Path('C:/Users/예방/Desktop/소방 크로키 업-로컬웹앱')
src=root/'work/cad-web/cad_engine/integrated_viewer.html'
out=root/'outputs/CAD-인터페이스복원-v12'
backup=app/'개발/backups'/('cad-ui-v12-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
targets=[app/'_internal/cad_engine/integrated_viewer.html',app/'소스/cad_engine/integrated_viewer.html']
targets += list((app/'data').glob('*/cad-output/model.html'))
changes=[]
for target in targets:
    assert target.resolve().is_relative_to(app.resolve()) and target.exists(),target
    saved=backup/target.relative_to(app);saved.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(target,saved);shutil.copy2(src,target)
    changes.append(str(target))
record=dict(version='cad-ui-v12',files=changes,backup=str(backup),sha256=hashlib.sha256(src.read_bytes()).hexdigest(),data_changed=False,extraction_rerun=False)
(out/'설치기록.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),'utf8')
print(json.dumps(record,ensure_ascii=False,indent=2))
