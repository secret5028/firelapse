import pathlib,sys,json,shutil,hashlib,base64,zipfile,re,subprocess,difflib
W=pathlib.Path(__file__).resolve().parent;CAD=pathlib.Path(r'C:\Users\예방\Documents\Codex\2026-09-07\2\CAD3D')
sys.path[:0]=[str(W/'cad-deps'),str(CAD)]
from cad_review_ui import enhance_review
RUN=W/'cad-v6-runs';OUT=W.parent/'outputs/CAD-문판정-v6';OUT.mkdir(exist_ok=True)
report=json.loads((RUN/'validation.json').read_text(encoding='utf8'))
names={'office-1F':'업무시설 1층','office-4F':'업무시설 4층','hotel-1F':'호텔 1층','hotel-4F':'호텔 4층','exhibition-1F':'전시시설 1층'}
cards=[]
for row in report:
 name=row['sample'];src=RUN/name;dst=OUT/name;dst.mkdir(exist_ok=True)
 p=json.loads((src/'plan.json').read_text(encoding='utf8'));b=json.loads((src/'building.json').read_text(encoding='utf8'))
 for group in ('code_sha256','evidence_code_sha256'):
  assert all(hashlib.sha256((CAD/f).read_bytes()).hexdigest()==sha for f,sha in p['provenance'][group].items()),name+' stale code'
 assert not row['changed_existing_connections'],(name,row['changed_existing_connections'])
 for f in src.iterdir():
  if f.suffix in ('.json','.html','.png','.svg'):shutil.copy2(f,dst/f.name)
 shutil.copy2(W.parent/'outputs/CAD-벽공리-v5'/name/'fused.png',dst/'before.png')
 (dst/'simulation_graph.json').write_text(json.dumps(b['floors'][0]['simulation_graph'],ensure_ascii=False,indent=2),encoding='utf8')
 ra=p['raster'];data=base64.b64encode((dst/'fused.png').read_bytes()).decode()
 (dst/'connectivity.svg').write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ra["W"]} {ra["H"]}"><image href="data:image/png;base64,{data}" width="{ra["W"]}" height="{ra["H"]}"/></svg>',encoding='utf8')
 h=(dst/'index.html').read_text(encoding='utf8').replace('소방 근거 통합 결과','수정 후 v6').replace('<nav>','<nav><button data-src="before.png">수정 전 v5</button>')
 note=f'<h2>{names[name]} · 문 판정 v6</h2><p><a href="../index.html">전체 결과</a> · <a href="building.html">3D 보기</a></p><p>연결 확인 {len(row["excluded"])}개 · 공간 {row["rooms_after"]}개<br>기존 정상 연결 유지: 공간 대응 비교</p>'
 if name=='office-1F':
  assert {o['id'] for o in p['simulation_graph']['excluded_openings']}=={'W76','W79'}
  openings={o['id']:o for o in p['openings']}
  assert set(openings['D13']['sides'])=={'R21','R25'} and set(openings['D18']['sides'])=={'R9','R15'}
  assert 'out' in openings['D6']['sides'] and not {'D16','W62','W65','W89'}&set(openings)
  note+='''<p><b>기존 8개 중 7개 처리 · 남은 W76 + 재검토 W79 = 2개</b></p><ul><li>D6: 방풍실 R30 ↔ 외기 복구 (기존 방풍실 ID R32)</li><li>D13: R21 ↔ R25 복구</li><li>D18: R9 ↔ R15 복구</li><li>D16: 호만 있고 문짝·구획 근거 부족 → 문 후보 제외</li><li>W62: 외부 부속 후보 제외</li><li>W65·W89: 원본 대조 기록에 따라 후보 제외</li></ul><p>W76: 고정창 가능성을 포함해 개폐 방식 미확정.<br>W79: 벽 복구 후 다시 드러난 미확정 후보.<br>두 후보는 유동 연결에서 제외됩니다.</p><p>문·창 0/50/100% 각각 60초 계산 완료. 물리 정확도 검증은 별도입니다.</p><p><a href="../office-1F-review-v6.json">도면별 검토 보정 기록</a></p>'''
 h=h.replace('<h2>표시와 검토</h2>',note+'<h2>기타 표시</h2>')
 (dst/'index.html').write_text(h,encoding='utf8');items=enhance_review(dst)
 assert len(items)==len(row['excluded'])
 scripts=re.findall(r'<script[^>]*>([\s\S]*?)</script>',(dst/'index.html').read_text(encoding='utf8'))
 check=W/f'v6-{name}-ui-check.js';check.write_text('\n'.join(scripts),encoding='utf8')
 subprocess.run([r'C:\Users\예방\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe','--check',str(check)],check=True,capture_output=True)
 cards.append(f'<a class="card" href="{name}/index.html"><h2>{names[name]}</h2><img src="{name}/fused.png" alt="{names[name]} 추출 결과"><p>확인 대상 {len(items)}개 · 공간 {len(p["rooms"])}개</p></a>')
code=OUT/'code';code.mkdir(exist_ok=True)
files={f.name for f in (W.parent/'outputs/CAD-벽공리-v5/code').iterdir() if f.is_file()}|{'cad_door_rules.py','cad_review_rules.py','test_cad_door_rules.py'}
diff=[]
for name in sorted(files):
 shutil.copy2(CAD/name,code/name);before=W/'cad-v6-before'/name
 if name.endswith(('.py','.json')):
  diff.extend(difflib.unified_diff(before.read_text(encoding='utf8').splitlines(True) if before.exists() else [],(CAD/name).read_text(encoding='utf8').splitlines(True),fromfile='v5/'+name,tofile='v6/'+name))
shutil.copy2(W/'office-1F-review-v6.json',OUT/'office-1F-review-v6.json')
(OUT/'changes.diff').write_text(''.join(diff),encoding='utf8')
(OUT/'검증결과.json').write_text(json.dumps(dict(unit_tests_passed=58,samples=report,
 code_sha256={f:hashlib.sha256((code/f).read_bytes()).hexdigest() for f in files},browser_click_test='not_run_local_file_access_restricted'),ensure_ascii=False,indent=2),encoding='utf8')
doc='''CAD 문 판정 v6

일반 코드 변경
- 반원 문 기호의 지름 형태 문짝선을 벽과 구분합니다.
- 반원 호 방향 판정에서 맞은편 문틀과 기존 벽 관통 여부를 대조합니다.
- 독립된 반원 문 구역의 틈 보강은 닫힌 문짝 위치 근처로 제한합니다. 여러 문을 한꺼번에 포함하는 복합 블록은 이 보강 규칙에서 제외합니다.
- 외기/외기이며 인접 실내 공간과 문짝 근거가 없는 부속 후보는 건물 개구부에서 제외합니다.
- 호만 있고 문짝·짝문·구획·벽 지지가 부족한 후보는 제외하되, 명시적인 문 레이어와 소방 보조 근거는 보호합니다.
- 창은 개폐 흔적이 없다는 이유만으로 삭제하지 않습니다. 고정창이 있을 수 있습니다.

원본 대조에 따른 도면별 보정 (완전 자동 인식 성과와 구분)
office-1F-review-v6.json은 입력 DXF의 SHA-256이 정확히 일치할 때만 적용됩니다.
D18 아래 TEX 레이어의 원본 벽선 1개를 복구합니다. 원본에 없는 대칭 벽을 만들지 않습니다.
W65(연속 벽면 부속선), W89(기둥 하부 반복 빗살 상세) 후보를 제외합니다.

업무시설 1층 실행
python code/cad_pipeline.py "input.dxf" result --floor 1F --review-profile office-1F-review-v6.json
python code/cad_build3d.py result/building result/plan.json --names 1F

도면별 보정 없이 일반 규칙만 실행
python code/cad_pipeline.py "input.dxf" result --floor 1F

검증
58개 단위 테스트. 실제 5개 층 재추출 및 3D·해석 입력 대응 검사.
업무시설 1층 0/50/100% 각각 60초, 나머지 4개 층 50% 60초 계산.
기존 정상 연결은 공간 겹침으로 대응시켜 비교합니다. 실 ID는 재추출에 따라 바뀔 수 있습니다.
업무시설 1층 기존 8개 중 7개 처리: D6,D13,D18 연결 복구 / D16,W62,W65,W89 제외.
남은 W76과 벽 복구 후 다시 확인 대상으로 올라온 W79, 총 2개는 유동 연결에서 제외합니다.
실 구획 수 변화와 전체 대응은 검증결과.json에 기록했습니다.
계산 성공은 물리 정확도 검증을 의미하지 않습니다. 로컬 파일 브라우저 자동화 제한으로 실제 클릭 검사는 수행하지 않았습니다. 생성 이미지·마커 대응·JavaScript 문법은 검사했습니다.
기존 웹앱 배포는 수행하지 않았습니다.
'''
(OUT/'설명과실행.txt').write_text(doc,encoding='utf8')
with zipfile.ZipFile(OUT/'CAD-문판정-v6.zip','w',zipfile.ZIP_DEFLATED) as z:
 for file in code.iterdir():z.write(file,'code/'+file.name)
 for name in ['office-1F-review-v6.json','설명과실행.txt','검증결과.json','changes.diff']:z.write(OUT/name,name)
page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CAD 문 판정 v6</title><style>body{margin:0;background:#f3f5f8;color:#21344a;font:17px/1.7 system-ui,'Malgun Gothic',sans-serif}header,main{max-width:1200px;margin:auto;padding:24px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:20px}.card{padding:18px;background:white;border:1px solid #ddd;border-radius:10px;color:inherit;text-decoration:none}.card img{width:100%;height:240px;object-fit:contain}a{color:#1565aa}h1{font-size:28px}h2{font-size:22px}.note{padding:14px;background:#fff0d4}</style><header><h1>CAD 문 판정 · v6</h1><p><b>업무시설 1층: 기존 확인 대상 8개 중 7개 처리</b><br>W76 보류 + W79 재검토 = 현재 확인 대상 2개</p><p><a href="office-1F/index.html">업무시설 1층 수정 결과</a> · <a href="office-1F/building.html">3D 보기</a> · <a href="CAD-문판정-v6.zip">수정 코드</a></p><p class="note">D6·D13·D18 연결 복구 / D16·W62·W65·W89 후보 제외.<br>D18 원본 벽선 복구와 W65·W89 제외는 도면별 검토 보정입니다. 나머지는 일반 규칙 수정입니다.</p><p>58개 테스트 · 5개 층 재추출 · 기존 정상 연결의 공간 대응 유지 확인<br><a href="검증결과.json">검증 결과</a> · <a href="설명과실행.txt">수정 내용과 실행 방법</a></p></header><main class="grid">__CARDS__</main></html>'''
(OUT/'index.html').write_text(page.replace('__CARDS__',''.join(cards)),encoding='utf8')
print(OUT)
