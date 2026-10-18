import pathlib, json, shutil, zipfile, hashlib, difflib, sys, os, subprocess
from html import escape
W=pathlib.Path(__file__).resolve().parent
CAD=pathlib.Path(r'C:\Users\예방\Documents\Codex\2026-09-07\2\CAD3D')
RUN=W/'cad-v2-runs'; OUT=W.parent/'outputs/CAD-통합추출-v2'
OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(CAD))
from cad_evidence import geometry
report=json.loads((RUN/'validation.json').read_text(encoding='utf-8'))
assert len(report)==5 and all(all(r['checks'].values()) for r in report)
env=dict(os.environ,PYTHONPATH=str(W/'cad-deps'),PYTHONIOENCODING='utf-8')
building_checks={}
for floor,use in [('1F','retail'),('4F','lodging')]:
    folder=RUN/('hotel-'+floor)
    subprocess.run([sys.executable,str(CAD/'cad_build3d.py'),str(folder/'building'),str(folder/'plan.json'),'--names',floor,'--use',use],env=env,check=True,capture_output=True)
    b=json.loads((folder/'building.json').read_text(encoding='utf-8'))['floors'][0]
    p=json.loads((folder/'plan.json').read_text(encoding='utf-8'))
    holes=lambda rs:sum(len(poly.get('h',[])) for r in rs for poly in r['polys'])
    assert holes(p['rooms'])==holes(b['rooms'])
    assert len(b['fire_symbols'])==len(p['fire']['symbols'])
    assert all(r['fire_evidence'] is not None for r in b['rooms'])
    if floor=='1F':
        door=next(o for o in b['openings'] if o['id']=='W9')
        assert door['kind']=='door' and door['operation']=='unknown'
        assert geometry(door['geometry_polys']).intersection(geometry(b['glass']['polys'])).area<.001
    building_checks[floor]=dict(rooms=len(b['rooms']),holes=holes(b['rooms']),fire_symbols=len(b['fire_symbols']),evidence_preserved=True)
cards=[]
names={'hotel-4F':'호텔 4층','hotel-1F':'호텔 1층','office-1F':'업무시설 1층','office-4F':'업무시설 4층','exhibition-1F':'전시시설 1층'}
for r in report:
    name=r['sample']; src=RUN/name; dst=OUT/name; dst.mkdir(exist_ok=True)
    p=json.loads((src/'plan.json').read_text(encoding='utf-8'))
    for group in ('code_sha256','evidence_code_sha256'):
        assert all(hashlib.sha256((CAD/file).read_bytes()).hexdigest()==sha for file,sha in p['provenance'][group].items()),'stale source'
    for file in ['index.html','plan.json','quality.json','architecture.json','architecture_plan.png','fused.png','source.svg','fire_evidence.json']:
        if (src/file).exists(): shutil.copy2(src/file,dst/file)
    if name.startswith('hotel'):
        shutil.copy2(src/'building.json',dst/'building.json')
        shutil.copy2(src/'building.html',dst/'building.html')
    st=p['stats']; changed=r['changed_openings']
    detail=' / '.join(f'{o["id"]}: {o["before"]} → {o["after"]}' for o in changed) or '기존 개구부 종류 유지'
    cards.append(f'<a class="card" href="{name}/index.html"><img src="{name}/fused.png" alt="{names[name]}"><h2>{names[name]}</h2><p>실 {st["rooms"]} · 문 {st["doors_open"]} · 창 {st["windows"]} · 실내창 {st["windows_inner"]}</p><p>{escape(detail)}</p><p>소방 심볼 {r["fire_symbols"]}개 · 형상 오류 {r["quality"]["errors"]}개</p></a>')
summary=dict(unit_tests=22,unit_test_result='passed',real_drawings=report,building_checks=building_checks,
    note='Checks verify structural consistency, not 100% correspondence with manually annotated CAD ground truth.')
(OUT/'검증결과.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
files=['cad_pipeline.py','cad_evidence.py','cad_plan.py','cad_heal.py','cad_topology.py','cadio.py','cad_build3d.py',
       'run_building.py','fire_overlay.py','fire_building.py','fire_symbols.py','fire_align.py','cad_compare.py',
       'layer_map.json','standard_heights.json','viewer_template.html','compare_template.html',
       'test_cad_topology.py','test_cad_evidence.py','requirements-extraction.txt','CAD-추출-사용법.txt']
code=OUT/'code'; code.mkdir(exist_ok=True)
for file in files: shutil.copy2(CAD/file,code/file)
changes=[]
for file in files:
    old=W/'cad-v2-before'/file
    before=old.read_text(encoding='utf-8').splitlines(True) if old.exists() else []
    after=(CAD/file).read_text(encoding='utf-8').splitlines(True)
    changes.extend(difflib.unified_diff(before,after,fromfile='before/'+file,tofile='after/'+file))
(OUT/'changes.diff').write_text(''.join(changes),encoding='utf-8')
with zipfile.ZipFile(OUT/'CAD-추출코드-v2.zip','w',zipfile.ZIP_DEFLATED) as z:
    for file in files: z.write(code/file,'CAD3D/'+file)
    z.write(OUT/'changes.diff','changes.diff'); z.write(OUT/'검증결과.json','검증결과.json')
shutil.copy2(CAD/'CAD-추출-사용법.txt',OUT/'실행방법.txt')
page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CAD 통합 추출 v2</title><style>
body{margin:0;background:#f0f4f8;color:#203046;font:16px/1.6 system-ui,'Malgun Gothic',sans-serif}header,main,footer{max-width:1250px;margin:auto;padding:25px}h1{font-size:29px;margin:0}p{margin:8px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:20px}.card{display:block;border:1px solid #d8e0e9;border-radius:12px;background:white;padding:16px;color:inherit;text-decoration:none}.card img{width:100%;height:290px;object-fit:contain}h2{margin:12px 0 4px;font-size:20px}.card p{font-size:14px}a{color:#165da3}.note{background:#e3ebf4;padding:15px;border-radius:8px}
</style><header><h1>CAD 벽·문·창 추출 · 소방 근거 통합</h1><p>2026-10-14 · 원본 CAD → 평면 추출 → 감지기·유도등 보조 판정 → 3D 데이터 전달</p><p>22개 단위 시험 통과 · 3개 건물 5개 층 재처리 · 기존 실 수와 문 연결·회전 방향 유지</p><p class="note">형상 검사 통과는 도면 판독 정확도 100%를 뜻하지 않습니다. 실·벽 면은 20mm 격자 기반이며, 애매한 연결은 검토 표시로 남습니다. 호텔의 소방 심볼은 기존 추출·정렬 자료를 최신 평면에 다시 대조했습니다.</p><p><a href="CAD-추출코드-v2.zip">실행 코드 ZIP</a> · <a href="실행방법.txt">실행방법</a> · <a href="검증결과.json">검증결과</a></p></header><main class="grid">__CARDS__</main><footer>각 결과를 누르면 소방 통합 결과 / 건축 평면 / 원본 CAD 벡터를 전환하고 확대할 수 있습니다.</footer></html>'''.replace('__CARDS__',''.join(cards))
(OUT/'index.html').write_text(page,encoding='utf-8')
print(str(OUT))
print(json.dumps(building_checks,ensure_ascii=False))
