from pathlib import Path
from PIL import Image
import io,base64,json,hashlib,re
from industrial_data import DATA
root=Path(__file__).parent
s=(root/'factory.html').read_text(encoding='utf-8')
s=s.replace('당산리 공장 · 소방공간뷰','강화산업단지 공장 · 소방공간뷰').replace('당산리 공장 · A-202—204','강화산업단지 · 20장 통합')
s=s.replace('<button data-floor="3">3층</button>','<button data-floor="3">옥탑</button>')
s=s.replace('<div class="north">방위 미확인 · 도면 상단 ↑</div>','<div class="north"><span id="northArrow" style="display:inline-block">↑</span> N · 배치도 기준</div>')
s=s.replace('<h2>목적 공간</h2>','<h2>진입 경로</h2><div class="split"><button id="startBtn">출발점 지정</button><button id="startResetBtn">해제</button></div><select id="entrance" aria-label="진입구"></select>')
s=s.replace('<p class="muted">벽 투명도</p>','<label><input type="checkbox" data-layer="equipment" checked>소방시설(기계)</label><label><input type="checkbox" data-layer="pipes" checked>소화전 배관 · 적색</label><label><input type="checkbox" data-layer="sprinklers" checked>SP 배관 · 자홍색</label><label><input type="checkbox" data-layer="machines" checked>생산설비</label><label><input type="checkbox" data-layer="roof">지붕</label><p class="muted">벽 투명도</p>')
s=s.replace('<select id="roomList" aria-label="목적 공간"></select>','')
s=s.replace('id="startResetBtn"','title="출발점 지정 해제 · 기본 도로 위치로 복귀" id="startResetBtn"')
s=s.replace('id="clearBtn"','title="화점 지정 해제" id="clearBtn"')
a=s.index('<section><div class="status"');b=s.index('</aside>',a)
s=s[:a]+'''<section><h2>소방기계 계통</h2><select id="system" aria-label="소방기계 계통"><option value="">시설 선택</option><option value="H">송수구 → 옥내소화전</option><option value="SP-A">준비작동식 A 계통</option><option value="SP-B">준비작동식 B 계통</option></select><p id="facilityInfo" class="muted"></p></section><details><summary>모델 근거</summary><p class="muted">건축 2015.12 · 기계 2015.10<br>층 높이 6m / 3.6m 임시값<br>좌표·설비 외곽·외부 동선 근사<br>노란색: 개구부·계단<br>청색: 진입 경로<br>적색: 소화전·공통 급수<br>자홍색: 스프링클러<br>배관: 천장 기준 · 높이 임시값</p></details>'''+s[b:]
a=s.index('<ul>',s.index('id="helpModal"'));b=s.index('</ul>',a)+5
s=s[:a]+'''<ul><li>20장 JPG를 사람이 대조한 통합 검토 모델입니다. 017·018·019 건축 평면으로 1층·2층·옥탑을 구성하고, 020~024 방화구획·창호 도면과 001~006 기계 도면을 겹쳐 판독했습니다. 반복 도면은 추가 층으로 만들지 않았습니다.</li><li>축간 98.6 × 32m. 1층에서 2층 6m, 2층에서 옥상 3.6m는 단면 자료가 없어 적용한 임시값입니다. 문·창·칸막이·계단 치수는 근사값이며 작은 화장실 내부 칸막이는 생략했습니다.</li><li>1층은 전체 바닥, 2층은 양끝 10.2m와 9.7m 폭 공간만 모델링했습니다. 중앙 OPEN에는 바닥과 횡단 통로를 만들지 않았습니다. 승강기·지하층은 확인되지 않아 추가하지 않았습니다.</li><li>정북은 배치도 016의 도면 오른쪽입니다. 시점 복원은 정북이 위를 향합니다. 양측 15.5m / 15m 도로와 대지 진입구를 반영했습니다. 배치도의 지면 고저차는 평탄화했고 보행·주차 장애물과 후면 협소 공간의 실제 통행 가능성은 확인되지 않았습니다.</li><li>도로 위 소방차·사람 옆을 기본 출발점으로 하며 출발점 지정으로 외부 지면에서 바꿀 수 있습니다. 건물 출입문과 계단을 통과하는 경로입니다. 1층 0.5m, 상층 0.25m 격자와 등록된 계단 연결에서 최단거리를 계산합니다. 10개 출입구마다 지정한 출발점에서의 접근 거리를 비교합니다. 화점 지정 후 가장 짧은 두 후보를 표시하고 목록을 누르면 다른 후보를 봅니다. 모델의 허용된 연결 내 거리이며 현장 안전성을 뜻하지 않습니다.</li><li>생산설비는 017의 외곽을 단순화한 통행 장애물입니다. 생산설비 레이어를 꺼도 경로 장애물은 유지됩니다. 화점 지정 시 해당 위치에서 화살표가 끝나며 해제하면 경로가 사라집니다. 목적공간은 적색 테두리입니다.</li><li>옥내소화전은 002의 1층 6개, 003의 2층 2개를 반영했습니다. 연결송수구와 공통 소화배관의 관계는 001·002 기준입니다. 계통 선은 단순 연결도이며 실제 배관 좌표·수리계산·방수 가능 범위가 아닙니다.</li><li>준비작동식 A/B는 004에 그려진 측부 계통을 반영했습니다. 중앙 공장의 스프링클러 설치 표기는 020에서 확인되지만, 개별 헤드 배치를 전부 재현하지 않았습니다. 지붕층 수조 소화용수 45톤 이상, 주·예비·보조펌프는 001·006 기준입니다. 전기설비는 소방기계로 대체하지 않았습니다.</li><li>건축 도면은 2015.12, 소방 도면은 2015.10이므로 서로 다른 시점의 계획을 대조한 결과입니다. 모든 수정사항이 정합된 준공 모델은 아닙니다. 실명은 도면을 따르며 없으면 임시명을 사용합니다.</li><li>마우스 상하 반전 기본. 가운데 또는 왼쪽 드래그 회전, Shift+가운데 또는 오른쪽 드래그 이동, 휠 확대, 클릭 중심 변경. 바닥 비교는 층 간격을 벌린 설명용 보기입니다.</li></ul>'''+s[b:]
s=s.replace('</style>','.routepick{display:block;width:100%;text-align:left;margin:5px 0;font-size:12px;padding:9px}.routepick b{float:right;color:#83c7ff}.routepick.chosen{border-color:#258dff;background:#203e59}#routes{max-height:220px;overflow:auto}#entrance{margin-bottom:9px}</style>')
(root/'industrial.html').write_text(s,encoding='utf-8')
assets={};hashes={}
def enc(im):
    b=io.BytesIO();im.convert('RGB').save(b,'JPEG',quality=80);return 'data:image/jpeg;base64,'+base64.b64encode(b.getvalue()).decode()
for k in DATA['sources']:
    p=Path('C:/Users/<user>/Downloads')/('20160524151100_'+k.zfill(3)+'.jpg');hashes[k]=hashlib.sha256(p.read_bytes()).hexdigest();im=Image.open(p)
    if k in ['17','18','19']:
        coords={'17':(297,500,1407,859),'18':(305,500,1418,859),'19':(307,500,1418,859)}[k];w,h=im.size;crop=im.crop(tuple(round(v*(w/1888 if i%2==0 else h/1334)) for i,v in enumerate(coords)));crop.thumbnail((2800,1500));assets['crop'+str(int(k)-16)]=enc(crop)
    im.thumbnail((2200,2200));assets[k]=enc(im)
def js(v):return json.dumps(v,ensure_ascii=False).replace('</','<\\/')
boot='window.INDUSTRIAL='+js(DATA)+';window.INDUSTRIAL_ASSETS='+js(assets)+';(async()=>{try{'
boot+='const core=URL.createObjectURL(new Blob(['+js((root/'three.core.js').read_text(encoding='utf-8'))+'],{type:"text/javascript"}));'
boot+='const lib=URL.createObjectURL(new Blob(['+js((root/'three.module.js').read_text(encoding='utf-8'))+'.replaceAll("./three.core.js",core)],{type:"text/javascript"}));'
boot+='const app=URL.createObjectURL(new Blob(['+js((root/'industrial.js').read_text(encoding='utf-8'))+'.replace("__THREE__",lib)],{type:"text/javascript"}));await import(app);'
boot+='}catch(e){document.getElementById("fatal").style.display="block";document.getElementById("fatal").textContent="3D 시작 오류: "+e.message;console.error(e)}})();'
html=s.replace('/*BOOT*/',boot)
from hydraulic_embed import embed_hydraulics
html=embed_hydraulics(html,root,'industrial-20-v1','강화산업단지 공장 · 기존 배관은 개략선, 계산 계통 별도 등록')
out=root.parent/'outputs'/'소방공간뷰-강화산업단지-통합.html';out.write_text(html,encoding='utf-8');(root/'industrial-sample.html').write_text(html,encoding='utf-8');(root/'industrial-hashes.json').write_text(json.dumps(hashes),encoding='utf-8');(root/'industrial-data.json').write_text(json.dumps(DATA,ensure_ascii=False),encoding='utf-8');print(out.stat().st_size,'bytes /',len(DATA['sources']),'source pages /',len(DATA['mechanical']),'mechanical items')
