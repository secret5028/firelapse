from pathlib import Path
import urllib.request,urllib.parse,json,time,io
from PIL import Image
W=Path(__file__).resolve().parent;URL='http://127.0.0.1:8882'
def api(path,body=None,raw=False):
 data=body if isinstance(body,bytes) else json.dumps(body).encode() if body is not None else None
 with urllib.request.urlopen(urllib.request.Request(URL+path,data=data),timeout=60) as r:return r.read() if raw else json.load(r)
def submit(name,filename,data):
 j=api('/api/jobs',{'name':name})['id'];api('/api/jobs/'+j+'/files?name='+urllib.parse.quote(filename),data);api('/api/jobs/'+j+'/process',{});return j
dwg=submit('DWG 업로드 검증 · 호텔 5F','hotel-5F.dwg',(W/'cad-input/hotel-5F.dwg').read_bytes())
im=Image.new('RGB',(100,100),'white');buf=io.BytesIO();im.save(buf,'PNG');scan=submit('기존 이미지 입력 회귀 검증','test.png',buf.getvalue())
for j in [dwg,scan]:
 last=''
 for i in range(600):
  row=next(x for x in api('/api/jobs') if x['id']==j)
  if last!=row['message']:print(row['status'],row['message'],flush=True);last=row['message']
  if row['status']=='error':raise AssertionError(row['message'])
  if row['status']=='ready':break
  time.sleep(2)
 else:raise TimeoutError(j)
assert 'SAVED_REVIEW_STATE' in api('/result/'+scan,raw=True).decode()
summary=api('/cad-result/'+dwg+'/summary.json');assert summary['floors']==['5F']
for tail in ['/cad-result/'+dwg+'/%2e%2e/files.json','/cad-assets/%2e%2e/local_index.html']:
 try:api(tail,raw=True);raise AssertionError('path traversal allowed')
 except urllib.error.HTTPError as e:assert e.code==404
(W/'cad-format-tests.json').write_text(json.dumps(dict(status='passed',dwg_job=dwg,image_job=scan,summary=summary),ensure_ascii=False,indent=2),'utf8')
print('DWG and existing image input passed',flush=True)
