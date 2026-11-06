from pathlib import Path
import shutil,json,datetime,hashlib
W=Path(__file__).resolve().parent;O=W.parent/'outputs/CAD-웹앱연결-v11'
source=(O/'배포본/소방 크로키 업-로컬웹앱').resolve()
target=Path('C:/Users/<user>/Desktop/소방 크로키 업-로컬웹앱').resolve()
assert source.is_relative_to(O.resolve()) and target.name=='소방 크로키 업-로컬웹앱'
assert (target/'소방 크로키 업.exe').is_file() and (source/'소방 크로키 업.exe').is_file()
report=json.loads((W/'cad-upload-integration.json').read_text('utf8'));assert report['status']=='passed' and report.get('executable')
formats=json.loads((W/'cad-format-tests.json').read_text('utf8'));assert formats['status']=='passed'
backup=target/'개발/backups'/('cad-upload-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));backup.mkdir(parents=True)
shutil.copy2(target/'소방 크로키 업.exe',backup/'소방 크로키 업.exe')
shutil.copytree(target/'_internal',backup/'_internal')
shutil.copytree(target/'소스',backup/'소스')
shutil.copytree(source/'_internal',target/'_internal',dirs_exist_ok=True)
shutil.copy2(source/'소방 크로키 업.exe',target/'소방 크로키 업.exe')
shutil.copytree(O/'소스',target/'소스',dirs_exist_ok=True)
dev=target/'개발/work'
for name in ['local_app.py','cad_upload.py']:shutil.copy2(W/'cad-web'/name,dev/name)
shutil.copytree(W/'cad-web/cad_engine',dev/'cad_engine',dirs_exist_ok=True)
shutil.copytree(W/'cad-web/local-resources',dev/'local-resources',dirs_exist_ok=True)
record=dict(installed=str(target),backup=str(backup),exe_sha256=hashlib.sha256((target/'소방 크로키 업.exe').read_bytes()).hexdigest(),history='existing data directory preserved')
(O/'설치기록.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),'utf8');print(json.dumps(record,ensure_ascii=False))
