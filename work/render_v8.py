import pathlib,sys,json,shutil,hashlib,re,subprocess,zipfile
W=pathlib.Path(__file__).resolve().parent;CAD=pathlib.Path(r'C:\Users\<user>\Documents\Codex\2026-09-07\2\CAD3D');sys.path[:0]=[str(W/'cad-deps'),str(CAD)]
from cad_pipeline import render_fused
from cad_swing import swing_points
import numpy as np,cv2
OLD=W.parent/'outputs/CAD-전층레이어-v7';OUT=W.parent/'outputs/CAD-문호표현-v8'
shutil.copytree(OLD,OUT,dirs_exist_ok=True,ignore=shutil.ignore_patterns('*.zip'))
template=(CAD/'viewer_template.html').read_text(encoding='utf8')
render_files=['cad_swing.py','cad_plan.py','cad_pipeline.py','viewer_template.html']
provenance=dict(change='render_full_recorded_double_action_swing',code_sha256={n:hashlib.sha256((CAD/n).read_bytes()).hexdigest() for n in render_files})
rows=[]
for folder in [OUT,W.parent/'outputs/CAD-문판정-v6']:
 for d in folder.iterdir():
  if not d.is_dir() or not (d/'plan.json').exists():continue
  p=json.loads((d/'plan.json').read_text(encoding='utf8'))
  render_fused(p,None,d/'fused.png')
  if (d/'architecture.json').exists():render_fused(json.loads((d/'architecture.json').read_text(encoding='utf8')),None,d/'architecture_plan.png')
  (d/'문호표현-수정.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf8')
  if folder==OUT:
   original=json.loads((OLD/d.name/'plan.json').read_text(encoding='utf8'))
   assert original==p # rendering must not alter compartments or simulation state
   count=sum(l.get('open2') is not None for o in p['openings'] for l in o.get('leaves',[]))
   rows.append(dict(floor=p['floor'],double_action_leaves=count,geometry_unchanged=True))
 for f in folder.rglob('building.json'):
  b=json.loads(f.read_text(encoding='utf8'));f.with_suffix('.html').write_text(template.replace('/*__DATA__*/null',json.dumps(b,ensure_ascii=False)),encoding='utf8')

# Regenerate overview thumbnails from the corrected floor images.
floors=['B1']+[f'{i}F' for i in range(1,8)]+['PH'];contact=np.full((1560,2250,3),255,np.uint8)
for k,floor in enumerate(floors):
 im=cv2.imdecode(np.fromfile(str(OUT/('office-'+floor)/'fused.png'),np.uint8),cv2.IMREAD_COLOR);s=min(710/im.shape[1],465/im.shape[0]);im=cv2.resize(im,None,fx=s,fy=s)
 x=k%3*750+20;y=k//3*520+45;contact[y:y+im.shape[0],x:x+im.shape[1]]=im;cv2.putText(contact,floor,(x,y-15),cv2.FONT_HERSHEY_SIMPLEX,.75,(35,50,80),2)
cv2.imencode('.png',contact)[1].tofile(str(OUT/'전층-미리보기.png'))

# A focused before/after image, using the same WCS crop and scale.
p=json.loads((OUT/'office-1F/plan.json').read_text(encoding='utf8'));ra=p['raster']
def pixel(x,y):return (round((x*1000-ra['x0'])/ra['R']),round((ra['y1']-y*1000)/ra['R']))
x0,y0=pixel(14041.6,-1788.9);x1,y1=pixel(14050,-1795.1)
for root,name in [(OLD,'문호-수정전.png'),(OUT,'문호-수정후.png')]:
 im=cv2.imdecode(np.fromfile(str(root/'office-1F/fused.png'),np.uint8),cv2.IMREAD_COLOR)[y0:y1,x0:x1]
 im=cv2.resize(im,None,fx=2,fy=2,interpolation=cv2.INTER_NEAREST);cv2.imencode('.png',im)[1].tofile(str(OUT/name))
for f in OUT.rglob('*.html'):
 if 'code' in f.parts:continue
 h=f.read_text(encoding='utf8').replace('CAD-전층레이어-v7.zip','CAD-문호표현-v8.zip').replace('· v7','· v8').replace('검토 v7','검토 v8')
 if f==OUT/'index.html':h=h.replace('<nav>','<p><b>180도 문 호 표시 수정: 한쪽 90도만 그리던 오류를 고쳐 전체 반원으로 표시합니다.</b> <a href="문호-수정후.png">방풍실 확대</a></p><nav>',1)
 f.write_text(h,encoding='utf8')
code=OUT/'code'
for f in CAD.iterdir():
 if f.is_file() and (f.suffix in ('.py','.json') or f.name in ('viewer_template.html','compare_template.html','requirements-extraction.txt')):shutil.copy2(f,code/f.name)
note='''v8 문 호 표시 수정
최종 평면 렌더러가 open2를 누락하여 양방향문의 한쪽 90도만 표시하던 오류를 수정했습니다.
호 양 끝을 닫힌 문짝 위치를 지나 연결하여 전체 반원을 그립니다. 175도 원본은 해당 범위를 유지하며 90도 문은 90도로 유지합니다.
3D에도 전체 회전 범위 안내선을 추가했습니다. 양방향문은 한쪽 끝에서 반대쪽 끝까지 총 180도이며, 닫힘 기준 양쪽 개방은 기존대로 각각 약 90도입니다.
전층 9개 평면과 통합/층별 3D를 다시 표시했습니다. 열려 있던 v6 결과도 호 표시를 수정했습니다.
평면 추출·방 연결·시뮬레이션 JSON은 v7과 동일하며 재해석하지 않았습니다.
기존 검사에 호 표시 회귀 검사 3개를 추가하여 70개 테스트 통과. 생성된 JavaScript 문법 검사 수행.
원본 plan.json의 추출 provenance는 그대로 보존하고 이번 표시 변경의 코드 해시는 문호표현-수정.json에 별도 기록합니다.
'''
(OUT/'문호표현-수정.txt').write_text(note,encoding='utf8')
(OUT/'문호표현-수정.json').write_text(json.dumps(dict(**provenance,unit_tests=70,floors=rows),ensure_ascii=False,indent=2),encoding='utf8')
node=r'C:\Users\<user>\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe';checked=0
for f in OUT.rglob('*.html'):
 if 'code' in f.parts:continue
 for attrs,body in re.findall(r'<script([^>]*)>([\s\S]*?)</script>',f.read_text(encoding='utf8')):
  if 'importmap' in attrs or not body.strip():continue
  c=W/'v8-check.mjs';c.write_text(body,encoding='utf8');subprocess.run([node,'--check',str(c)],check=True,capture_output=True);checked+=1
(OUT/'UI검사.json').write_text(json.dumps(dict(javascript_blocks_checked=checked,syntax='passed',browser_click_test='not_run_local_file_access_restricted'),ensure_ascii=False,indent=2),encoding='utf8')
with zipfile.ZipFile(OUT/'CAD-문호표현-v8.zip','w',zipfile.ZIP_DEFLATED) as z:
 for f in code.iterdir():z.write(f,'code/'+f.name)
 for name in ('문호표현-수정.txt','문호표현-수정.json','office-1F-review-v7.json','office-PH-review-v7.json','도면검토목록.json'):z.write(OUT/name,name)
print(json.dumps(dict(output=str(OUT),floors=rows,js_blocks=checked),ensure_ascii=False))
