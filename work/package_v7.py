import pathlib,sys,json,shutil,zipfile,difflib,hashlib,re,subprocess,html
W=pathlib.Path(__file__).resolve().parent;CAD=pathlib.Path(r'C:\Users\예방\Documents\Codex\2026-09-07\2\CAD3D');sys.path[:0]=[str(W/'cad-deps'),str(CAD)]
from cad_review_ui import enhance_review
from cad_source_audit import write_layer_viewer
from cadio import load,units_to_m
from cad_plan import LayerMap
import numpy as np,cv2
ROOT=W/'cad-v7-runs';OUT=W.parent/'outputs/CAD-전층레이어-v7';OUT.mkdir(exist_ok=True)
report=json.loads((ROOT/'validation.json').read_text(encoding='utf8'));manifest=json.loads((W/'drawing-manifest-v7.json').read_text(encoding='utf8'))
style='body{font:16px/1.7 system-ui,Malgun Gothic,sans-serif;margin:0;background:#f2f5f9;color:#24364a}header,main{max-width:1280px;margin:auto;padding:24px}h1{font-size:28px}h2{font-size:21px}a{color:#1764a1}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:18px}.card{background:white;padding:18px;border-radius:12px;border:1px solid #d4dfec}.card img{width:100%;height:240px;object-fit:contain}table{border-collapse:collapse;width:100%;background:white}td,th{text-align:left;padding:10px;border-bottom:1px solid #ddd}.note{background:#fff2d9;padding:15px;border-radius:8px}nav{display:flex;gap:16px;flex-wrap:wrap}'
cards=[];contact=np.full((3*520,3*750,3),255,np.uint8)
for k,row in enumerate(report['floors']):
 floor=row['floor'];name='office-'+floor;src=ROOT/name;dst=OUT/name;dst.mkdir(exist_ok=True)
 for f in src.iterdir():
  if f.suffix in ('.json','.html','.png','.svg'):shutil.copy2(f,dst/f.name)
 p=json.loads((dst/'plan.json').read_text(encoding='utf8'))
 note=f'<h2>{floor} · 전층 레이어 검토 v7</h2><p><a href="../index.html">전층 목록</a> · <a href="building.html">이 층 3D</a> · <a href="../building.html">전층 3D</a></p><p>공간 {row["rooms"]}개 · 원본 레이어 {row["scanned_layers"]}개 검색<br>형상 검사 오류 {row["quality_errors"]}개 · 연결 확인 {len(row["uncertain"])}개</p>'
 if floor=='1F':note+='<p><b>기존 W79 → D19: 문짝·호·문틀의 레이어를 함께 판독해 문으로 복구.</b><br>D19는 R15 ↔ 새 공간 R17로 연결됩니다. D6·D13·D18의 기존 연결 관계는 공간 대응상 유지됩니다.</p><p>D16은 주변 문틀 근거가 있어 후보로 복귀했습니다. W76과 함께 북측 구획이 불명확하므로 유동 연결에서 보류합니다.</p><p>W65·W89 제외만 이전 원본 대조 보정을 유지합니다. TEX 벽선 복구는 이번 일반 규칙으로 처리했습니다.</p>'
 if floor=='3F':note+='<p>추가 확인: 전면 외곽 곡선 영역 R27의 실내·외 구분은 미확정입니다. 형상이 유효하다는 검사와 공간 용도 판정은 구별해야 합니다.</p>'
 if floor=='PH':note+='<p>지붕SL바닥 영역은 실내 방에서 제외했습니다. 전층 모델에서 옥탑 위치는 벽 형상 상관으로 추정한 정렬(r=0.39)이므로 위치 대조가 필요합니다.</p>'
 h=(dst/'index.html').read_text(encoding='utf8').replace('<h2>표시와 검토</h2>',note+'<h2>표시와 검토</h2>').replace('소방 근거 통합 결과','최종 추출 결과')
 (dst/'index.html').write_text(h,encoding='utf8');items=enhance_review(dst);assert len(items)==len(row['uncertain'])
 im=cv2.imdecode(np.fromfile(str(dst/'fused.png'),np.uint8),cv2.IMREAD_COLOR);s=min(710/im.shape[1],465/im.shape[0]);small=cv2.resize(im,None,fx=s,fy=s)
 x=(k%3)*750+20;y=(k//3)*520+45;contact[y:y+small.shape[0],x:x+small.shape[1]]=small
 cv2.putText(contact,floor+' / rooms '+str(row['rooms'])+' / review '+str(len(items)),(x,y-15),cv2.FONT_HERSHEY_SIMPLEX,.75,(35,50,80),2)
 cards.append(f'<article class="card"><h2>{floor}</h2><a href="{name}/index.html"><img src="{name}/fused.png" alt="{floor} 평면"></a><p>공간 {row["rooms"]}개 · 연결 확인 {len(items)}개 · 검사 레이어 {row["scanned_layers"]}개</p><nav><a href="{name}/index.html">평면·확인 표시</a><a href="{name}/building.html">3D</a><a href="{name}/layers.html">전체 레이어 대조</a></nav></article>')
cv2.imencode('.png',contact)[1].tofile(str(OUT/'전층-미리보기.png'))
for name in ('building.html','building.json'):shutil.copy2(ROOT/name,OUT/name)
shutil.copy2(ROOT/'validation.json',OUT/'검증결과.json');shutil.copy2(W/'drawing-manifest-v7.json',OUT/'도면검토목록.json');shutil.copy2(W/'office-1F-review-v7.json',OUT/'office-1F-review-v7.json')
shutil.copy2(W/'office-PH-review-v7.json',OUT/'office-PH-review-v7.json')

# Roof is a reference sheet, not a fabricated occupied storey.
roof=next(r for r in manifest['drawings'] if r['role']=='roof_plan');d,pr,ins=load(roof['path']);unit=units_to_m(d,pr);lm=LayerMap(CAD/'layer_map.json')
vectors=[dict(id='V'+str(i),category=lm.cat(p.layer),entity=p.kind,layer=p.raw,source=p.source,closed=p.closed,excluded_from_boundary=False,points=[[x*unit,y*unit] for x,y in p.pts],arc=None if p.arc is None else [p.arc[0]*unit,p.arc[1]*unit,p.arc[2]*unit,p.arc[3],p.arc[4]]) for i,p in enumerate(pr)]
pts=np.array([q for v in vectors for q in v['points']]);lo=pts.min(0)-1;hi=pts.max(0)+1
rp=dict(source_vectors=vectors,raster=dict(x0=lo[0]*1000,y1=hi[1]*1000,R=20,W=round((hi[0]-lo[0])*50),H=round((hi[1]-lo[1])*50)),layer_evidence=dict(scanned_layers=sorted({p.raw for p in pr}),derived_wall_pieces=0))
rd=OUT/'roof';rd.mkdir(exist_ok=True);write_layer_viewer(rp,rd/'layers.html');(rd/'index.html').write_text('<meta charset="utf-8"><a href="../도면검토.html">도면 검토 목록</a> · <a href="layers.html">지붕도 전체 레이어</a><p>지붕 점검구와 지붕 바닥 참고도입니다. 별도 실내 층으로 생성하지 않았습니다.</p>',encoding='utf8')

audit=OUT/'sources';audit.mkdir(exist_ok=True)
for f in (W/'cad-v7-inventory').glob('fire-*.png'):shutil.copy2(f,audit/f.name)
for name in ('cad_inventory.json','pdf_inventory.json','layouts.json','PH-roof-label.json'):shutil.copy2(W/'cad-v7-inventory'/name,audit/name)
pdfcards=[]
for r in manifest['drawings']:
 if r['role']!='raster_reference':continue
 i=r['page'];pdfcards.append(f'<article class="card"><h2>소방 PDF {i}쪽</h2><a href="sources/fire-{i:02}.png"><img src="sources/fire-{i:02}.png"></a><p>{html.escape(r["title"])}</p><p>대상: {", ".join(r["floors"]) or "범례·목록"}<br>육안 대조 완료 · 좌표 합성 미적용</p></article>')
rows=''.join(f'<tr><td>{r["floor"]}</td><td>{html.escape(r["name"])}</td><td>{r["primitives"]}</td><td>{len(r["layers"])}</td></tr>' for r in manifest['drawings'] if r['role'] in ('architectural_plan','roof_plan'))
auditpage=f'<!doctype html><html lang="ko"><meta charset="utf-8"><title>도면·레이어 검토 범위</title><style>{style}</style><header><h1>도면·레이어 검토 범위</h1><p><a href="index.html">전층 결과</a> · <a href="roof/layers.html">지붕도 대조</a> · <a href="도면검토목록.json">검토 기록</a></p><p>{manifest["coverage_note"]}</p><p>전체 CAD의 Model 공간을 확인했으며 Layout1은 모두 비어 있습니다. 레이어의 꺼짐·동결 상태도 목록에 남겼습니다. 문자·해치·치수 엔티티 수는 원본 목록에 기록하고, 구조 판정은 전개한 기하 요소를 사용합니다.</p><table><tr><th>층</th><th>도면</th><th>기하 요소</th><th>등록 레이어</th></tr>{rows}</table><p class="note">소방 PDF는 모두 스캔입니다. 변경전 도면은 이력 자료로 구분했습니다. CAD 좌표와 정합하지 않은 감지기·유도등·배관 기호를 자동 확정 위치로 넣지 않았습니다.</p></header><main class="grid">{"".join(pdfcards)}</main></html>'
(OUT/'도면검토.html').write_text(auditpage,encoding='utf8')
total=sum(len(r['uncertain']) for r in report['floors'])
(OUT/'index.html').write_text(f'<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CAD 전층·전체 레이어 v7</title><style>{style}</style><header><h1>CAD 전층·전체 레이어 · v7</h1><p>지하 1층 · 지상 1~7층 · 옥탑층, 총 9개 층 재추출 및 3D 생성</p><nav><a href="building.html">전층 통합 3D</a><a href="office-1F/index.html">1층 수정 결과</a><a href="도면검토.html">전체 도면 검토 기록</a><a href="CAD-전층레이어-v7.zip">수정 코드</a></nav><p class="note">W79였던 위치를 문 D19로 복구했습니다. 1층 확인 대상은 북측 D16·W76 2개입니다.<br>전층 연결 확인 대상은 {total}개이며 각 층 평면에서 빨간 번호로 표시합니다.</p><p>67개 테스트 통과 · 9개 층 형상 오류 0개 · 실/벽 면적 중첩 0 · 각 층 0/50/100% 개구부 상태의 60초 시제품 계산 완료.<br>계산 성공은 화재 물리 정확도 검증을 뜻하지 않습니다.</p><p><a href="검증결과.json">검증 결과</a> · <a href="설명과실행.txt">수정 내용·적용 범위</a> · <a href="전층-미리보기.png">전층 평면 한눈에 보기</a></p></header><main class="grid">{"".join(cards)}</main></html>',encoding='utf8')

doc='''CAD 전층·전체 레이어 v7

적용: 업무시설 28-200-2026-00000010의 B1, 1F~7F, PH 총 9개 층.
건축 CAD 10장(지붕 포함), 소방 PDF 10쪽, 모든 CAD 레이어와 배치 목록을 확인했습니다.

코드 변경
- 원본 기하를 레이어명으로 버리지 않고 전체 도면 범위로 보존합니다.
- 문짝·호·이중 벽/문틀 근거를 레이어를 넘어 대조합니다. 가구 레이어의 호도 이 근거가 있으면 문으로 채택합니다.
- 기존 구조선과 새 문에 연결된 이중 벽선 중 실제로 겹치는 길이만 복구합니다. 교차하는 가구·설비선으로 복구가 퍼지지 않도록 별도 연결 검사를 합니다.
- 문짝 사각 윤곽을 닫힘 위치의 단순 보조선보다 우선하여 문 방향이 뒤집히는 경우를 수정했습니다.
- 호만 있는 후보라도 주변 문틀 근거가 있으면 보류 목록으로 유지합니다.
- 윤곽 유효화 중 실이 벽으로 채워지는 오류를 수정하고 실/벽 비중첩 검사와 회귀 테스트를 추가했습니다.
- 전체 레이어 대조 화면, 출처 해시·층·도면 역할에 묶인 도면 목록 검증을 추가했습니다.

1층 변화
- 기존 W79 → D19, R15 ↔ R17 연결. R17은 원본 이중 경계를 복구하여 분리된 9.644㎡ 공간입니다. 공간 용도는 확정하지 않았습니다.
- W77 연결 상대는 이에 따라 R9 ↔ R17로 변경됐습니다.
- D6, D13, D18 기존 정상 연결은 실 ID 대응상 유지됩니다. 실 ID는 재추출로 바뀔 수 있습니다.
- D16은 문틀 근거가 있어 불명확 후보로 복귀. W76과 함께 북측 구획 확인이 필요합니다.
- W65·W89 제외는 앞선 사용자/원본 대조의 도면별 보정입니다. TEX 벽선의 수동 승격은 제거하고 일반 규칙으로 대체했습니다.
- 옥탑층 R0는 원본의 '지붕SL바닥' 표기를 확인하여 실내 구획에서 제외했습니다. 이 판정은 office-PH-review-v7.json에 원본 해시와 영역으로 묶인 검토 보정입니다. 참고 형상은 plan.json의 non_compartment_regions에 보존합니다.

층 높이
B1 -4.2, 1F .9, 2F 6.4, 3F 11.9, 4F 17.4, 5F 21.9, 6F 26.4, 7F 30.9, PH 36.6, 지붕 39.9m (GL 기준).
B1의 기존 추정 -2.9m를 도면 -4.2m로 교정했습니다.
7F는 층별 LEVEL/SL +30.9m 기준이며 별도 FL +31.5m/+32.2m 단차는 단일 층 모델에 반영하지 않았습니다. 천장고는 용도 기본값입니다.

확보 자료의 한계
소방 PDF는 스캔이며 평면은 지하층 위주입니다. 1F~7F 개별 소방 평면·창호일람·단면·입면은 현재 원본 폴더에서 확보되지 않았습니다.
소방 PDF와 B1 도면의 1F 계단실 부분도는 대조 및 출처 목록에 등록했으나 좌표 정합 전 자동 합성하지 않았습니다.
이번 건물의 감지기·유도등은 검증된 CAD 좌표 자료가 없어 새 위치를 자동 생성하지 않았습니다.
지붕도는 참고도로 보존하며 실내 층을 만들지 않았습니다.
3F 전면 외곽 곡선 영역 R27은 실내·외 구분이 미확정이며 검토 대상으로 표시했습니다. 개구부 연결 확인 11개와 별개의 공간 분류 검토입니다.
옥탑층 정렬은 벽 형상 상관 r=0.39의 추정값입니다. 다른 층은 코어/기둥으로 맞췄으나 옥탑 정렬은 별도 대조가 필요합니다.

검증
67개 단위 테스트. 9개 층 재추출·평면/3D/해석 입력 일치. 실/벽 중첩 0, 형상 오류 0.
각 층 문창 개방 0/50/100%로 60초 계산(총 27회). 시제품 실행 검증이며 물리 정확도 검증 아님.
다른 호텔·전시시설 3개 층 회귀 검사에서 기존 정상 연결 유지.
로컬 파일 브라우저 자동화 접근 제한으로 실제 클릭 시험은 하지 못했습니다. 정적 이미지·데이터·JavaScript 문법을 검사했습니다.
기존 웹앱 배포는 별도이며, 이번 결과와 수정 코드를 인계할 수 있도록 묶었습니다.

실행
pip install -r code/requirements-extraction.txt
python code/cad_pipeline.py input.dxf result --floor 1F --review-profile office-1F-review-v7.json --drawing-manifest 도면검토목록.json
검토 보정과 도면 목록은 정확히 일치하는 원본에만 적용됩니다. 다른 건물은 해당 옵션을 생략하거나 해당 원본의 검토 목록을 작성하세요.
python code/cad_build3d.py result/building result/plan.json --names 1F
'''
(OUT/'설명과실행.txt').write_text(doc,encoding='utf8')
code=OUT/'code';code.mkdir(exist_ok=True);diff=[]
for f in CAD.iterdir():
 if not f.is_file() or f.suffix not in ('.py','.json') and f.name not in ('viewer_template.html','compare_template.html','requirements-extraction.txt'):continue
 shutil.copy2(f,code/f.name);old=W/'cad-v7-before'/f.name
 if f.suffix=='.py':diff.extend(difflib.unified_diff(old.read_text(encoding='utf8').splitlines(True) if old.exists() else [],f.read_text(encoding='utf8').splitlines(True),fromfile='v6/'+f.name,tofile='v7/'+f.name))
(OUT/'changes.diff').write_text(''.join(diff),encoding='utf8')
for f in ('run_v7_final.py','validate_v7.py','compare_v7.py','inventory_v7.py','manifest_v7.py'):shutil.copy2(W/f,code/f)
with zipfile.ZipFile(OUT/'CAD-전층레이어-v7.zip','w',zipfile.ZIP_DEFLATED) as z:
 for f in code.iterdir():z.write(f,'code/'+f.name)
 for name in ('설명과실행.txt','changes.diff','검증결과.json','office-1F-review-v7.json','office-PH-review-v7.json','도면검토목록.json'):z.write(OUT/name,name)
# Syntax-check actual generated JavaScript, excluding import-map JSON.
node=r'C:\Users\예방\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe';checked=0
for path in OUT.rglob('*.html'):
 if 'code' in path.parts:continue
 for attrs,body in re.findall(r'<script([^>]*)>([\s\S]*?)</script>',path.read_text(encoding='utf8')):
  if 'importmap' in attrs or not body.strip():continue
  check=W/'v7-script-check.mjs';check.write_text(body,encoding='utf8');subprocess.run([node,'--check',str(check)],check=True,capture_output=True);checked+=1
(OUT/'UI검사.json').write_text(json.dumps(dict(javascript_blocks_checked=checked,syntax='passed',browser_click_test='not_run_local_file_access_restricted'),ensure_ascii=False,indent=2),encoding='utf8')
print(OUT,'JS blocks',checked,flush=True)
