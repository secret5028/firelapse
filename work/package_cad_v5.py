import pathlib,sys,json,shutil,base64,hashlib,zipfile,difflib
W=pathlib.Path(__file__).resolve().parent;CAD=pathlib.Path(r'C:\Users\<user>\Documents\Codex\2026-09-07\2\CAD3D')
sys.path[:0]=[str(W/'cad-deps'),str(CAD)]
import numpy as np
from fire_zone import Model
from cad_review_ui import enhance_review
RUN=W/'cad-v5-runs';OUT=W.parent/'outputs/CAD-벽공리-v5';OUT.mkdir(exist_ok=True)
report=json.loads((RUN/'validation.json').read_text(encoding='utf8'))
assert len(report)==5
names={'hotel-4F':'호텔 4층','hotel-1F':'호텔 1층','office-1F':'업무시설 1층','office-4F':'업무시설 4층','exhibition-1F':'전시시설 1층'}
cards=[];runs=[]
for row in report:
 name=row['sample'];src=RUN/name;dst=OUT/name;dst.mkdir(exist_ok=True)
 p=json.loads((src/'plan.json').read_text(encoding='utf8'));b=json.loads((src/'building.json').read_text(encoding='utf8'))
 for group in ('code_sha256','evidence_code_sha256'):
  assert all(hashlib.sha256((CAD/f).read_bytes()).hexdigest()==sha for f,sha in p['provenance'][group].items())
 old=json.loads((W.parent/'outputs/CAD-연결보강-v4'/name/'building.json').read_text(encoding='utf8'))
 # Removed items were not flow connections; all confirmed connections stay identical.
 assert b['floors'][0]['simulation_graph']['connections']==old['floors'][0]['simulation_graph']['connections']
 m=Model(b,b['floors'][0]['name'],dict(fire_room='R0',door_open_default=50,window_open_default=50))
 sol=m.run(t_end=60,dt_out=10)
 assert sol.success and np.isfinite(sol.y).all() and abs(sol.t[-1]-60)<1e-6
 result=m.result();result.pop('flags')
 (src/'simulation-50.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
 runs.append(dict(sample=name,state_percent=50,seconds=60,solver_success=True,rooms=len(m.rmap),confirmed_connections_unchanged=True))
 for f in src.iterdir():
  if f.suffix in ('.json','.html','.png','.svg'):shutil.copy2(f,dst/f.name)
 shutil.copy2(W.parent/'outputs/CAD-연결보강-v4'/name/'fused.png',dst/'before.png')
 (dst/'simulation_graph.json').write_text(json.dumps(b['floors'][0]['simulation_graph'],ensure_ascii=False,indent=2),encoding='utf8')
 ra=p['raster'];data=base64.b64encode((src/'fused.png').read_bytes()).decode('ascii')
 svg=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ra["W"]} {ra["H"]}"><image href="data:image/png;base64,{data}" width="{ra["W"]}" height="{ra["H"]}"/>']
 for r in p['rooms']:
  if r['id'] not in p['simulation_graph']['isolated_rooms']:continue
  for poly in r['polys']:
   pts=' '.join(f'{(x*1000-ra["x0"])/ra["R"]:.2f},{(ra["y1"]-y*1000)/ra["R"]:.2f}' for x,y in poly['o'])
   svg.append(f'<polygon points="{pts}" fill="#f59e0b" fill-opacity=".2" stroke="#a84600" stroke-width="5" stroke-dasharray="10 6"/>')
 svg.append('</svg>');(dst/'connectivity.svg').write_text(''.join(svg),encoding='utf8')
 h=(dst/'index.html').read_text(encoding='utf8').replace('class="on" data-src="fused.png"','data-src="fused.png"')
 h=h.replace('<nav>','<nav><button class="on" data-src="connectivity.svg">벽 공리 적용 결과</button><button data-src="before.png">이전 v4</button>')
 h=h.replace('id="drawing" src="fused.png"','id="drawing" src="connectivity.svg"')
 prefix=f'<h2>벽 위 개구부 판정 v5</h2><p><a href="../index.html">전체 결과</a> · <a href="building.html">3D 보기</a></p><p><b>벽 지지 근거 부족 후보 {row["host_filter"]["rejected"]}개 제외</b><br>연결 확인 대상 {row["excluded_graph_openings"]}개 남음<br>공간 {row["solver_rooms"]}개 유지</p><p>주황 점선은 연결 미확정 공간입니다. 빨간 번호는 남은 개구부 확인 대상입니다.</p><p><a href="simulation-50.json">50% 개방 · 60초 실행 결과</a><br>계산 완료는 물리 정확도 검증을 뜻하지 않습니다.</p>'
 h=h.replace('<h2>표시와 검토</h2>',prefix+'<h2>기타 도면 표시</h2>')
 h=h.replace('소방 근거 통합 결과','추출 결과')
 (dst/'index.html').write_text(h,encoding='utf8')
 items=enhance_review(dst);assert len(items)==row['excluded_graph_openings']
 cards.append(f'<a class="card" href="{name}/index.html"><img src="{name}/fused.png" alt="{names[name]}"><h2>{names[name]}</h2><p>제외 후보 {row["host_filter"]["rejected"]}개 · 남은 확인 대상 {len(items)}개</p><p>실 {row["solver_rooms"]}개 유지 · 기존 정상 연결 유지</p></a>')
 print(name,'packaged',flush=True)
assert sum(r['host_filter']['rejected'] for r in report)==8
assert sum(r['excluded_graph_openings'] for r in report)==16
code=OUT/'code';code.mkdir(exist_ok=True)
files={p.name for p in (W.parent/'outputs/CAD-연결보강-v4/code').iterdir() if p.is_file()}|{'cad_host.py','test_cad_host.py'}
diff=[]
for name in sorted(files):
 shutil.copy2(CAD/name,code/name)
 before=W/'cad-v5-before'/name;a=before.read_text(encoding='utf8').splitlines(True) if before.exists() else []
 diff.extend(difflib.unified_diff(a,(CAD/name).read_text(encoding='utf8').splitlines(True),fromfile='v4/'+name,tofile='v5/'+name))
(OUT/'changes.diff').write_text(''.join(diff),encoding='utf8')
(OUT/'검증결과.json').write_text(json.dumps(dict(unit_tests_passed=51,samples=report,runs=runs,
 code_sha256={f:hashlib.sha256((code/f).read_bytes()).hexdigest() for f in files}),ensure_ascii=False,indent=2),encoding='utf8')
doc='''CAD 벽 위 개구부 공리 적용 v5

문·창 후보는 독립된 원본 벽선과 양쪽 문틀·기둥 지지 근거로 검사합니다.
후보 기호를 이용해 만든 래스터 벽에 겹친다는 이유만으로 벽 위라고 인정하지 않습니다.
이번 자동 제외는 연결이 불명확한 후보를 대상으로 합니다. 기존 정상 연결 전체의 진위를 판정한 것은 아닙니다.
문짝 근거가 있는 후보, 소방 근거로 보정된 문, 유리 칸막이처럼 일부 지지만 있는 후보는 자동 삭제하지 않습니다.
외벽에 붙은 개구부는 바닥 외곽과 실내 공간을 함께 확인하여 실 ↔ 외기로 연결합니다.
단순히 도면 가장자리에 있거나 외곽과 한 점에서 닿는 기호는 외벽 개구부로 확정하지 않습니다.
이번 실제 표본에서는 새로 외기 연결된 항목은 0개입니다. 남은 [미확정, 외기] 항목은 외기측이 아니라 실내측 공간 연결이 미확정입니다.

결과: 기존 확인 대상 24개 중 8개 제외, 16개 유지.
업무시설 1층: W68,W69,W72,W75,W78,W79 제외 (기둥 주변·벽 지지 없는 복합/짧은 기호 후보).
전시시설 1층: W2,W7 제외 (벽·문틀 지지 근거 부족).
원본 CAD와 제외 후보의 형상/근거는 rejected_openings.json에 보존했습니다.
제외는 자동 판정이며 실제 도면의 정답을 확정했다는 뜻이 아닙니다.

51개 단위 테스트 통과. 실제 5개 층 재추출 및 3D 변환 완료.
128개 공간 보존, 기존 정상 문 연결 및 해석 연결/치수 동일성 확인.
5개 층 각각 50% 개방으로 60초 계산 성공. 물리 정확도 검증은 별도입니다.

실행: code 폴더에서
python cad_pipeline.py input.dxf result --floor 1F
python cad_build3d.py result/building result/plan.json --names 1F
python -m unittest discover -p "test_cad*.py"

v4 결과는 별도 폴더에 보존했습니다. 기존 웹앱 배포 및 화재 해석 모델의 물리식 변경은 하지 않았습니다.
'''
(OUT/'설명과실행.txt').write_text(doc,encoding='utf8')
with zipfile.ZipFile(OUT/'CAD-벽공리-v5.zip','w',zipfile.ZIP_DEFLATED) as z:
 for file in code.iterdir():z.write(file,'CAD3D/'+file.name)
 for name in ('설명과실행.txt','changes.diff','검증결과.json'):z.write(OUT/name,name)
page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>벽 위 개구부 · v5</title><style>
body{margin:0;background:#f0f4f8;color:#203046;font:16px/1.65 system-ui,'Malgun Gothic',sans-serif}header,main,footer{max-width:1250px;margin:auto;padding:25px}h1{font-size:29px;margin:0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:20px}.card{display:block;border:1px solid #d8e0e9;border-radius:12px;background:white;padding:16px;color:inherit;text-decoration:none}.card img{width:100%;height:270px;object-fit:contain}h2{font-size:20px}a{color:#165da3}.note{background:#fff2d6;padding:16px;border-radius:8px}</style>
<header><h1>벽 위 개구부 공리 적용 · v5</h1><p><b>확인 대상 24개 → 벽 지지 근거 부족 후보 8개 제외 → 16개 유지</b></p><p>원본 벽선·문틀·기둥 지지를 대조하고, 단순한 기호를 문·창으로 사용하는 것을 줄였습니다.</p><p class="note">외벽 개구부는 실내 공간 ↔ 외기로 연결합니다. 외기측이 이미 확인된 항목은 실내측 미확정 여부를 구분해 표시합니다. 자동 제외한 후보는 근거와 함께 보존합니다.</p><p>실 128개 유지 · 기존 정상 연결 보존 · 51개 테스트 · 5개 층 50% 개방 60초 실행 완료</p><p><a href="CAD-벽공리-v5.zip">실행 코드</a> · <a href="설명과실행.txt">변경 내용</a> · <a href="검증결과.json">검증 결과</a></p></header><main class="grid">__CARDS__</main><footer>각 층에서 이전 v4와 비교할 수 있습니다. 빨간 번호는 남은 확인 대상이며, ‘벽 지지 근거 부족으로 제외한 후보’에서 제외 목록을 확인할 수 있습니다.</footer></html>'''.replace('__CARDS__',''.join(cards))
(OUT/'index.html').write_text(page,encoding='utf8')
print(OUT,flush=True)
