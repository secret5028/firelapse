import sys, json, pathlib, shutil, zipfile, difflib, hashlib
import numpy as np
import cv2

ROOT = pathlib.Path(__file__).resolve().parent.parent
CAD = pathlib.Path(r'C:\Users\<user>\Documents\Codex\2026-09-07\2\CAD3D')
sys.path.insert(0, str(CAD))
from cad_compare import render_original, b64
from cad_plan import LayerMap

RUN = ROOT/'work/cad-runs'
OUT = ROOT/'outputs/CAD-수정결과-20261014'
OUT.mkdir(parents=True, exist_ok=True)
orig, plan = render_original(str(ROOT/'work/cad-input/hotel-4F.dxf'),
                             str(RUN/'hotel-4F-after.json'), LayerMap(str(CAD/'layer_map.json')))
before = cv2.imdecode(np.fromfile(RUN/'hotel-4F-before_plan.png',dtype=np.uint8),cv2.IMREAD_COLOR)
after = cv2.imdecode(np.fromfile(RUN/'hotel-4F-after_plan.png',dtype=np.uint8),cv2.IMREAD_COLOR)
assert orig.shape == before.shape == after.shape
for name, img in [('hotel-4F-original.png',orig),('hotel-4F-before.png',before),('hotel-4F-after.png',after)]:
    cv2.imencode('.png',img)[1].tofile(str(OUT/name))

ra=plan['raster']
T=lambda xy: [round((xy[0]-ra['x0'])/ra['R'],1),round((ra['y1']-xy[1])/ra['R'],1)]
ops={o['id']:o for o in plan['openings']}
rooms={r['id']:r for r in plan['rooms']}
marks=[]
for c in plan['checks']:
    pos=None
    if c.get('id') in ops and ops[c['id']]['polys']:
        pos=T(np.mean(ops[c['id']]['polys'][0],axis=0)*1000)
    elif c.get('id') in rooms:
        pos=T(np.array(rooms[c['id']]['center'])*1000)
    marks.append(dict(t=c['rule'],d=f"{c.get('id','')} {c.get('note','')}",p=pos))
for f in plan['heal']['flags']:
    marks.append(dict(t=f['kind'],d=str(f.get('width','')),p=T(f['at'])))
data=[dict(name='호텔 4층',src='A-307 지상4층평면도.dwg → DXF',w=orig.shape[1],h=orig.shape[0],
           o=b64(orig),p=b64(after),g=b64(before),gname='수정 전 · 동일 원본 재실행',marks=marks,
           info=dict(rooms=len(rooms),stats=plan['stats'],heal=plan['heal']['summary']['ops']))]
html=(CAD/'compare_template.html').read_text(encoding='utf-8')
html=html.replace('__TITLE__','호텔 4층 · 수정 코드 실행 결과')
html=html.replace('/*__DATA__*/null',json.dumps(data,ensure_ascii=False).replace('</',r'<\/'))
html=html.replace('pane(f.g?\'레이어+공리\':\'처리 결과\',[[f.p]]);if(f.g)pane(f.gname||\'형상(레이어 무관)\',[[f.g]])',
                  "if(f.g)pane(f.gname,[[f.g]]);pane('수정 후 · 2026-10-14',[[f.p]])")
html=html.replace('결과: 레이어+공리','수정 후').replace('결과: 세 번째 화면','수정 전')
html=html.replace('type="checkbox" checked','type="checkbox"')
start=html.index('<h3>소방 심볼(세 번째 화면)</h3>')
end=html.index('<h3>표시점·검사',start)
html=html[:start]+'''<h3>이번 수정</h3><p>실 22개 · 문 18개 · 창 33개. 기존 문 연결과 열림 방향 유지.</p>
<p>실 내부 제외 영역 1개를 JSON과 3D 변환에 보존했습니다.</p>
<p><b style="color:#963cb4">□ 보라색 사각형</b>: 문틀의 축방향 지지 확인이 필요한 14곳. 확정 오류가 아니라 자동 연결의 검토 대상입니다.</p>
<p>실내창의 미닫이문 자동 확정을 중단하고, 불명 연결에 상태값을 추가했습니다. 이 층에는 실내창이 없습니다.</p>
<p>휠: 확대 · 드래그: 이동 · 전체: 화면 맞춤. 검사항목 클릭 시 해당 위치로 이동.</p>
<p>관리번호 28-200-2018-00000088. 이번 결과는 평면 추출과 형상 전달 점검이며, 화재해석 검증 결과가 아닙니다.</p>'''+html[end:]
(OUT/'compare.html').write_text(html,encoding='utf-8')
shutil.copy2(RUN/'hotel-4F-after.json',OUT/'hotel-4F-plan.json')

building=json.loads((RUN/'hotel-4F-building.json').read_text(encoding='utf-8'))
count_holes=lambda rs: sum(len(p.get('h',[])) for r in rs for p in r.get('polys',[]))
assert count_holes(plan['rooms'])==count_holes(building['floors'][0]['rooms'])==1
report=json.loads((RUN/'regression.json').read_text(encoding='utf-8'))
assert all(all(r['regression'].values()) for r in report), 'regression requires investigation'
verification=dict(unit_tests='7 passed',samples=[dict(building=r['building'],floor=r['floor'],
    rooms_before=r['before']['stats']['rooms'],rooms_after=r['after']['stats']['rooms'],
    holes_after=r['after']['holes'],checks=r['regression']) for r in report],
    building_conversion=dict(rooms=len(building['floors'][0]['rooms']),holes=1),
    provenance=plan['provenance'])
(OUT/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')
changed=['cad_plan.py','cad_heal.py','cad_build3d.py','cad_topology.py','test_cad_topology.py']
patch=[]
with zipfile.ZipFile(OUT/'modified-code.zip','w',zipfile.ZIP_DEFLATED) as z:
    for name in changed:
        z.write(CAD/name,'after/'+name)
        original=ROOT/'work/cad-baseline'/name
        old=original.read_text(encoding='utf-8').splitlines(True) if original.exists() else []
        if original.exists(): z.write(original,'before/'+name)
        patch.extend(difflib.unified_diff(old,(CAD/name).read_text(encoding='utf-8').splitlines(True),fromfile='before/'+name,tofile='after/'+name))
    z.writestr('changes.diff',''.join(patch))
    z.write(CAD/'layer_map.json','layer_map.json')
(OUT/'README.txt').write_text('''호텔 4층 CAD 수정 코드 실행 결과 — 2026-10-14
대상: 관리번호 28-200-2018-00000088, A-307 지상4층평면도.dwg
선정 이유: CAD 원본이 확보되어 있고 객실·복도·계단과 다수의 외기에 면한 창을 함께 확인할 수 있음.
원본 DWG를 DXF로 변환한 뒤, 동일한 DXF·레이어맵·20mm 해상도로 수정 전후 실행.

compare.html: CAD 선 / 수정 전 / 수정 후 비교. 확대·이동·겹치기 가능.
hotel-4F-after.png: 수정한 코드로 새로 생성한 추출 결과.
hotel-4F-plan.json: 형상과 연결 상태, 검사항목, 소스·코드 해시.
verification.json: 3개 건물 5개 층의 회귀검사와 단일층 3D 변환 확인.
modified-code.zip: 변경된 소스 5개, 수정 전 소스, diff, 레이어맵.

실 22개 / 문 18개 / 창 33개. 기존 문 연결과 문짝 회전방향 유지.
실 내부 제외 영역 1개를 폴리곤 내부 링으로 보존, 3D JSON 전달까지 확인.
문틀 축방향 지지 미확인 14곳은 보라색 사각형으로 표시. 오류 확정 아님.
기존 가까운 벽 연결은 실 분할용 가상 경계로 유지하고 기록함.
실내창은 폭만으로 미닫이문으로 확정하지 않음.
연결 미확인은 외기로 확정하지 않고 상태값을 기록함.
실제 문 형상으로 근거가 있는 개구부는 자동 틈 봉합에서 보호함.
창 블록의 사각형 중심선만으로 개구부를 보호하는 추정은 실 병합 문제로 제외함.

남은 범위: 창 개구부의 정확한 형상 근거, 검토 표시의 실제 도면 대조,
화재 엔진에서 미확인 상태 처리, 방화문 속성, 개방률 0/50/100%, 웹앱 통합.
현재 결과는 평면 추출 및 형상 전달 확인이며, 시뮬레이션 정확도 검증이 아님.
기존 저장 결과는 덮어쓰지 않고 새 폴더에 보관함.
''',encoding='utf-8')
print(json.dumps(verification,ensure_ascii=False))
print(OUT)
