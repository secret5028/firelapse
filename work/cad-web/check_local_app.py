from pathlib import Path
import os,threading,urllib.request,json,time,re
os.environ['FIRE_SPACE_DATA']=str(Path('work/local-test-data').resolve())
import local_app as app
server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
base='http://127.0.0.1:'+str(server.server_port)
def call(path,data=None):
 req=urllib.request.Request(base+path,data=data)
 with urllib.request.urlopen(req,timeout=30) as r:return r.read()
def post(path,obj):return json.loads(call(path,json.dumps(obj).encode()))
j=post('/api/jobs',{'name':'DWG DXF PDF PNG 통합 검증'})['id']
for file in ['work/cad-input/2.dwg','work/cad-input/3.dxf','work/tool-check/다른PDF.pdf','work/tool-check/새도면.png']:
 f=Path(file);call('/api/jobs/'+j+'/files?name='+urllib.parse.quote(f.name),f.read_bytes())
call('/api/jobs/'+j+'/files?name=duplicate.dwg',Path('work/cad-input/2.dwg').read_bytes())
assert len(json.loads((app.HOME/j/'files.json').read_text('utf-8')))==4
post('/api/jobs/'+j+'/process',{})
for _ in range(120):
 row=next(r for r in json.loads(call('/api/jobs')) if r['id']==j)
 if row['status'] in ['ready','error']:break
 time.sleep(1)
assert row['status']=='ready',row
html=call('/result/'+j).decode();assert 'cadLayers' in html and 'LOCAL_JOB' in html
digest=re.search(r'"sourceHash": "([a-f0-9]+)"',html)[1]
post('/api/jobs/'+j+'/state',{'version':1,'sourceHash':digest,'pages':[]})
assert (app.HOME/j/'state.json').exists()
assert 'window.SAVED_REVIEW_STATE={"version": 1' in call('/result/'+j).decode()
j2=post('/api/jobs',{'name':'다른 건물'})['id'];assert j!=j2
assert not (app.HOME/j2/'state.json').exists()
server.shutdown()
print('PASS DWG conversion + DXF + PDF + PNG batch, duplicate prevention, history, isolated jobs, saved state')
