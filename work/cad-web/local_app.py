"""Offline drawing workspace. All formats use the same review document."""
from pathlib import Path
import sys,os,json,uuid,hashlib,threading,webbrowser,sqlite3,time,subprocess,shutil,re,io,base64
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlparse,parse_qs,unquote
from concurrent.futures import ThreadPoolExecutor
from PIL import Image,ImageDraw
import ezdxf
from ezdxf.disassemble import recursive_decompose
from ezdxf import path as cadpath
import file_tool
import drawing_llm
import interpretation
import preprocess_pipeline
import cad_upload
if "--cad-worker" in sys.argv:
 with open(Path(sys.argv[-2])/"cad-worker.log","w",encoding="utf8") as cadlog:
  with cad_upload.contextlib.redirect_stdout(cadlog),cad_upload.contextlib.redirect_stderr(cadlog):
   raise SystemExit(cad_upload.worker(sys.argv[-2],sys.argv[-1]))
from hydraulic_embed import embed_hydraulics

BASE=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))
if not getattr(sys,'frozen',False):BASE=BASE/'local-resources'
file_tool.BASE=BASE
HOME=Path(os.environ.get('FIRE_SPACE_DATA',str(Path(sys.executable).parent/'data' if getattr(sys,'frozen',False) else Path(__file__).parent/'local-data')))
HOME.mkdir(parents=True,exist_ok=True)
POOL=ThreadPoolExecutor(max_workers=1)
SUPPORTED=file_tool.SUPPORTED|{'.dwg','.dxf'}
def db():
 c=sqlite3.connect(HOME/'history.sqlite');c.row_factory=sqlite3.Row;return c
with db() as c:
 c.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,name TEXT,status TEXT,message TEXT,created REAL)')
 if 'progress' not in [r['name'] for r in c.execute('PRAGMA table_info(jobs)')]:
  c.execute('ALTER TABLE jobs ADD COLUMN progress INTEGER NOT NULL DEFAULT 0')
  c.execute("UPDATE jobs SET progress=100 WHERE status='ready'")
 c.execute("UPDATE jobs SET status='error',message='실행이 중단되었습니다. 다시 처리하세요.' WHERE status='processing'")
def update(j,status,message,progress=None):
 with db() as c:
  if progress is None:c.execute('UPDATE jobs SET status=?,message=? WHERE id=?',(status,message,j))
  else:c.execute('UPDATE jobs SET status=?,message=?,progress=? WHERE id=?',(status,message,max(0,min(100,int(progress))),j))
def cad_pages(src,label,folder,progress=lambda value,message:None):
 progress(.02,'CAD 읽기')
 dxf=src
 if src.suffix=='.dwg':
  progress(.05,'DWG 변환 중')
  dxf=folder/(src.stem+'.dxf')
  result=subprocess.run([str(BASE/'cad-tools'/'dwg2dxf.exe'),'-y','-o',str(dxf),str(src)],capture_output=True,timeout=180,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  (folder/(src.stem+'.conversion.log')).write_bytes(result.stdout+result.stderr)
  if result.returncode or not dxf.exists():raise ValueError(label+': DWG 변환 실패. CAD에서 DXF로 저장한 파일도 사용할 수 있습니다.')
 progress(.25,'DXF 구조 읽기')
 doc=ezdxf.readfile(dxf);pages=[]
 units={1:.0254,2:.3048,4:.001,5:.01,6:1,7:1000}.get(doc.units,.001)
 layouts=[doc.modelspace()]+[l for l in doc.layouts if l.name!='Model' and len(l)]
 for layout_index,layout in enumerate(layouts):
  progress(.3+.65*layout_index/len(layouts),'레이어 추출 · '+layout.name)
  lines=[];texts=[]
  for n,e in enumerate(recursive_decompose(layout)):
   if n>200000:raise ValueError('CAD 객체가 너무 많습니다. 도면을 분리해 주세요.')
   try:
    if e.dxftype() in ('TEXT','MTEXT'):
     texts.append(e.dxf.text if e.dxftype()=='TEXT' else e.plain_text());continue
    if e.dxftype() in ('HATCH','SOLID','TRACE','3DFACE','VIEWPORT'):continue
    pts=[[p.x,p.y] for p in cadpath.make_path(e).flattening(max(.01,.025/units))]
    if len(pts)>1:lines.append({'layer':e.dxf.layer,'p':pts})
   except (AttributeError,TypeError,ValueError,NotImplementedError):continue
  if not lines:continue
  progress(.3+.65*(layout_index+.7)/len(layouts),'도면 이미지 생성 · '+layout.name)
  xy=[p for l in lines for p in l['p']];xmin=min(p[0] for p in xy);ymin=min(p[1] for p in xy);xmax=max(p[0] for p in xy);ymax=max(p[1] for p in xy)
  scale=min(2000/max(xmax-xmin,1),1500/max(ymax-ymin,1));im=Image.new('RGB',(2100,1600),'white');draw=ImageDraw.Draw(im)
  mapped=[]
  for l in lines:
   pts=[[50+(p[0]-xmin)*scale,1550-(p[1]-ymin)*scale] for p in l['p']];draw.line([tuple(p) for p in pts],fill='#344252',width=1)
   mapped.append({'layer':l['layer'],'p':pts})
  mapping={l['layer']:('wall' if re.search(r'(WALL|BWALL|\$CON$|^IN-CON$)',l['layer'],re.I) else 'door' if re.search(r'(DOOR|DOFRAME)',l['layer'],re.I) else 'window' if re.search(r'(WINDOW|WIN$)',l['layer'],re.I) else '') for l in lines}
  b=io.BytesIO();im.save(b,'PNG');floor=re.search(r'(?:평면도\s*)?(\d+)층',label);floor=int(floor.group(1)) if floor else 1
  pages.append({'image':'data:image/png;base64,'+base64.b64encode(b.getvalue()).decode(),'width':2100,'height':1600,'source':label,'number':len(pages)+1,'text':label+' · '+layout.name,'cad':mapped,'initial':{'floor':floor,'scale':units/scale,'mapping':mapping},'unitNote':'CAD 단위 적용' if doc.units else 'CAD 단위 미지정: mm 임시 적용','drawingTexts':texts[:100]})
 if not pages:raise ValueError(label+': 변환 가능한 선 객체가 없습니다.')
 progress(1,'CAD 추출 완료')
 return pages
def process(j):
 folder=HOME/j
 try:
  manifest=json.loads((folder/'files.json').read_text('utf-8'));pages=[]
  has_cad=any(Path(f['stored']).suffix in ('.dwg','.dxf') for f in manifest)
  for i,f in enumerate(manifest):
   def report(value,message):update(j,'processing',f'{i+1}/{len(manifest)} · {f["name"]} · {message}',5+(20 if has_cad else 85)*(i+value)/len(manifest))
   report(0,'읽기 준비')
   src=folder/f['stored']
   if src.suffix in ('.dwg','.dxf'):part=cad_pages(src,f['name'],folder,report)
   else:
    def page_report(message):
     match=re.search(r'(\d+)/(\d+)',message)
     report(int(match[1])/int(match[2]) if match else 0,message.strip())
    part=file_tool.extract_pages(src,page_report)
    for p in part:p['source']=f['name'];p['text']=f['name']+' · '+p.get('text','')
   pages+=part
   report(1,'추출 완료')
   if len(pages)>300:raise ValueError('한 작업은 최대 300페이지입니다.')
  with db() as c:name=c.execute('SELECT name FROM jobs WHERE id=?',(j,)).fetchone()['name']
  digest=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()
  update(j,'processing','기존 도면 검토 화면 저장',25 if has_cad else 93)
  result=file_tool.render_review(name,digest,pages)
  update(j,'processing','결과 파일 저장 중',27 if has_cad else 98)
  (folder/'result.html').write_text(result,'utf-8')
  if has_cad:
   result=cad_upload.run(folder,BASE,lambda value,message:update(j,'processing',message,value))
   update(j,'ready',f"CAD {len(result['floors'])}개 층 · 평면 추출·3D 모델 완료",100)
  else:update(j,'ready',f'{len(pages)}페이지 · 층과 CAD 레이어를 확인하세요',100)
 except Exception as e:update(j,'error',str(e)[:500])
preprocess_pipeline.configure(HOME,BASE,POOL,db)
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def send(self,data,code=200,mime='application/json; charset=utf-8'):
  if not isinstance(data,bytes):data=(json.dumps(data,ensure_ascii=False) if not isinstance(data,str) else data).encode('utf-8')
  self.send_response(code);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)));self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
 def do_GET(self):
  p=urlparse(self.path).path
  if cad_upload.serve(self,p,HOME,BASE):return
  if preprocess_pipeline.handle_get(self,p):return
  if p=='/api/health':return self.send({'app':'fire-space-local','cad_version':'cad-upload-v1'})
  if p=='/api/llm/status':return self.send(drawing_llm.config())
  if p=='/':return self.send((BASE/'local_index.html').read_bytes(),mime='text/html; charset=utf-8')
  if p=='/api/jobs':
   with db() as c:return self.send([dict(r) for r in c.execute('SELECT * FROM jobs ORDER BY created DESC')])
  m=re.fullmatch(r'/api/jobs/([a-f0-9]{32})/hydraulics',p)
  if m:
   with db() as c:row=c.execute('SELECT id FROM jobs WHERE id=?',(m[1],)).fetchone()
   if not row:return self.send({'error':'작업이 없습니다.'},404)
   f=HOME/m[1]/'hydraulics.json'
   return self.send(json.loads(f.read_text('utf-8')) if f.exists() else None)
  m=re.fullmatch(r'/result/([a-f0-9]{32})',p)
  if m:
   if (HOME/m[1]/'cad-output/index.html').exists() and parse_qs(urlparse(self.path).query).get('legacy')!=['1']:
    self.send_response(302);self.send_header('Location','/cad-result/'+m[1]+'/index.html');self.end_headers();return
   f=HOME/m[1]/'result.html'
   if f.exists():
    content=f.read_text('utf-8');statefile=f.parent/'state.json'
    manifest=json.loads((f.parent/'files.json').read_text('utf-8'))
    digest=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()
    with db() as c:row=c.execute('SELECT name FROM jobs WHERE id=?',(m[1],)).fetchone()
    content=embed_hydraulics(content,BASE,digest,row['name'])
    content+='\n<script>'+ (BASE/'drawing-llm-ui.js').read_text('utf8')+'</script>'
    content+='\n<script>'+ (BASE/'interpretation-ui.js').read_text('utf8')+'</script>'
    state=json.loads(statefile.read_text('utf-8')) if statefile.exists() else None
    code='<script>window.LOCAL_JOB='+json.dumps(m[1])+';window.SAVED_REVIEW_STATE='+file_tool.js_json(state)+';</script>'
    return self.send(content.replace('<header>',code+'<header>',1),mime='text/html; charset=utf-8')
  return self.send({'error':'찾을 수 없습니다.'},404)
 def do_POST(self):
  if preprocess_pipeline.handle_post(self):return
  try:
   origin=self.headers.get('Origin')
   if origin and origin!='http://'+self.headers.get('Host',''):return self.send({'error':'다른 사이트의 요청은 허용되지 않습니다.'},403)
   n=int(self.headers.get('Content-Length','0'))
   if n<0 or n>50*1024*1024:return self.send({'error':'파일당 최대 50MB입니다.'},413)
   data=self.rfile.read(n);u=urlparse(self.path);p=u.path
   if p=='/api/stop':
    self.send({'ok':True});threading.Thread(target=self.server.shutdown,daemon=True).start();return
   if p=='/api/jobs':
    name=str(json.loads(data).get('name','새 건물')).strip()[:100] or '새 건물';j=uuid.uuid4().hex;(HOME/j).mkdir()
    (HOME/j/'files.json').write_text('[]','utf-8')
    with db() as c:c.execute('INSERT INTO jobs(id,name,status,message,created) VALUES(?,?,?,?,?)',(j,name,'upload','파일 업로드 중',time.time()))
    return self.send({'id':j})
   m=re.fullmatch(r'/api/jobs/([a-f0-9]{32})/(files|process|state|cad-state|hydraulics|llm-review|interpret)',p)
   if not m:raise ValueError('잘못된 요청입니다.')
   j,action=m.groups();folder=HOME/j
   with db() as c:row=c.execute('SELECT * FROM jobs WHERE id=?',(j,)).fetchone()
   if not row:raise ValueError('작업이 없습니다.')
   if action=='interpret':
    if row['status']!='ready' or n>2100000:raise ValueError('처리 완료된 도면의 2MB 이하 요청만 가능합니다.')
    v=interpretation.handle(folder,json.loads(data))
    return self.send(v,mime='application/zip') if isinstance(v,bytes) else self.send(v)
   if action=='llm-review':
    if row['status']!='ready' or n>10000:raise ValueError('처리 완료된 도면만 검토할 수 있습니다.')
    return self.send(drawing_llm.review(folder,json.loads(data)))
   if action=='cad-state':
    v=json.loads(data)
    if row['status']!='ready' or n>2000000 or not (folder/'cad-output/building.json').exists():raise ValueError('처리 완료된 CAD 모델만 저장할 수 있습니다.')
    if not isinstance(v,dict) or v.get('version')!=1 or v.get('jobId')!=m[1]:raise ValueError('다른 CAD 작업의 설정입니다.')
    ops=v.get('operations',{})
    if not isinstance(ops,dict) or any(not isinstance(ops.get(k,[]),list) or len(ops.get(k,[]))>300 for k in ['vehicles','routes','fires','people']):raise ValueError('작전 설정 형식이 잘못되었습니다.')
    tmp=folder/('cad-state-'+uuid.uuid4().hex+'.tmp');tmp.write_text(json.dumps(v,ensure_ascii=False,allow_nan=False),'utf-8');os.replace(tmp,folder/'cad-ui-state.json');return self.send({'ok':True})
   if action=='hydraulics':
    if row['status']!='ready' or n>2000000:raise ValueError('처리 완료된 건물에 2MB 이하의 계통을 저장하세요.')
    v=json.loads(data)
    manifest=json.loads((folder/'files.json').read_text('utf-8'))
    digest=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()
    if not isinstance(v,dict) or v.get('buildingId')!=digest or v.get('version')!=1:raise ValueError('다른 건물의 계통입니다.')
    if not isinstance(v.get('nodes'),list) or not isinstance(v.get('pipes'),list) or len(v['nodes'])>1000 or len(v['pipes'])>2000:raise ValueError('계통 형식이 잘못되었습니다.')
    tmp=folder/('hydraulics-'+uuid.uuid4().hex+'.tmp');tmp.write_text(json.dumps(v,ensure_ascii=False,allow_nan=False),'utf-8');os.replace(tmp,folder/'hydraulics.json');return self.send({'ok':True})
   if action=='state':
    state=json.loads(data)
    if row['status']!='ready' or not isinstance(state.get('pages'),list) or len(state['pages'])>300:raise ValueError('잘못된 작업 정보입니다.')
    content=(folder/'result.html').read_text('utf-8')
    if json.dumps(state.get('sourceHash')) not in content:raise ValueError('다른 건물의 작업입니다.')
    tmp=folder/'state.tmp';tmp.write_text(json.dumps(state,ensure_ascii=False),'utf-8');os.replace(tmp,folder/'state.json');return self.send({'ok':True})
   if row['status']=='processing':raise ValueError('처리 중입니다.')
   files=json.loads((folder/'files.json').read_text('utf-8'))
   if action=='files':
    if row['status']!='upload':raise ValueError('새 작업에 업로드하세요.')
    name=Path(parse_qs(u.query).get('name',[''])[0].replace('\\','/')).name;suffix=Path(name).suffix.lower()
    if suffix not in SUPPORTED:raise ValueError('DWG, DXF, PDF, JPG, PNG, TIFF, BMP를 지원합니다.')
    if len(files)>=50:raise ValueError('한 작업은 50개 파일까지입니다.')
    floor_override=parse_qs(u.query).get('floor',[None])[0]
    if floor_override and not re.fullmatch(r'(B[1-9]\d?|[1-9]\d?F|PH)',floor_override):raise ValueError('층 형식이 잘못되었습니다.')
    sha=hashlib.sha256(data).hexdigest()
    if any(f['sha256']==sha for f in files):return self.send({'duplicate':True})
    stored=uuid.uuid4().hex+suffix;(folder/stored).write_bytes(data);files.append({'name':name,'stored':stored,'sha256':sha,'floor':floor_override});(folder/'files.json').write_text(json.dumps(files,ensure_ascii=False),'utf-8');return self.send({'ok':True})
   if not files:raise ValueError('도면을 선택하세요.')
   update(j,'processing','처리 대기 중',0);POOL.submit(process,j);return self.send({'ok':True})
  except Exception as e:return self.send({'error':str(e)},400)
def main():
 port=int(os.environ.get('FIRE_SPACE_PORT','8778'))
 try:server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
 except OSError:
  import urllib.request
  try:
   with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health',timeout=2) as r:existing=json.load(r)
   if existing.get('app')!='fire-space-local':raise ValueError('사용 중인 포트')
   webbrowser.open(f'http://127.0.0.1:{port}');return
  except Exception:raise RuntimeError('8778 포트가 사용 중입니다. 기존 실행을 종료해 주세요.')
 if '--no-browser' not in sys.argv:webbrowser.open(f'http://127.0.0.1:{port}')
 server.serve_forever()
if __name__=='__main__':main()
