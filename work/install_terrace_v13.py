from pathlib import Path
import json,sys,os,shutil,datetime,urllib.request,time,subprocess,hashlib
root=Path(__file__).resolve().parent.parent;out=root/'outputs/CAD-테라스-v13';app=Path('C:/Users/예방/Desktop/소방 크로키 업-로컬웹앱');job='d018b4bb75da4475b1fd75447603c1a0';built=out/'배포본/소방 크로키 업-로컬웹앱'
def api(port,path,value=None):
 with urllib.request.urlopen('http://127.0.0.1:'+str(port)+path,data=None if value is None else json.dumps(value).encode(),timeout=10) as r:return json.load(r)
# Executable startup check uses an isolated copy of the existing test data.
env=dict(os.environ,FIRE_SPACE_PORT='8884',FIRE_SPACE_DATA=str(root/'work/cad-ui-test-data'))
proc=subprocess.Popen([str(built/'소방 크로키 업.exe'),'--no-browser'],env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
try:
 for _ in range(50):
  try:assert api(8884,'/api/health')['app']=='fire-space-local';break
  except Exception:time.sleep(.2)
 else:raise RuntimeError('new executable startup failed')
finally:
 try:api(8884,'/api/stop',{})
 except Exception:pass
 try:proc.wait(timeout=10)
 except subprocess.TimeoutExpired:proc.terminate();proc.wait(timeout=10)
jobs=api(8778,'/api/jobs');assert isinstance(jobs,list) and not any(j['status']=='processing' for j in jobs)
backup=app/'개발/backups'/('cad-terrace-v13-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));backup.mkdir(parents=True)
paths=['소방 크로키 업.exe','_internal/cad_engine/cad_model_transport.py','소스/cad_engine/cad_model_transport.py','개발/work/cad_engine/cad_model_transport.py','data/'+job+'/cad-output/building.json']
for rel in paths:
 src=app/rel
 if src.exists():dst=backup/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
record=dict(version='cad-terrace-v13',backup=str(backup),installed=str(app),model_updated=job,extraction_rerun=False,history_preserved=True,status='backed_up',executable_startup_test=True)
(out/'설치기록.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),'utf8')
api(8778,'/api/stop',{});time.sleep(1)
# Only executable and changed model module are replaced; dependencies unchanged.
shutil.copy2(built/'소방 크로키 업.exe',app/'소방 크로키 업.exe')
for rel in paths[1:4]:shutil.copy2(root/'work/cad-web/cad_engine/cad_model_transport.py',app/rel)
shutil.copy2(out/'building.json',app/paths[4])
run=subprocess.Popen([str(app/'소방 크로키 업.exe'),'--no-browser'],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
for _ in range(50):
 try:assert api(8778,'/api/health')['app']=='fire-space-local';break
 except Exception:time.sleep(.2)
else:raise RuntimeError('installed executable startup failed')
m=api(8778,'/cad-result/'+job+'/building.json');t=next(f for f in m['floors'] if f['name']=='3F')['outdoor_spaces'][0];assert t['upper_slab_overlap_m2']==0
record.update(status='installed',pid=run.pid,exe_sha256=hashlib.sha256((app/'소방 크로키 업.exe').read_bytes()).hexdigest(),terrace_area_m2=118.01604)
(out/'설치기록.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),'utf8');print(json.dumps(record,ensure_ascii=False))
