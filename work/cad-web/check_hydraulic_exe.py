from pathlib import Path
import os,subprocess,time,urllib.request,json
env=os.environ.copy();env['FIRE_SPACE_PORT']='8789';env['FIRE_SPACE_DATA']=str(Path('work/exe-test-data').resolve())
p=subprocess.Popen([str(Path('work/hydraulic-dist/소방 크로키 업-로컬웹앱/소방 크로키 업.exe').resolve()),'--no-browser'],env=env,creationflags=subprocess.CREATE_NO_WINDOW)
base='http://127.0.0.1:8789'
def call(path,data=None):
 with urllib.request.urlopen(urllib.request.Request(base+path,data=data),timeout=30) as r:return r.read()
try:
 for _ in range(30):
  try:assert json.loads(call('/api/health'))['app']=='fire-space-local';break
  except Exception:time.sleep(1)
 else:raise AssertionError('EXE startup failed')
 j=json.loads(call('/api/jobs',b'{"name":"Packaged DWG verification"}'))['id']
 call('/api/jobs/'+j+'/files?name=1F.dwg',Path('work/cad-input/2.dwg').read_bytes());call('/api/jobs/'+j+'/process',b'{}')
 for _ in range(90):
  row=next(r for r in json.loads(call('/api/jobs')) if r['id']==j)
  if row['status'] in ('ready','error'):break
  time.sleep(1)
 assert row['status']=='ready',row
 html=call('/result/'+j);assert b'cadLayers' in html and b'REVIEW_DATA' in html and b'hydraulic-scripts' in html
 assert json.loads(call('/api/jobs/'+j+'/hydraulics')) is None
 call('/api/stop',b'{}');p.wait(timeout=15)
 print('PASS standalone EXE startup, bundled DWG converter, result serving, clean shutdown')
finally:
 if p.poll() is None:p.terminate()
