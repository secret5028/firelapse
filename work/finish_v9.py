import pathlib,json,sys,os,subprocess,re,shutil,hashlib
W=pathlib.Path(__file__).resolve().parent;C=pathlib.Path('C:/Users/예방/Documents/Codex/2026-09-07/2/CAD3D');O=W.parent/'outputs/CAD-평면연결-v9';sys.path[:0]=[str(W/'cad-deps'),str(C)]
from cad_stage1_report import publish
publish(O,W/'drawing-manifest-v7.json')
from PIL import Image,ImageDraw,ImageFont
font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',25)
for folder in O.glob('office-*'):
 p=json.loads((folder/'plan.json').read_text(encoding='utf8'));ra=p['raster'];im=Image.open(folder/'fused.png').convert('RGB');d=ImageDraw.Draw(im,'RGBA')
 def xy(x,y):return ((x*1000-ra['x0'])/ra['R'],(ra['y1']-y*1000)/ra['R'])
 for ramp in p['ramps']:
  for part in ramp['polys']:d.polygon([xy(*q) for q in part['o']],fill=(255,140,0,100),outline=(220,100,0,255),width=4)
 for c in p['cores']:
  a=xy(c['cx']-c['w']/2,c['cy']+c['h']/2);b=xy(c['cx']+c['w']/2,c['cy']-c['h']/2);col=(0,120,110,255) if c['kind']=='stair' else (125,60,175,255)
  d.rectangle([a,b],outline=col,width=4);d.text((a[0],a[1]-32),('계단 ' if c['kind']=='stair' else '승강기 ')+c['core_id'],font=font,fill=col,stroke_width=2,stroke_fill='white')
 im.thumbnail((1800,1800));im.save(folder/'코어-미리보기.png')
page=(O/'index.html').read_text(encoding='utf8').replace('/fused.png','/코어-미리보기.png');(O/'index.html').write_text(page,encoding='utf8')
# Syntax and artifact-link checks, without claiming browser interaction.
node=pathlib.Path('C:/Users/예방/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe');n=0
for page in O.rglob('*.html'):
 if 'code' in page.relative_to(O).parts:continue
 text=page.read_text(encoding='utf8')
 for attrs,script in re.findall(r'<script\b([^>]*)>(.*?)</script>',text,re.S|re.I):
  if not script.strip():continue
  if 'importmap' in attrs or 'application/json' in attrs:json.loads(script);continue
  tmp=W/'v9-syntax-check.mjs';tmp.write_text(script,encoding='utf8');r=subprocess.run([str(node),'--check',str(tmp)],capture_output=True,text=True,encoding='utf8')
  assert r.returncode==0,(str(page),r.stderr[-1200:]);n+=1
(O/'UI검사.json').write_text(json.dumps(dict(javascript_blocks_passed=n,browser_interaction_test='not_run',visual_check='static core overlay preview'),ensure_ascii=False,indent=2),encoding='utf8')
env=dict(os.environ,PYTHONPATH=str(W/'cad-deps'),TEMP=str(W/'test-temp'),TMP=str(W/'test-temp'),PYTHONIOENCODING='utf-8')
r=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(C),'-p','test_cad*.py'],env=env,capture_output=True,text=True,encoding='utf8');(O/'테스트결과.txt').write_text(r.stdout+r.stderr,encoding='utf8');assert r.returncode==0
# Report code is copied by publish. Keep exact source hashes in one place.
print('Published, JS blocks',n,'and unit suite passed',flush=True)
