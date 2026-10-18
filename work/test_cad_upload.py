from pathlib import Path
import sys,os,json,urllib.request,urllib.parse,urllib.error,time,subprocess
W=Path(__file__).resolve().parent;S=W/'cad-web';D=W/'cad-web-test-data';D.mkdir(exist_ok=True)
port=os.environ.get('CAD_TEST_PORT','8881')
env=dict(os.environ,PYTHONPATH=str(W/'cad-deps'),PYTHONIOENCODING='utf-8',FIRE_SPACE_DATA=str(D),FIRE_SPACE_PORT=port)
log=(W/'cad-web-server.log').open('w',encoding='utf8')
command=[os.environ['CAD_TEST_EXE'],'--no-browser'] if os.environ.get('CAD_TEST_EXE') else [sys.executable,str(S/'local_app.py'),'--no-browser']
server=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
def api(path,body=None,raw=False):
 data=body if isinstance(body,bytes) else json.dumps(body).encode() if body is not None else None
 with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:'+port+path,data=data),timeout=120) as r:return r.read() if raw else json.load(r)
try:
 for i in range(60):
  try:health=api('/api/health');break
  except Exception:
   if server.poll() is not None:raise RuntimeError((W/'cad-web-server.log').read_text('utf8'))
   time.sleep(.5)
 assert health['cad_version']=='cad-upload-v1'
 manifest=json.loads((W/'drawing-manifest-v7.json').read_text('utf8'))
 job=api('/api/jobs',{'name':'CAD 업로드 연결 검증 · B1·1F'})['id']
 for floor in ['B1','1F']:
  src=Path(next(r['path'] for r in manifest['drawings'] if r['role']=='architectural_plan' and r['floor']==floor))
  api('/api/jobs/'+job+'/files?name='+urllib.parse.quote(src.name),src.read_bytes())
 api('/api/jobs/'+job+'/process',{});last=''
 deadline=time.monotonic()+1200
 while time.monotonic()<deadline:
  row=next(j for j in api('/api/jobs') if j['id']==job)
  if row['message']!=last:print(row['status'],row['progress'],row['message'],flush=True);last=row['message']
  if row['status']=='error':raise RuntimeError(row['message'])
  if row['status']=='ready':break
  time.sleep(2)
 else:raise TimeoutError('integration test timed out')
 summary=api('/cad-result/'+job+'/summary.json');assert summary['floors']==['B1','1F'];assert summary['vertical_links']>=4
 html=api('/result/'+job,raw=True).decode();assert 'model.html' in html and 'plans.html' in html
 model=api('/cad-result/'+job+'/model.html',raw=True).decode();assert 'cdn.jsdelivr.net' not in model
 assert "REVISION = '160'" in api('/cad-assets/three.module.js',raw=True).decode()
 for tail in ['/cad-result/'+job+'/%2e%2e/files.json','/cad-assets/%2e%2e/local_index.html']:
  try:api(tail,raw=True);raise AssertionError('path traversal allowed')
  except urllib.error.HTTPError as e:assert e.code==404
 assert 'SAVED_REVIEW_STATE' in api('/result/'+job+'?legacy=1',raw=True).decode()
 (W/'cad-upload-integration.json').write_text(json.dumps(dict(status='passed',job=job,summary=summary,server_pid=server.pid,port=port,executable=os.environ.get('CAD_TEST_EXE')),ensure_ascii=False,indent=2),'utf8')
 print('INTEGRATION PASSED',job,flush=True)
 # Keep the test server available for the browser verification.
except:
 server.terminate();raise

