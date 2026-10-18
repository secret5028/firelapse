import pathlib,zipfile,re,subprocess,json,hashlib
W=pathlib.Path(__file__).resolve().parent;O=W.parent/'outputs/CAD-문호표현-v8'
f=O/'index.html';f.write_text(f.read_text(encoding='utf8').replace('67개 테스트','70개 테스트'),encoding='utf8')
checked=0
for f in O.rglob('*.html'):
 if 'code' in f.parts:continue
 for attrs,body in re.findall(r'<script([^>]*)>([\s\S]*?)</script>',f.read_text(encoding='utf8')):
  if 'importmap' in attrs or not body.strip():continue
  assert "setLayer('connectivity.svg')" not in body
  p=W/'v8-check.mjs';p.write_text(body,encoding='utf8');subprocess.run([r'C:\Users\예방\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe','--check',str(p)],check=True,capture_output=True);checked+=1
with zipfile.ZipFile(O/'CAD-문호표현-v8.zip','w',zipfile.ZIP_DEFLATED) as z:
 for f in (O/'code').iterdir():z.write(f,'code/'+f.name)
 for name in ('문호표현-수정.txt','문호표현-수정.json','office-1F-review-v7.json','office-PH-review-v7.json','도면검토목록.json'):z.write(O/name,name)
print('JavaScript syntax passed:',checked)
