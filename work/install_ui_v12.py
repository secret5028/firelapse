from pathlib import Path
import os,sys,json,shutil,hashlib,datetime,urllib.request,time,subprocess
root=Path(__file__).resolve().parent.parent;out=root/'outputs/CAD-인터페이스복원-v12';src=out/'배포본/소방 크로키 업-로컬웹앱'
app=Path('C:/Users/<user>/Desktop/소방 크로키 업-로컬웹앱');job='d018b4bb75da4475b1fd75447603c1a0'
assert json.loads((out/'검증결과.json').read_text('utf8'))['status']=='passed'
def api(port,path,value=None):
 data=json.dumps(value).encode() if value is not None else None
 with urllib.request.urlopen('http://127.0.0.1:'+str(port)+path,data=data,timeout=10) as r:return json.load(r)
# Copy the final resource template into the build before executable verification.
shutil.copy2(root/'work/cad-web/cad_engine/integrated_viewer.html',src/'_internal/cad_engine/integrated_viewer.html')
env=dict(os.environ,FIRE_SPACE_PORT='8884',FIRE_SPACE_DATA=str(root/'work/cad-ui-test-data'))
test=subprocess.Popen([str(src/'소방 크로키 업.exe'),'--no-browser'],env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
try:
 for _ in range(50):
  try:api(8884,'/api/health');break
  except Exception:time.sleep(.2)
 context=api(8884,'/cad-result/'+job+'/legacy-context.json');assert context['jobId']==job
 state=context['state'];assert state['operations']['vehicles'] and state['operations']['people']
 assert api(8884,'/api/jobs/'+job+'/cad-state',state)['ok']
except Exception:
 test.terminate();raise
finally:
 try:api(8884,'/api/stop',{})
 except Exception:pass
 test.wait(timeout=15)
if '--resume-stopped-install' in sys.argv:
 backup=app/'개발/backups/cad-legacy-v12-20261014-171121'
 assert (backup/'소방 크로키 업.exe').exists()
else:
 jobs=api(8778,'/api/jobs');assert not any(j['status']=='processing' for j in jobs),'사용자 도면 처리 중: 설치 보류'
 assert api(8778,'/api/health')['app']=='fire-space-local'
 backup=app/'개발/backups'/('cad-legacy-v12-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));backup.mkdir(parents=True)
 shutil.copy2(app/'소방 크로키 업.exe',backup/'소방 크로키 업.exe')
 shutil.copytree(app/'_internal',backup/'_internal')
 shutil.copytree(app/'소스',backup/'소스')
 for name in ['building.json','model.html']:
  saved=backup/'data'/job/'cad-output'/name;saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(app/'data'/job/'cad-output'/name,saved)
 api(8778,'/api/stop',{});time.sleep(1)
shutil.copytree(src/'_internal',app/'_internal',dirs_exist_ok=True)
shutil.copy2(src/'소방 크로키 업.exe',app/'소방 크로키 업.exe')
shutil.copytree(root/'work/cad-web',app/'소스',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
for name in ['local_app.py','cad_upload.py']:shutil.copy2(root/'work/cad-web'/name,app/'개발/work'/name)
shutil.copytree(root/'work/cad-web/cad_engine',app/'개발/work/cad_engine',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
shutil.copy2(out/'building.json',app/'data'/job/'cad-output/building.json')
shutil.copy2(out/'model.html',app/'data'/job/'cad-output/model.html')
run=subprocess.Popen([str(app/'소방 크로키 업.exe'),'--no-browser'],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
for _ in range(50):
 try:health=api(8778,'/api/health');break
 except Exception:time.sleep(.2)
assert api(8778,'/cad-result/'+job+'/legacy-context.json')['jobId']==job
record=dict(version='cad-legacy-ui-v12',installed=str(app),backup=str(backup),exe_sha256=hashlib.sha256((app/'소방 크로키 업.exe').read_bytes()).hexdigest(),pid=run.pid,executable_verified=True,history_preserved=True,extraction_rerun=False,model_updated=job,test_fixtures_deployed=False)
(out/'설치기록.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),'utf8')
print(json.dumps(record,ensure_ascii=False))
