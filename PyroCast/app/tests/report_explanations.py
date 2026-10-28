"""Report source-backed UI prose inventory; no simulation or source mutation."""
from pathlib import Path
import json
import re
import hashlib
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'simulation/results/ui_refactor_stage4_item6_20261028'
CAD = Path('C:/Users/예방/Documents/Codex/2026-10-14/files-pasted-by-the-user-cad3d/work/cad-ui-test-data/d018b4bb75da4475b1fd75447603c1a0/cad-output/model.html')
report = json.loads((OUT / 'verification.json').read_text('utf-8'))
sources = list((ROOT / 'app/web/panels').glob('*.js')) + [ROOT / 'app/web/controller.js'] + [ROOT / ('simulation/viewer/' + name) for name in ['frozen_rule_controls.js', 'lite_doors.js', 'screening.js']] + [CAD]
lines = {p: p.read_text('utf-8').splitlines() for p in sources}
sentence = re.compile(r'입니다|합니다|않습니다|없습니다|아닙니다|하세요|됩니다|아님|표시용|별도|기준이며|검토용|설명|가정이며|전용|무작위 완주|임계값은 사용자 가정|가스 화염 표현 끔|위험 테두리:')

def origin(entry):
    text, node = entry['text'], entry.get('id') or ''
    if node == 'reviewCopy2_ck': return CAD, 110
    if node == 'v': return CAD, 417
    if node == 'reviewCopy1_liteMC':
        p=ROOT/'app/web/controller.js'
        return p,next(i for i,l in enumerate(lines[p],1) if "$('liteMC').textContent=c.progress_text" in l)
    preferred = []
    if node.startswith('building'): preferred = [ROOT / 'app/web/panels/building.js']
    elif node.startswith('r8') or node == 'cfbtFrozenRules': preferred = [ROOT / 'simulation/viewer/frozen_rule_controls.js']
    elif node.startswith('reviewCopy1'): preferred = [ROOT / 'app/web/panels/legacy_lite_panel.js']
    elif node.startswith(('reviewCopy2', 'reviewCopy3')): preferred = [CAD]
    elif node.startswith('reviewCopy4'): preferred = [ROOT / 'app/web/panels/legacy_overlay.js']
    elif node == 'liteScreening': preferred = [ROOT / 'simulation/viewer/screening.js']
    elif node == 'liteDoorClasses': preferred = [ROOT / 'simulation/viewer/lite_doors.js']
    elif node == 'resultMCBasis': return ROOT / 'app/web/panels/results.js', next(i for i,l in enumerate(lines[ROOT / 'app/web/panels/results.js'], 1) if "$('resultMCBasis').replaceChildren" in l)
    for p in preferred + sources:
        for i, line in enumerate(lines[p], 1):
            if text in line or (len(text) > 18 and text[:18] in line): return p, i
    if node.startswith('building'):
        p = ROOT / 'app/web/panels/building.js'
        marker = 'buildingFuel' if node == 'buildingFuel' else "$('buildingDoors').replaceChildren"
        return p, next(i for i,l in enumerate(lines[p],1) if marker in l and 'for(const row' in l)
    if node.startswith('r8') or node=='cfbtFrozenRules':
        p=ROOT/'simulation/viewer/frozen_rule_controls.js'
        needle = 'schema.assumption' if '프로젝트 가정' in text else '부분 결과:' if text.startswith('부분 결과:') else 'report.complete?' if '완료 ·' in text else 'const paragraph='
        return p,next(i for i,l in enumerate(lines[p],1) if needle in l)
    if node=='liteScreening': return ROOT/'simulation/viewer/screening.js',39
    return ROOT/'app/web/panels/legacy_lite_panel.js',31

rows=[];seen=set()
after={e['text'] for e in report['modernText']}
for e in report['stage3Text']:
    t=e['text'];node=e.get('id') or ''
    if t in seen or not (sentence.search(t) or node=='reviewCopy2_ck' or (node=='buildingFuel' and '근거:' in t) or (node=='v' and t.startswith('드래그:'))): continue
    if t=='가정과 한계' or node=='reviewCopy1_liteLimits' or t.startswith('연기 무늬·온도색·불투명도는 표시용입니다.'): continue
    # Button/section titles, values and CAD source names are not explanatory sentences.
    if e['tag']=='BUTTON' or (node=='reviewCopy4_cfbtGasReplay'): continue
    seen.add(t);p,line=origin(e)
    remains=t in after
    reason='도면 인식·연결 검토가 필요한 개별 진단이므로 유지.' if node=='reviewCopy2_ck' else '마우스·터치 조작 방법은 목업에서 지정한 조작 힌트이므로 유지.' if node=='v' else '숫자·실행 상태를 보존하고 설명만 ⓘ로 분리.' if node=='liteScreening' and t.startswith('저장된 비교:') else '모델·표시·검토 범위 설명을 ⓘ data-tip으로 이동.'
    rows.append(dict(file=str(p),line=line,text=t,action='유지' if remains else 'ⓘ로 이동',reason=reason))

def cell(s): return str(s).replace('|','\\|').replace('\n','<br>')
def table(items):
    return '\n'.join(['| 파일 · 줄 | 문구 | 처리 | 사유 |','|---|---|---|---|']+[f'| [{Path(r["file"]).name}:{r["line"]}](<{r["file"]}:{r["line"]}>) | {cell(r["text"])} | {r["action"]} | {r["reason"]} |' for r in items])

retained=[r for r in rows if r['action']=='유지'];moved=[r for r in rows if r['action']!='유지']
body='# 항목 6 — 설명문 전수 점검\n\n'
body+='기준: 직전 d1d06a2 번들과 최종 운영 번들. 패널 4개·HUD·범례·하단, 접힌 규칙 설정과 전체 메뉴 검토의 DOM도 포함했습니다. `data-tip` 및 가정과 한계 본문은 점검 대상에서 제외합니다. 표는 문장뿐 아니라 설명형 단편과 CAD 진단도 넓게 포함합니다. 숫자·표 머리글·실명·설정 라벨은 문장으로 세지 않습니다. 외부 CAD 파일은 수정하지 않았고, 해당 파일의 줄은 진단/조작 안내 생성 위치입니다. 동적 문구는 생성하는 파일·줄로 표시합니다.\n\n'
body+=f'이동 {len(moved)}개, 유지 {len(retained)}개(중복 문구 제외). 유지 항목은 아래와 같이 도면 진단 및 조작 안내입니다. 모델 설명은 ⓘ로 옮겼습니다. 기존 title-only ⓘ도 data-tip으로 통일했습니다.\n\n## 본문에 유지한 문구\n\n'+table(retained)
body+='\n\n## 이동한 문구\n\n'+table(moved)
body+='\n\n## 조건부 오류·상태 안내(유지)\n\n'
states=[('app/web/panels/display.js','0 이상이며 주의 ≤ 테두리로 입력하세요.','유효한 임계값 입력을 위해 필요한 오류 안내.'),('app/web/controller.js','적격 실 범위의 N과 화점을 선택하세요.','실행 요청 전 입력 수정이 필요한 안내.'),('app/web/controller.js','문 목록 읽기 실패 · ','읽기 실패를 숨기지 않기 위한 오류 상태.'),('app/web/controller.js','저장 실패 · ','저장 실패 시 미반영 상태를 알리기 위한 안내.'),('app/web/controller.js','탐색 목록 읽기 실패 · ','목록 부재와 읽기 오류를 구분하기 위한 안내.'),('simulation/viewer/frozen_rule_controls.js','r8 결과를 읽을 수 없습니다.','기존 검토 모듈 오류를 사용자에게 전달.'),('simulation/viewer/screening.js','완료된 비교가 없습니다.','저장된 결과의 부재를 표시.'),('simulation/viewer/screening.js','순차 계산 시작. 결과 새로고침으로 확인하세요.','실행 중 상태를 확인하는 조작 안내.'),('simulation/viewer/screening.js','현재 문 설정과 저장된 비교 조건이 다릅니다.','다른 설정의 결과를 현재 결과로 오인하지 않도록 상태 경고.')]
items=[]
for file,text,reason in states:
 p=ROOT/file;line=next(i for i,l in enumerate(p.read_text('utf-8').splitlines(),1) if text in l)
 items.append(dict(file=str(p),line=line,text=text+'{오류 내용}' if text.endswith(' · ') else text,action='유지',reason=reason))
body+=table(items)
body+='\n\n## 검증\n\n- 1440×1080 및 390×844: 건물·탐색·결과·표시, 8장. `screenshots.html`에서 전체 확인.\n- S09 1800 s / 1420 s, S06 890 s, 전체 건물 코어 ON: clock 180000 ms, 같은 카메라·1000×600 WebGL 영역. 이번에는 위험도 ON으로 비교.\n- 작전 기호 초기 OFF, 위험 토글 4+1 왕복 상태 일치, legacy 캔버스·범례 각 1개.\n- 키보드 ⓘ·Escape, 동적 규칙 설명 재처리, dispose 구독·자원·툴팁 DOM 0. POST 0.\n- 엔진·셰이더·render_order·서버 SHA 확인은 `frozen-sha.json`, 픽셀은 `pixel-comparison.json`, 세부 브라우저 수치는 `verification.json`.\n- 기존 CAD 오류 진단은 삭제하지 않았습니다. 새 설명을 추가할 때는 infoTip/data-tip을 사용해야 하며, 이 검사는 현재 소스와 저장 사례 기준입니다.\n'
(OUT/'text-audit.md').write_text(body,'utf-8',newline='\n')
(OUT/'text-audit.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n','utf-8',newline='\n')

repo=ROOT/'simulation/results/github-publish-20261026'
files=['simulation/viewer/legacy_real_view.js','simulation/viewer/legacy_real_bridge.js','simulation/viewer/frozen_rule_controls.js','app/web/scene/render_order.js','tools/serve_cfbt_building.py','tools/lite_screening_service.py']
hashes=[]
for file in files:
 old=subprocess.check_output(['git','-c','safe.directory='+str(repo),'-C',str(repo),'show','HEAD:PyroCast/'+file])
 current=(ROOT/file).read_bytes()
 hashes.append(dict(file=file,before_sha256=hashlib.sha256(old).hexdigest(),after_sha256=hashlib.sha256(current).hexdigest(),unchanged=old==current))
frozen=json.loads((ROOT/'simulation/results/ui_refactor_stage0_20261026/verification.json').read_text('utf-8'))
assert all(r['unchanged'] for r in hashes) and frozen['frozen_unchanged']
(OUT/'frozen-sha.json').write_text(json.dumps(dict(files=hashes,stage0=frozen),ensure_ascii=False,indent=2)+'\n','utf-8',newline='\n')
gallery='<!doctype html><meta charset="utf-8"><title>항목 6 탭 캡처</title><style>body{background:#142b3b;color:white;font:16px system-ui}section{margin:30px 0}img{max-width:100%;border:1px solid #698493}a{color:#42e8ff}</style><h1>항목 6 · 8장</h1><a href="text-audit.md">문구 목록</a>'
for size,label in [('desktop','데스크톱 1440'),('mobile','모바일 390')]:
 for tab,name in [('building','건물'),('explore','탐색'),('result','결과'),('display','표시')]:gallery+=f'<section><h2>{label} · {name}</h2><img src="{tab}-{size}.png"></section>'
(OUT/'screenshots.html').write_text(gallery,'utf-8',newline='\n')
print(json.dumps(dict(moved=len(moved),retained=len(retained),frozen=True),ensure_ascii=False))
