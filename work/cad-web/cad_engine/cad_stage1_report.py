"""Publish stage-1 source grouping, text metadata and aligned core evidence."""
import argparse,json,html,re,hashlib,shutil
from pathlib import Path
import ezdxf
from cad_review_ui import enhance_review
from cad_evidence import geometry,polygon_parts

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def esc(x):return html.escape(str(x))
def texts(entities,depth=0):
    for e in entities:
        if e.dxftype() in ('TEXT','MTEXT'):yield e
        elif e.dxftype()=='INSERT' and depth<12:
            yield from texts(e.virtual_entities(),depth+1)
STYLE='body{font:16px/1.6 system-ui,"Malgun Gothic";background:#edf2f6;color:#21374c;margin:0}header,main{padding:22px;max-width:1350px;margin:auto}a{color:#086698}table{width:100%;border-collapse:collapse;background:white}td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left}.card{background:white;padding:18px;border-radius:12px;margin:16px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}.card img{width:100%;height:210px;object-fit:contain}nav{display:flex;gap:15px;flex-wrap:wrap}.note{background:#fff2d3;padding:14px}button{padding:9px;cursor:pointer}svg text{font-family:system-ui;font-weight:bold;paint-order:stroke;stroke:white;stroke-width:4px;stroke-linejoin:round}'

def metadata(source,plan):
    doc=ezdxf.readfile(source);rows=[]
    for e in texts(doc.modelspace()):
        try:
            s=(e.dxf.text if e.dxftype()=='TEXT' else e.plain_text()).strip()
            if not re.search(r'층|SL|FL|GL|주차|PARKING|창고|사무|공장|기계실|계단|승강|ELEV|축척|SCALE|1\s*[:/]\s*\d+',s,re.I):continue
            rows.append(dict(text=s,point=[e.dxf.insert.x*plan['unit_m'],e.dxf.insert.y*plan['unit_m']],layer=e.dxf.layer))
        except (AttributeError,TypeError):continue
    return dict(method='native_CAD_text',ocr_status='not_needed_for_vector_text; raster references not registered',
        drawing_unit_m=plan['unit_m'],scale_candidates=[r for r in rows if re.search(r'축척|SCALE|1\s*[:/]\s*\d+',r['text'],re.I)],
        height_candidates=[r for r in rows if re.search(r'층고|SL|FL|GL',r['text'],re.I)],texts=rows)

def core_page(out,p,f,building):
    ra=p['raster'];xy=lambda x,y:((x*1000-ra['x0'])/ra['R'],(ra['y1']-y*1000)/ra['R'])
    overlays=[];lists=[]
    for r in p['ramps']:
        for part in r['polys']:
            points=' '.join(f'{x:.2f},{y:.2f}' for x,y in [xy(*q) for q in part['o']])
            overlays.append(f'<polygon points="{points}" fill="#ff981d" fill-opacity=".3" stroke="#c56c00" stroke-width="4"><title>차량 램프 · 계단 코어에서 제외 · 상하단 연결 미확정</title></polygon>')
        lists.append(f'<li>차량 램프 {r["id"]}: 곡선 구간 폭 약 {r["width_m"]}m · 계단과 분리</li>')
    for c in p['cores']:
        x,y=xy(c['cx']-c['w']/2,c['cy']+c['h']/2);w=c['w']*1000/ra['R'];h=c['h']*1000/ra['R']
        ss=[s for s in building['shafts'] if s['core_ids'].get(f['name'])==c['core_id']]
        color='#008984' if c['kind']=='stair' else '#8854b5';name='계단' if c['kind']=='stair' else '승강기'
        status=' → '.join(ss[0]['floors']) if ss else '다른 층 대응 없음 · 독립 후보'
        label=f'{name} {c["core_id"]}'
        overlays.append(f'<g><rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{color}" fill-opacity=".18" stroke="{color}" stroke-width="4"/><text x="{x}" y="{y-8}" font-size="27" fill="{color}">{label}</text><title>{esc(status)}</title></g>')
        lists.append(f'<li><b style="color:{color}">{label}</b> — {esc(status)}<br>대응 공간: {esc(", ".join(c["access_room_ids"]) or "미확정")} · {"독립 계단/승강기 실" if c.get("room_id") else "공간 내부의 코어 위치 — 전체 실을 승강로로 바꾸지 않음"}</li>')
    doc=f'''<!doctype html><html lang="ko"><meta charset="utf-8"><title>{f['name']} · 코어·램프 대조 v9</title><style>{STYLE}#viewport{{overflow:auto;max-height:78vh;background:white}}#drawing{{display:block;width:100%}}</style><header><h1>{f['name']} · 계단·승강기·램프 대조</h1><nav><a href="../index.html">전층 결과</a><a href="index.html">벽·문·창 추출</a><a href="layers.html">모든 원본 레이어</a><a href="floor_metadata.json">텍스트 정보</a></nav><p>용도: {esc(f['use'])} · 정렬: {esc(f['align'])}</p><button onclick="document.getElementById('bg').setAttribute('href','source.svg')">원본 벡터</button> <button onclick="document.getElementById('bg').setAttribute('href','fused.png')">추출 평면</button> <label>확대 <input type="range" min="100" max="400" value="100" oninput="document.getElementById('drawing').style.width=this.value+'%'"></label><p>청록: 계단 / 보라: 승강기 / 주황: 차량 램프. 코어 박스는 정렬 기준 영역입니다.</p></header><main><div id="viewport"><svg id="drawing" viewBox="0 0 {ra['W']} {ra['H']}" xmlns="http://www.w3.org/2000/svg"><image id="bg" href="source.svg" width="{ra['W']}" height="{ra['H']}"/>{''.join(overlays)}</svg></div><div class="card"><ul>{''.join(lists)}</ul></div></main></html>'''
    (out/'코어검토.html').write_text(doc,encoding='utf-8')

def publish(root,manifest_path):
    root=Path(root);manifest=read(manifest_path);b=read(root/'building.json');rows=[];cards=[];clusters=[]
    for f in b['floors']:
        out=root/('office-'+f['name']);p=read(out/'plan.json')
        primary=next(r for r in manifest['drawings'] if r.get('role')=='architectural_plan' and r.get('floor')==f['name'])
        related=[r for r in manifest['drawings'] if r.get('floor')==f['name'] or f['name'] in r.get('floors',[])]
        meta=metadata(primary['path'],p);meta.update(selected_use=f['use'],level_GL_m=b['levels'][len(rows)],floor_height_m=f['h'],height_source='previously reviewed CAD level annotations',alignment=f['align'])
        save(out/'floor_metadata.json',meta)
        clusters.append(dict(building=manifest['building'],floor=f['name'],drawings=related,unregistered_raster_references=[r for r in related if r['role']=='raster_reference']))
        items=enhance_review(out)
        page=(out/'index.html').read_text(encoding='utf8')
        if '평면 추출 v9' not in page:
            page=page.replace('<h2>표시와 검토</h2>',f'<h2>{f["name"]} · 평면 추출 v9</h2><p><a href="../index.html">전층 결과</a> · <a href="코어검토.html">계단·승강기·램프 대조</a></p><h2>표시와 검토</h2>')
        page=page.replace("document.querySelector('button[data-src=\"connectivity.svg\"]').click();","document.querySelector('button[data-src=\"fused.png\"]').click();")
        (out/'index.html').write_text(page,encoding='utf8');core_page(out,p,f,b)
        overlap=sum(geometry(polygon_parts(r)).intersection(geometry(p['walls'])).area for r in p['rooms'])
        old=read(root.parent/'CAD-문호표현-v8'/out.name/'plan.json')
        assert p['quality']['errors']==0 and overlap<.001
        assert [r['id'] for r in p['rooms']]==[r['id'] for r in old['rooms']]
        assert all('xcorr' not in f['align'] and 'unconfirmed' not in f['align'] for f in b['floors'])
        rows.append(dict(floor=f['name'],use=f['use'],rooms=len(p['rooms']),openings=len(p['openings']),ramps=len(p['ramps']),cores=len(p['cores']),quality_errors=p['quality']['errors'],wall_room_overlap_m2=overlap,alignment=f['align'],shift=f['shift'],source_sha256=p['provenance']['source_sha256'],excluded=p['simulation_graph']['excluded_openings']))
        cards.append(f'<article class="card"><h2>{f["name"]} · {esc(f["use"])}</h2><a href="{out.name}/코어검토.html"><img src="{out.name}/fused.png"></a><p>공간 {len(p["rooms"])} · 코어 {len(p["cores"])} · 램프 {len(p["ramps"])}</p><nav><a href="{out.name}/코어검토.html">코어·램프 대조</a><a href="{out.name}/index.html">추출 평면</a><a href="{out.name}/layers.html">전체 레이어</a></nav></article>')
    assert b['floors'][0]['use']=='parking'
    bp=read(root/'office-B1/plan.json');assert len(bp['ramps'])==1 and not any(o['id']=='D0' for o in bp['openings'])
    stairs=[s for s in b['shafts'] if s['kind']=='stair']
    assert sorted(len(s['floors']) for s in stairs)==[8,9]
    assert all(min(s['overlaps'])>=.6 for s in b['shafts'])
    assert len(b['vertical_connections'])==35
    links=dict(schema_version=1,floors=[dict(name=f['name'],shift=f['shift'],scale=f['scale'],align=f['align'],z=f['z'],h=f['h']) for f in b['floors']],nodes=b['core_nodes'],connections=b['vertical_connections'],groups=b['shafts'],unmatched=b['unconfirmed_vertical_cores'])
    save(root/'층간연결.json',links);save(root/'층별도면묶음.json',clusters)
    report=dict(scope='stage_1_only',floors=rows,vertical_links=len(b['vertical_connections']),groups=[dict(kind=s['kind'],floors=s['floors'],overlaps=s['overlaps']) for s in b['shafts']],unmatched=b['unconfirmed_vertical_cores'],checks='geometry consistency and CAD core correspondence; not fire physics validation',known_limits=['램프 곡선 구간만 추출. 상하단 표고·외기 연결 미확정','B1/1F 각각 추가 계단 후보 1개는 다른 층 대응 근거가 없어 연결하지 않음','3F R27 실내외 미확정 상태 유지','스캔 소방 PDF 자동 좌표 등록·OCR 융합은 미적용'])
    save(root/'검증결과.json',report)
    table=''.join(f'<tr><td>{"계단" if s["kind"]=="stair" else "승강기"}</td><td>{" → ".join(s["floors"])}</td><td>{min(s["overlaps"]):.0%}</td></tr>' for s in b['shafts'])
    (root/'index.html').write_text(f'<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>평면 추출 · 코어 연결 v9</title><style>{STYLE}</style><header><h1>1단계 평면 추출 · 전층 v9</h1><p>B1 · 1~7층 · 옥탑 — CAD 9개 층 재추출</p><nav><a href="office-B1/코어검토.html">지하주차장·램프 확인</a><a href="층간연결.json">층간 연결 데이터</a><a href="층별도면묶음.json">층별 도면 묶음</a><a href="검증결과.json">검증 기록</a><a href="설명과실행.txt">변경·실행 안내</a></nav><div class="card">B1 용도: 주차장 / 차량 램프 1개 분리 / 램프 주변 D0 후보 제거<br>전층 계단·승강기 기준 정렬 / 코어 5개 계통 · 인접 층 연결 35개</div><table><tr><th>코어</th><th>연결 층</th><th>최소 대응 영역 겹침</th></tr>{table}</table><p class="note">추가 계단 후보 B1·1F 각 1개는 층간 연결에서 제외했습니다. 램프 상하단·외기 연결은 미확정입니다. 정렬·연결 데이터 검증이며 화재 해석 검증은 아닙니다.</p></header><main class="grid">{"".join(cards)}</main></html>',encoding='utf8')
    code=root/'code';code.mkdir(exist_ok=True)
    for src in Path(__file__).parent.iterdir():
        if src.suffix in ('.py','.json','.html') or src.name=='requirements-extraction.txt':shutil.copy2(src,code/src.name)
    save(root/'코드해시.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in code.iterdir()})
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root');ap.add_argument('manifest');a=ap.parse_args();publish(a.root,a.manifest)
