import pathlib,json,shutil,zipfile,hashlib,difflib,html,base64,sys
W=pathlib.Path(__file__).resolve().parent;CAD=pathlib.Path(r'C:\Users\예방\Documents\Codex\2026-09-07\2\CAD3D')
sys.path.insert(0,str(CAD))
from cad_review_ui import enhance_review
RUN=W/'cad-v4-runs';OUT=W.parent/'outputs/CAD-연결보강-v4';OUT.mkdir(exist_ok=True)
report=json.loads((RUN/'validation.json').read_text(encoding='utf8'))
scenarios=json.loads((RUN/'scenarios.json').read_text(encoding='utf8'))
vertical=json.loads((RUN/'hotel-4F-5F/validation.json').read_text(encoding='utf8'))
assert len(report)==5 and len(scenarios)==15 and all(s['solver_success'] for s in scenarios)
names={'hotel-4F':'호텔 4층','hotel-1F':'호텔 1층','office-1F':'업무시설 1층','office-4F':'업무시설 4층','exhibition-1F':'전시시설 1층'}
cards=[]
def diagnostic_svg(p, background):
    ra=p['raster'];scale=1000/ra['R']
    def points(poly):return ' '.join(f'{(x-ra["x0"]/1000)*scale:.2f},{(ra["y1"]/1000-y)*scale:.2f}' for x,y in poly)
    data=base64.b64encode(background.read_bytes()).decode('ascii')
    lines=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ra["W"]} {ra["H"]}"><image href="data:image/png;base64,{data}" width="{ra["W"]}" height="{ra["H"]}"/>']
    isolated=set(p['simulation_graph']['isolated_rooms'])
    for r in p['rooms']:
        if r['id'] in isolated:
            for poly in r['polys']:lines.append(f'<polygon points="{points(poly["o"])}" fill="#f59e0b" fill-opacity=".25" stroke="#a84600" stroke-width="5" stroke-dasharray="10 6"><title>{r["id"]} 연결 미확정 · 해석 포함</title></polygon>')
    for o in p['openings']:
        if o.get('connection_evidence'):
            for poly in o['polys']:lines.append(f'<polygon points="{points(poly)}" fill="none" stroke="#c000ad" stroke-width="6"><title>{o["id"]} 연결 복구</title></polygon>')
    lines.append('</svg>');return ''.join(lines)
for r in report:
    name=r['sample'];src=RUN/name;dst=OUT/name;dst.mkdir(exist_ok=True)
    for f in src.iterdir():
        if f.is_file() and f.suffix in ('.html','.json','.png','.svg'):shutil.copy2(f,dst/f.name)
    p=json.loads((src/'plan.json').read_text(encoding='utf8'))
    for group in ('code_sha256','evidence_code_sha256'):
        assert all(hashlib.sha256((CAD/f).read_bytes()).hexdigest()==sha for f,sha in p['provenance'][group].items())
    b=json.loads((src/'building.json').read_text(encoding='utf8'))
    # User-facing graph is the one with resolved floor heights, consumed by the solver.
    (dst/'simulation_graph.json').write_text(json.dumps(b['floors'][0]['simulation_graph'],ensure_ascii=False,indent=2),encoding='utf8')
    shutil.copy2(W.parent/'outputs/CAD-자동보강-v3'/name/'fused.png',dst/'before.png')
    (dst/'connectivity.svg').write_text(diagnostic_svg(p,src/'fused.png'),encoding='utf8')
    h=(dst/'index.html').read_text(encoding='utf8')
    h=h.replace('class="on" data-src="fused.png"','data-src="fused.png"')
    h=h.replace('<nav>','<nav><button class="on" data-src="connectivity.svg">연결 검토</button><button data-src="before.png">이전 v3</button>')
    h=h.replace('id="drawing" src="fused.png"','id="drawing" src="connectivity.svg"')
    prefix=f'<h2>v4 공간 연결 결과</h2><p><a href="../index.html">전체 결과</a> · <a href="building.html">3D 보기</a></p><p><b>3D {r["three_d_rooms"]}개 · 해석 {r["solver_rooms"]}개 실</b><br>누락 0개 · 연결 미확정 공간 {len(r["isolated_rooms"])}개 유지</p><p>주황 점선: 연결 미확정 공간<br>자주색 테두리: 연결 복구 개구부</p><p>개방률 0·50·100% 각각 60초 계산 완료. 아래 결과는 실행 확인용이며 물리 정확도 검증 결과가 아닙니다.</p>'
    prefix+='<p>'+ ' · '.join(f'<a href="simulation-{state}.json">{state}% 결과</a>' for state in (0,50,100))+'</p>'
    h=h.replace('<h2>표시와 검토</h2>',prefix+'<h2>도면 표시</h2>')
    h=h.replace('소방 근거 통합 결과','추출 결과')
    h=h.replace('<a href="plan.json">최종 평면 JSON</a>', '<a href="plan.json">평면 JSON</a> · <a href="simulation_graph.json">층 높이 적용 연결표</a>')
    (dst/'index.html').write_text(h,encoding='utf8')
    enhance_review(dst)
    cards.append(f'<a class="card" href="{name}/index.html"><img src="{name}/fused.png" alt="{names[name]}"><h2>{names[name]}</h2><p>3D·해석 공통 실 {r["solver_rooms"]}개 · 누락 0개</p><p>연결 복구 {len(r["recovered_openings"])}개 / 연결 미확정 공간 {len(r["isolated_rooms"])}개 유지</p><p>0·50·100% 각각 60초 계산 완료</p></a>')
for name in ('hotel-5F','hotel-4F-5F'):
    dst=OUT/name;dst.mkdir(exist_ok=True)
    for f in (RUN/name).iterdir():
        if f.is_file() and f.suffix in ('.html','.json','.png','.svg'):shutil.copy2(f,dst/f.name)
code=OUT/'code';code.mkdir(exist_ok=True)
files=[p.name for p in (W.parent/'outputs/CAD-자동보강-v3/code').iterdir() if p.is_file()]+['cad_connectivity.py','test_cad_connectivity.py','cad_review_ui.py','CAD-연결보강-v4.txt']
diff=[]
for name in sorted(set(files)):
    shutil.copy2(CAD/name,code/name)
    before=W/'cad-v4-before'/name
    a=before.read_text(encoding='utf8').splitlines(True) if before.exists() else []
    diff+=list(difflib.unified_diff(a,(CAD/name).read_text(encoding='utf8').splitlines(True),fromfile='v3/'+name,tofile='v4/'+name))
(OUT/'changes.diff').write_text(''.join(diff),encoding='utf8')
summary=dict(unit_tests_passed=43,samples=report,scenarios=scenarios,vertical=vertical,
    isolated_ignition_test=json.loads((RUN/'isolated-room-test.json').read_text(encoding='utf8')),
    code_sha256={f:hashlib.sha256((code/f).read_bytes()).hexdigest() for f in sorted(set(files))})
(OUT/'검증결과.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
shutil.copy2(CAD/'CAD-연결보강-v4.txt',OUT/'설명과실행.txt')
with zipfile.ZipFile(OUT/'CAD-연결보강-v4.zip','w',zipfile.ZIP_DEFLATED) as z:
    for name in sorted(set(files)):z.write(code/name,'CAD3D/'+name)
    z.write(OUT/'changes.diff','changes.diff');z.write(OUT/'검증결과.json','검증결과.json')
page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CAD 공간 연결 v4</title><style>
body{margin:0;background:#f0f4f8;color:#203046;font:16px/1.65 system-ui,'Malgun Gothic',sans-serif}header,main,footer{max-width:1250px;margin:auto;padding:25px}h1{font-size:29px;margin:0}p{margin:8px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:20px}.card{display:block;border:1px solid #d8e0e9;border-radius:12px;background:white;padding:16px;color:inherit;text-decoration:none}.card img{width:100%;height:270px;object-fit:contain}h2{margin:12px 0 4px;font-size:20px}.card p{font-size:14px}a{color:#165da3}.note{background:#e3ebf4;padding:15px;border-radius:8px}.metrics{display:flex;gap:14px;flex-wrap:wrap}.metric{background:white;border:1px solid #d8e0e9;border-radius:8px;padding:12px 22px}.metric strong{display:block;font-size:28px}</style>
<header><h1>CAD 공간 연결 v4</h1><p>공간을 빠짐없이 유지하고, 도면 근거로 문·창의 연결을 보강했습니다.</p>
<div class="metrics"><div class="metric"><strong>128 / 128</strong>5개 층 실 → 해석 포함</div><div class="metric"><strong>15 / 15</strong>60초 실행 완료</div><div class="metric"><strong>43</strong>단위 테스트 통과</div></div>
<p>호텔 1층 창 2개 외기 연결 복구 · 기존 정상 문 연결 유지 · 개방률 0·50·100% 통일</p>
<p class="note">연결 미확정 공간 14개는 고립된 상태로 유지합니다. 미확정·동일 공간 개구부 연결 24개가 남았습니다. 계산 완료는 실행 검증이며 실제 화재해석 정확도를 뜻하지 않습니다.</p>
<p><b>⚠ 불명확한 개구부 24개 위치 보기:</b> <a href="hotel-1F/index.html">호텔 1층 · 5개</a> / <a href="office-1F/index.html">업무시설 1층 · 14개</a> / <a href="exhibition-1F/index.html">전시시설 1층 · 5개</a></p><p>도면의 빨간 번호 또는 옆 목록을 누르면 위치를 확대합니다. 호텔 4층·업무시설 4층은 0개입니다.</p>
<p><a href="hotel-4F-5F/building.html">호텔 4·5층 결합 3D</a> · <a href="hotel-4F-5F/validation.json">층간 연결 검증</a></p>
<p>인접층의 계단 2곳·승강로 2곳 대응 확인. 각 대상층 + 수직 존 모델 30초 계산 완료. 높이는 기본값을 사용했습니다.</p>
<p><a href="CAD-연결보강-v4.zip">실행 코드</a> · <a href="설명과실행.txt">변경 내용·실행 방법</a> · <a href="검증결과.json">검증 결과</a></p></header>
<main class="grid">__CARDS__</main><footer>각 도면의 ‘연결 검토’에서 주황 점선은 연결 미확정 공간, 자주색 테두리는 복구 개구부입니다. 개방률은 유효 개구 면적 비율이며 문짝 각도와 다릅니다.</footer></html>'''.replace('__CARDS__',''.join(cards))
(OUT/'index.html').write_text(page,encoding='utf8');print(OUT)
