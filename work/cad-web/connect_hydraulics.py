from pathlib import Path
import json
from hydraulic_embed import embed_hydraulics
root=Path('work')
for name,alias,canvas in [('cad_viewer.js','T','renderer.domElement'),('industrial.js','THREE','canvas')]:
 p=root/name;s=p.read_text('utf-8')
 if 'installHydraulicView' not in s:s+=f'\nwindow.installHydraulicView?.({alias},scene,camera,{canvas});\n'
 p.write_text(s,'utf-8')
p=root/'folder_review.html';s=p.read_text('utf-8')
if 'installHydraulicView' not in s:s=s.replace('const cv=renderer.domElement;', 'window.installHydraulicView?.(T,scene,camera,renderer.domElement);const cv=renderer.domElement;')
p.write_text(s,'utf-8')
# Deliberately synthetic example in its own building, never applied to user drawings.
net={'version':1,'buildingId':'hydraulic-training-example-v1','name':'수리 계산 기능 예제 · 실제 건물 아님','reviewed':True,'inlet':'I','active':['A','B'],
 'nodes':[
 {'id':'I','type':'inlet','name':'예제 송수구','x':0,'y':1,'z':0},
 {'id':'J','type':'junction','name':'분기점','x':10,'y':4,'z':0},
 {'id':'A','type':'outlet','name':'예제 살수 말단 A','x':20,'y':8,'z':-5,'flowLpm':100,'residualMpa':.1},
 {'id':'B','type':'outlet','name':'예제 살수 말단 B','x':20,'y':8,'z':5,'flowLpm':100,'residualMpa':.1}],
 'pipes':[
 {'id':'P1','from':'I','to':'J','lengthM':20,'diameterMm':65,'c':120,'k':2,'state':'open','direction':'forward','reviewed':True},
 {'id':'P2','from':'J','to':'A','lengthM':15,'diameterMm':40,'c':120,'k':3,'state':'open','direction':'both','reviewed':True},
 {'id':'P3','from':'J','to':'B','lengthM':30,'diameterMm':40,'c':120,'k':3,'state':'open','direction':'both','reviewed':True}]}
(root/'hydraulic-example.json').write_text(json.dumps(net,ensure_ascii=False,indent=2),'utf-8')
page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>소방 크로키 업 · 송수구 계산 기능 예제</title><style>body{background:#102637;color:#e5f1ff;font:16px sans-serif;margin:40px;line-height:1.8}h1{font-size:24px}p{max-width:550px}button{font-size:16px;padding:14px;background:#175885;color:white;border:0;border-radius:9px}</style><body><h1>송수구 · 방수 말단 · 필요 송수압</h1><p>기능 확인용 가상 계통입니다. 입력된 유량·압력·관경·C·손실계수는 실제 건물의 기준값이 아닙니다.</p><p>오른쪽 계통도에서 송수구 또는 말단을 선택하세요. 두 말단을 함께 선택했을 때의 공통 배관 유량과 필요 송수압을 확인할 수 있습니다. 계통 편집에서 길이·내경·높이·밸브 상태를 바꿔 비교하세요.</p><button onclick="HydraulicUI.open()">계통 검토 열기</button><script>window.HYDRAULIC_INITIAL='''+json.dumps(net,ensure_ascii=False)+''';</script></body></html>'''
page=embed_hydraulics(page,root,net['buildingId'],net['name'])
page=page.replace('</body>','<script>HydraulicUI.open()</script></body>')
Path('outputs/소방-송수구-수리계산-기능예제.html').write_text(page,'utf-8')
print('Connected shared panel and created isolated training example')
