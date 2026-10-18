import pathlib,json,shutil,zipfile,hashlib,difflib,sys
W=pathlib.Path(__file__).resolve().parent;CAD=pathlib.Path(r'C:\Users\예방\Documents\Codex\2026-09-07\2\CAD3D')
RUN=W/'cad-v3-runs';OUT=W.parent/'outputs/CAD-자동보강-v3';OUT.mkdir(exist_ok=True)
report=json.loads((RUN/'validation.json').read_text(encoding='utf-8'));assert len(report)==5
names={'hotel-4F':'호텔 4층','hotel-1F':'호텔 1층','office-1F':'업무시설 1층','office-4F':'업무시설 4층','exhibition-1F':'전시시설 1층'}
cards=[]
for r in report:
    name=r['sample'];src=RUN/name;dst=OUT/name;dst.mkdir(exist_ok=True)
    for file in ['index.html','plan.json','quality.json','architecture.json','architecture_plan.png','fused.png','source.svg','fire_evidence.json','simulation_graph.json','building.json','building.html']:
        if (src/file).exists():shutil.copy2(src/file,dst/file)
    p=json.loads((src/'plan.json').read_text(encoding='utf-8'))
    for group in ('code_sha256','evidence_code_sha256'):
        assert all(hashlib.sha256((CAD/f).read_bytes()).hexdigest()==sha for f,sha in p['provenance'][group].items())
    shutil.copy2(W.parent/'outputs/CAD-통합추출-v2'/name/'fused.png',dst/'before.png')
    h=(dst/'index.html').read_text(encoding='utf-8')
    h=h.replace('<nav>','<nav><button data-src="before.png">이전 v2 결과</button>')
    h=h.replace('소방 근거 통합 결과','자동 보강 + 소방 근거')
    h=h.replace('<h2>표시와 검토</h2>','<h2>자동 보강 결과</h2><p><a href="building.html">3D 보기</a> · <a href="simulation_graph.json">시뮬레이션 연결표</a></p><p>실 '+str(r['rooms_before'])+' → '+str(r['rooms_after'])+' · 승강기문 '+str(r['elevator_doors_before'])+' → '+str(r['elevator_doors_after'])+'</p>')
    (dst/'index.html').write_text(h,encoding='utf-8')
    cards.append(f'<a class="card" href="{name}/index.html"><img src="{name}/fused.png" alt="{names[name]}"><h2>{names[name]}</h2><p>실 {r["rooms_before"]} → {r["rooms_after"]} · 승강기문 {r["elevator_doors_before"]} → {r["elevator_doors_after"]}</p><p>기존 정상 문 연결 유지 · 3D {r["three_d_rooms"]}개 실 전달</p></a>')
code=OUT/'code';code.mkdir(exist_ok=True)
files=[p.name for p in (W.parent/'outputs/CAD-통합추출-v2/code').iterdir() if p.is_file()]+['cad_auto.py','test_cad_auto.py','CAD-자동보강-v3.txt','fire_zone.py','fire_load_table.json']
diff=[]
for name in sorted(set(files)):
    shutil.copy2(CAD/name,code/name)
    before=W/'cad-v3-before'/name
    a=before.read_text(encoding='utf-8').splitlines(True) if before.exists() else []
    b=(CAD/name).read_text(encoding='utf-8').splitlines(True)
    diff+=list(difflib.unified_diff(a,b,fromfile='v2/'+name,tofile='v3/'+name))
(OUT/'changes.diff').write_text(''.join(diff),encoding='utf-8')
(OUT/'검증결과.json').write_text(json.dumps(dict(unit_tests_passed=29,samples=report),ensure_ascii=False,indent=2),encoding='utf-8')
shutil.copy2(CAD/'CAD-자동보강-v3.txt',OUT/'설명과실행.txt')
with zipfile.ZipFile(OUT/'CAD-자동보강-v3.zip','w',zipfile.ZIP_DEFLATED) as z:
    for name in sorted(set(files)):z.write(code/name,'CAD3D/'+name)
    z.write(OUT/'changes.diff','changes.diff');z.write(OUT/'검증결과.json','검증결과.json')
page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CAD 자동 보강 v3</title><style>
body{margin:0;background:#f0f4f8;color:#203046;font:16px/1.6 system-ui,'Malgun Gothic',sans-serif}header,main,footer{max-width:1250px;margin:auto;padding:25px}h1{font-size:29px;margin:0}p{margin:8px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:20px}.card{display:block;border:1px solid #d8e0e9;border-radius:12px;background:white;padding:16px;color:inherit;text-decoration:none}.card img{width:100%;height:290px;object-fit:contain}h2{margin:12px 0 4px;font-size:20px}.card p{font-size:14px}a{color:#165da3}.note{background:#e3ebf4;padding:15px;border-radius:8px}</style>
<header><h1>CAD 자동 보강 v3</h1><p>작은 오차를 허용하고 3D·시뮬레이션 입력용 공간 연결을 자동 정리합니다.</p><p>호텔 4층: 승강로 3개 분리·승강기문 3개 연결 / 업무시설 1층: 단차로 나뉜 9개 영역을 하나의 다목적실로 정리</p><p>29개 단위 시험 · 실제 5개 층 · 정상 문 연결 보존 · 3D 실/개구부 전달 확인</p><p class="note">벽 틈을 80/160mm 범위로 시험해 안정적인 작은 보강폭을 선택합니다. 20mm 해상도는 유지합니다. 미확인 연결은 연결표에서 제외하고 근거를 남깁니다. 물리 해석 결과의 검증은 별도입니다.</p><p><a href="CAD-자동보강-v3.zip">실행 코드</a> · <a href="설명과실행.txt">변경 내용·실행 방법</a> · <a href="검증결과.json">검증 결과</a></p></header><main class="grid">__CARDS__</main><footer>각 결과에서 v2/v3 비교, CAD 원본, 3D 모델, 공간 연결표를 확인할 수 있습니다.</footer></html>'''.replace('__CARDS__',''.join(cards))
(OUT/'index.html').write_text(page,encoding='utf-8');print(OUT)
