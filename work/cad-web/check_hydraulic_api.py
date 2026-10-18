from pathlib import Path
import os,json,threading,urllib.request,urllib.error,hashlib
os.environ['FIRE_SPACE_DATA']=str(Path('work/hydraulic-api-test').resolve())
import local_app as app
s=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler);threading.Thread(target=s.serve_forever,daemon=True).start();base='http://127.0.0.1:'+str(s.server_port)
def call(path,obj=None):
 req=urllib.request.Request(base+path,data=None if obj is None else json.dumps(obj).encode())
 with urllib.request.urlopen(req) as r:return r.read()
try:
 j=json.loads(call('/api/jobs',{'name':'Hydraulic test'}))['id'];j2=json.loads(call('/api/jobs',{'name':'Isolation test'}))['id']
 for ident in [j,j2]:
  # distinct real manifest hashes, without invoking CAD converter for an API contract test
  (app.HOME/ident/'files.json').write_text(json.dumps([{'sha256':ident}]),'utf-8')
  (app.HOME/ident/'result.html').write_text('<html><body><header>History</header></body></html>','utf-8');app.update(ident,'ready','test',100)
 manifest=json.loads((app.HOME/j/'files.json').read_text('utf-8'));digest=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()
 net=json.loads(Path('work/hydraulic-example.json').read_text('utf-8'));net['buildingId']=digest
 assert json.loads(call('/api/jobs/'+j+'/hydraulics')) is None
 assert json.loads(call('/api/jobs/'+j+'/hydraulics',net))['ok']
 assert json.loads(call('/api/jobs/'+j+'/hydraulics'))==net
 assert json.loads(call('/api/jobs/'+j2+'/hydraulics')) is None
 try:call('/api/jobs/'+j2+'/hydraulics',net);raise AssertionError('cross-building accepted')
 except urllib.error.HTTPError as e:assert e.code==400
 content=call('/result/'+j).decode();assert 'hydraulic-scripts' in content and digest in content and 'LOCAL_JOB' in content
 print('PASS history network save/read, different building rejected, older results receive shared hydraulic panel')
finally:s.shutdown()
