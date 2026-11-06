import json,pathlib,sys,re,html,shutil,subprocess
W=pathlib.Path(__file__).resolve().parent;C=pathlib.Path('C:/Users/<user>/Documents/Codex/2026-09-07/2/CAD3D');sys.path[:0]=[str(W/'cad-deps'),str(C)]
from cad_evidence import geometry
from cad_model_transport import road_faces
from cad_stage1_report import STYLE
O=W.parent/'outputs/CAD-모델링-v10';V=W.parent/'outputs/CAD-평면연결-v9'
b=json.loads((O/'building.json').read_text(encoding='utf8'));audit=json.loads((O/'위치검사.json').read_text(encoding='utf8'))
checks=[];cards=[];total_steps=0
for f in b['floors']:
 p=json.loads((V/('office-'+f['name'])/'plan.json').read_text(encoding='utf8'));r=p['raster']
 def xy(q):return ((q[0]*1000-r['x0'])/r['R'],(r['y1']-q[1]*1000)/r['R'])
 def poly(points,color,opacity=.12,dash=''):
  pp=' '.join(f'{x:.3f},{y:.3f}' for x,y in map(xy,points));return f'<polygon points="{pp}" fill="{color}" fill-opacity="{opacity}" stroke="{color}" stroke-width="3" stroke-dasharray="{dash}"/>'
 overlay=[]
 for c in p['cores']:
  x,y,w,h=c['cx'],c['cy'],c['w']/2,c['h']/2
  overlay.append(poly([[x-w,y-h],[x+w,y-h],[x+w,y+h],[x-w,y+h]],'#e34d59',.04,'8 6'))
 for c in f['transport']:
  region=geometry(c['region']);max_out=0
  for m in c['meshes']:
   max_out=max(max_out,geometry(m['polys']).difference(region).area)
   assert m['z1']>m['z0'] and m['z1']<=c['rise_m']+.001
  assert max_out<1e-7
  if c['meshes']:assert abs(max(s['z1'] for s in c['meshes'])-c['rise_m'])<1e-7
  total_steps+=len(c['meshes'])
  for part in c['room_region'] or []:
   raw=[[(q[0]+b['origin'][0]-f['shift'][0])/f['scale'],(q[1]+b['origin'][1]-f['shift'][1])/f['scale']] for q in part['o']]
   overlay.append(poly(raw,'#008984',.04))
  checks.append(dict(floor=f['name'],id=c['id'],step_meshes=len(c['meshes']),outside_region_m2=max_out,rise_m=c['rise_m']))
 for ramp in p.get('ramps',[]):
  for part in ramp['polys']:overlay.append(poly(part['o'],'#e34d59',.05,'10 6'))
  for part in road_faces(p,ramp)['polys']:overlay.append(poly(part['o'],'#d28800',.18))
 source=f['name']+'-source.svg';shutil.copy2(V/('office-'+f['name'])/'source.svg',O/source)
 cards.append(f'<section class="card"><h2>{f["name"]}</h2><p>빨강 점선: 종전 기호 범위 / 청록: 추출된 독립 실 경계 / 주황: 벽면 기준 차량 램프</p><div style="overflow:auto;max-height:80vh"><svg viewBox="0 0 {r["W"]} {r["H"]}" style="width:180%;min-width:900px"><image href="{source}" width="{r["W"]}" height="{r["H"]}"/>{"".join(overlay)}</svg></div></section>')
(O/'위치대조.html').write_text(f'<!doctype html><html lang="ko"><meta charset="utf-8"><title>계단·램프 원본 대조</title><style>{STYLE}</style><header><h1>계단·램프 위치 대조</h1><a href="index.html">3D 모델</a><p>계단 기호 박스와 계단실 경계는 서로 다릅니다. 건물 좌표 변환 오차는 0.001m 미만입니다. 램프는 양쪽 벽면까지 각각 약 0.30m 넓혔으며 확인된 두 경계의 공통 곡선 구간을 표시합니다. 계단의 단수·참과 램프 경사는 시각화용 근사입니다.</p></header><main>{"".join(cards)}</main></html>',encoding='utf8')
node=pathlib.Path('C:/Users/<user>/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
s=(O/'index.html').read_text(encoding='utf8');scripts=re.findall(r'<script([^>]*)>(.*?)</script>',s,re.S)
for i,(attr,body) in enumerate(scripts):
 if 'importmap' in attr:json.loads(body);continue
 file=W/f'v10-script-{i}.mjs';file.write_text(body,encoding='utf8');subprocess.run([str(node),'--check',str(file)],check=True,capture_output=True)
assert 'syncLabels();applyCeil();syncTransport();' in s
report=dict(floors=len(b['floors']),cores=len(checks),stair_meshes=total_steps,vertical_links=len(b['vertical_connections']),max_coordinate_error_m=max(x.get('coordinate_error_m',0) for x in audit),checks=checks,js_syntax='pass',browser_runtime='not_verified',physics='not_evaluated',assumptions=['계단 단수·계단참 형상은 기존 웹앱 방식의 근사','램프 경사 10%·방향은 표시용 가정, 조절 가능','램프의 상단 층 연결은 미확정'])
(O/'검증결과.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in report.items() if k!='checks'},ensure_ascii=False))
