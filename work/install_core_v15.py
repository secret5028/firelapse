from pathlib import Path
import json,datetime,shutil,hashlib
root=Path.cwd();out=root/'outputs/CAD-수직동선완화-v15';app=Path('C:/Users/예방/Desktop/소방 크로키 업-로컬웹앱');src=root/'work/cad-web/cad_engine/integrated_viewer.html';job='d018b4bb75da4475b1fd75447603c1a0'
backup=app/'개발/backups'/('cad-core-v15-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));backup.mkdir(parents=True)
paths=['_internal/cad_engine/integrated_viewer.html','소스/cad_engine/integrated_viewer.html','개발/work/cad_engine/integrated_viewer.html','data/'+job+'/cad-output/model.html']
for rel in paths:
 p=app/rel;q=backup/rel;q.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():shutil.copy2(p,q)
 shutil.copy2(src,p)
# Keep the newly packaged executable's companion resource in sync.
shutil.copy2(src,root/'outputs/CAD-테라스-v13/배포본/소방 크로키 업-로컬웹앱/_internal/cad_engine/integrated_viewer.html')
shutil.copy2(root/'work/cad_core_emphasis.js',out/'cad_core_emphasis.js')
record=dict(version='cad-core-v15',installed=str(app),backup=str(backup),status='installed',template_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),current_job=job,restart_required=False,source_geometry_changed=False)
(out/'설치기록.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),'utf8');print(json.dumps(record,ensure_ascii=False))

