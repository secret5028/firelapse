"""CAD extraction + optional aligned fire evidence + auditable deliverables.

python cad_pipeline.py input.dxf output_dir --floor 4F
    --fire-json old/4F_fire.json --fire-reference-plan old/4F.json
DWG input requires --dwg2dxf executable or DWG2DXF environment variable.
"""
import argparse
import copy
import hashlib
import html
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import numpy as np
import cv2
from cad_plan import run
from cad_evidence import analyze_fire, fuse_fire, quality_report, geometry


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def save(path,data): Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')


def verify_fire_frame(plan, fire, reference, floor):
    """Reuse a cached registration only against its matching reference plan.

    This checks coordinate consistency, not survey accuracy or CAD revision equality.
    """
    if reference is None: return False, 'missing_reference_plan'
    if floor and Path(reference).stem.casefold()!=floor.casefold(): return False,'floor_mismatch'
    ref=read(reference)
    a=geometry(plan.get('footprint',[])); b=geometry(ref.get('footprint',[]))
    if a.is_empty or b.is_empty: return False,'missing_footprint'
    overlap=a.intersection(b).area/max(a.union(b).area,1e-9)
    alignment=fire.get('align',{})
    valid=bool(alignment) and all(isinstance(v,list) and len(v)>=3 and v[2]>=4 and
        (len(v)<4 or v[3]<=50) for v in alignment.values())
    same=overlap>=.99 and a.hausdorff_distance(b)<=.1
    return bool(valid and same),dict(mode='cached_registration_reference_check',footprint_iou=round(overlap,6),
        original_alignment=alignment, reference_sha256=digest(reference),
        note='기존 소방 심볼 좌표 재사용; 소방 원본의 새 심볼 추출은 아님')


def write_source_svg(plan,path):
    ra=plan['raster']; scale=1000/ra['R']; ox=ra['x0']/1000; oy=ra['y1']/1000
    def xy(p): return ((p[0]-ox)*scale,(oy-p[1])*scale)
    lines=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ra["W"]} {ra["H"]}" role="img" aria-label="CAD source vectors">',
        '<rect width="100%" height="100%" fill="white"/>']
    for v in plan.get('source_vectors',[]):
        pts=' '.join(f'{x:.4f},{y:.4f}' for x,y in map(xy,v['points']))
        color=dict(wall='#30343b',column='#8d3030',door='#159447',window='#087bd5').get(v['category'],'#888')
        dash=' stroke-dasharray="6 4" opacity=".35"' if v['excluded_from_boundary'] else ''
        tag='polygon' if v['closed'] else 'polyline'
        # ARC retains a true SVG arc. Other curves keep their labelled tessellation.
        if v['entity']=='ARC' and v.get('arc'):
            cx,cy,r,a0,a1=v['arc']; angle=math.radians(a0); end=math.radians(a1)
            p0=xy((cx+r*math.cos(angle),cy+r*math.sin(angle))); p1=xy((cx+r*math.cos(end),cy+r*math.sin(end)))
            d=f'M {p0[0]} {p0[1]} A {r*scale} {r*scale} 0 {int((a1-a0)%360>180)} 0 {p1[0]} {p1[1]}'
            element=f'<path d="{d}"'
        else: element=f'<{tag} points="{pts}"'
        lines.append(f'{element} fill="none" stroke="{color}" stroke-width="1.4"{dash}><title>{html.escape(v["id"]+" "+v["layer"])}</title></'+('path' if v['entity']=='ARC' and v.get('arc') else tag)+'>')
    lines.append('</svg>'); Path(path).write_text('\n'.join(lines),encoding='utf-8')


def render_fused(plan,base,path):
    ra=plan['raster']
    def xy(x,y): return (round((x*1000-ra['x0'])/ra['R']),round((ra['y1']-y*1000)/ra['R']))
    image=np.full((ra['H'],ra['W'],3),255,np.uint8)
    def paint(parts,color):
        for part in parts:
            outer=part['o'] if isinstance(part,dict) else part
            holes=part.get('h',[]) if isinstance(part,dict) else []
            mask=np.zeros(image.shape[:2],np.uint8)
            cv2.fillPoly(mask,[np.int32([xy(x,y) for x,y in outer])],255)
            for hole in holes:cv2.fillPoly(mask,[np.int32([xy(x,y) for x,y in hole])],0)
            image[mask>0]=color
    rng=np.random.default_rng(7)
    for r in plan['rooms']:paint(r['polys'],tuple(int(x) for x in rng.integers(170,245,3)))
    paint(plan['walls'],(60,60,60))
    for o in plan['openings']:
        color=(0,165,0) if o['kind'].startswith('door') else (230,160,80)
        paint(o.get('geometry_polys') or o['polys'],color)
        for leaf in o.get('leaves',[]):
            cv2.line(image,xy(*leaf['hinge']),xy(*leaf['closed']),(0,85,0),2)
            from cad_swing import swing_points
            pts=[xy(*q) for q in swing_points(leaf)]
            cv2.polylines(image,[np.int32(pts)],False,(0,120,0),1,cv2.LINE_AA)
    for r in plan['rooms']:
        pos=xy(*r['center']);cv2.putText(image,r['id'],(pos[0]-8,pos[1]),cv2.FONT_HERSHEY_SIMPLEX,.45,(30,30,30),1)
    for o in plan['openings']:
        if o.get('kind_before_fire'):
            for p in o['polys']:
                cv2.fillPoly(image,[np.array([xy(x,y) for x,y in p],np.int32)],(30,180,40))
    for s in plan.get('fire',{}).get('symbols',[]):
        p=xy(s['x'],s['y']); color=(40,40,230)
        if s['kind']=='detector':
            cv2.circle(image,p,9,color,2,cv2.LINE_AA)
            cv2.circle(image,p,3,color,-1,cv2.LINE_AA)
        elif s['kind']=='exit_sign':
            color=(0,130,0) if s.get('opening') else (180,60,150)
            cv2.rectangle(image,(p[0]-7,p[1]-7),(p[0]+7,p[1]+7),color,2)
        elif s['kind']=='corridor_light': cv2.drawMarker(image,p,(220,90,0),cv2.MARKER_TRIANGLE_UP,16,2)
        elif s['kind']=='hydrant': cv2.drawMarker(image,p,(0,120,230),cv2.MARKER_CROSS,18,2)
    cv2.imencode('.png',image)[1].tofile(str(path))


def write_viewer(out,plan):
    fire=plan.get('fire',{}); symbols=fire.get('symbols',[])
    counts={k:sum(s['kind']==k for s in symbols) for k in ('detector','exit_sign','corridor_light')}
    q=plan['quality']; st=plan['stats']
    rows=''.join(f'<li><b>{html.escape(c["rule"])}</b> {html.escape(str(c.get("id","")))} — {html.escape(c.get("note",""))}</li>' for c in plan['checks'])
    document='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CAD 평면 추출 · 소방도면 보조 판정</title><style>
*{box-sizing:border-box}body{margin:0;background:#f3f5f8;color:#1b2738;font:15px/1.6 system-ui,'Malgun Gothic',sans-serif}
header{padding:20px 28px;background:white;border-bottom:1px solid #ccd5e0}h1{font-size:23px;margin:0 0 8px}p{margin:5px 0}nav{display:flex;gap:8px;margin-top:14px;flex-wrap:wrap}button{padding:8px 14px;border:1px solid #ccd5e0;background:white;border-radius:7px;cursor:pointer}.on{background:#173d67;color:white}
main{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:18px;padding:18px}#canvas{height:76vh;overflow:auto;background:white;border:1px solid #d7dfe8}#drawing{display:block;width:100%;max-width:none}aside{background:white;padding:16px;max-height:76vh;overflow:auto}h2{font-size:17px}li{margin:10px 0;font-size:13px}a{color:#145a9c}@media(max-width:850px){main{grid-template-columns:1fr}aside{max-height:none}}
</style><header><h1>CAD 평면 추출 · 소방도면 보조 판정</h1><p>__SUMMARY__</p><p>CAD 선은 원본 좌표를 보존합니다. 실·벽 면은 __RES__ mm 격자로 산출합니다. 자동 판독 정확도는 도면 대조가 필요합니다.</p>
<p><a href="layers.html">전체 레이어 대조</a> · <a href="source_coverage.json">관련 도면 확인 기록</a></p><nav><button class="on" data-src="fused.png">소방 근거 통합 결과</button><button data-src="architecture_plan.png">건축 평면 추출</button><button data-src="source.svg">CAD 원본 벡터</button><label>확대 <input id="zoom" type="range" min="100" max="400" value="100"> <span id="z">100%</span></label></nav></header>
<main><section id="canvas"><img id="drawing" src="fused.png" alt="추출 평면"></section><aside><h2>표시와 검토</h2><p>빨강 ◎ 감지기(중앙점 있음)<br>빨강 ○ 건축선의 애매한 틈<br>초록 □ 개구부와 연결된 피난구유도등<br>보라 □ 확인할 문틀 또는 미연결 유도등<br>파랑 △ 통로유도등<br>주황 + 소화전</p><p>감지기가 없다는 이유로 실을 지우지 않습니다. 유도등만으로 새 문을 만들지 않습니다.</p><p>__FIRE__</p><p>형상 검사 오류 __ERRORS__개. 검토 표시 __CHECKS__개.<br>표시는 확정 오류와 구별해야 합니다.</p><p><a href="plan.json">최종 평면 JSON</a> · <a href="quality.json">검사 결과</a></p><details><summary>전체 검토 항목</summary><ul>__ROWS__</ul></details></aside></main>
<script>const im=document.getElementById('drawing');document.querySelectorAll('[data-src]').forEach(b=>b.onclick=()=>{im.src=b.dataset.src;document.querySelectorAll('[data-src]').forEach(x=>x.classList.toggle('on',x===b))});document.getElementById('zoom').oninput=e=>{im.style.width=e.target.value+'%';document.getElementById('z').textContent=e.target.value+'%'};</script></html>'''
    summary=f'{plan.get("floor", "")} · 실 {st["rooms"]} · 문 {st["doors_open"]} · 창 {st["windows"]} · 실내창 {st["windows_inner"]} / 감지기 {counts["detector"]} · 피난구유도등 {counts["exit_sign"]} · 통로유도등 {counts["corridor_light"]}'
    for key,value in dict(SUMMARY=html.escape(summary),RES=round(plan['res_m']*1000,2),FIRE='소방 좌표: 기존 정렬과 기준 평면 일치 확인' if fire.get('alignment_verified') else '소방 좌표 미확인 또는 소방 자료 미입력 — 자동 보정 없음',ERRORS=q['errors'],CHECKS=len(plan['checks']),ROWS=rows).items(): document=document.replace('__'+key+'__',str(value))
    (out/'index.html').write_text(document,encoding='utf-8')


def finalize_plan(base, out, *, floor=None, fire_json=None, fire_reference_plan=None, input_source=None, base_image=None):
    out=Path(out); out.mkdir(parents=True,exist_ok=True)
    base['floor']=floor
    from cad_review_rules import apply_space_review
    base=apply_space_review(base)
    from cad_auto import isolate_elevator_cores
    from cad_connectivity import recover_connections, build_graph
    plan=isolate_elevator_cores(base)
    plan=recover_connections(plan)
    if fire_json:
        fire=read(fire_json)
        verified,registration=verify_fire_frame(base,fire,fire_reference_plan,floor)
        evidence=analyze_fire(plan,fire.get('symbols',[]),alignment_verified=verified)
        evidence['registration']=registration
        evidence['source_sha256']=digest(fire_json)
        save(out/'fire_evidence.json',evidence)
        plan=fuse_fire(plan,evidence)
    for d in plan.get('cad_diagnostics',[]):
        plan['checks'].append(dict(rule='CAD입력-누락가능',id=d.get('block',''),note=json.dumps(d,ensure_ascii=False)))
    from cad_host import apply_host_axioms
    plan=apply_host_axioms(plan)
    from cad_review_rules import apply_candidate_review
    plan=apply_candidate_review(plan)
    from cad_core_contract import normalize_cores
    plan=normalize_cores(plan)
    plan['provenance'].update(input_sha256=digest(input_source) if input_source else base['provenance']['source_sha256'],
        evidence_code_sha256={n:digest(Path(__file__).with_name(n)) for n in ('cad_pipeline.py','cad_evidence.py','cad_connectivity.py','cad_host.py','cad_source_audit.py','cad_swing.py','cad_core_contract.py')})
    plan['quality']=quality_report(plan)
    plan['simulation_graph']=build_graph(plan['rooms'],plan['openings'])
    for rid in plan['simulation_graph']['isolated_rooms']:
        plan['checks'].append(dict(rule='AUTO연결미확정실유지',id=rid,note='공간을 유지하며 연결 근거 부족을 표시. 문 또는 외기 연결을 임의 생성하지 않음'))
    save(out/'plan.json',plan); save(out/'quality.json',plan['quality'])
    save(out/'simulation_graph.json',plan['simulation_graph'])
    save(out/'rejected_openings.json',plan.get('rejected_openings',[]))
    if base_image and Path(base_image).resolve()!=(out/'architecture_plan.png').resolve():
        import shutil
        shutil.copy2(base_image,out/'architecture_plan.png')
    write_source_svg(plan,out/'source.svg'); render_fused(plan,out/'architecture_plan.png',out/'fused.png'); write_viewer(out,plan)
    from cad_source_audit import write_layer_viewer
    write_layer_viewer(plan,out/'layers.html')
    save(out/'source_coverage.json',plan.get('source_coverage',dict(status='drawing_manifest_not_supplied')))
    return plan


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('input'); ap.add_argument('out'); ap.add_argument('--floor')
    ap.add_argument('--map',default=str(Path(__file__).with_name('layer_map.json')))
    ap.add_argument('--res',type=float,default=.02); ap.add_argument('--dwg2dxf')
    ap.add_argument('--fire-json'); ap.add_argument('--fire-reference-plan')
    ap.add_argument('--review-profile',help='Optional reviewed exceptions bound to the exact DXF hash')
    ap.add_argument('--drawing-manifest',help='Inventory of source drawings, floor roles, revisions and review coverage')
    a=ap.parse_args(argv); source=Path(a.input).resolve(); out=Path(a.out).resolve(); out.mkdir(parents=True,exist_ok=True)
    dxf=source
    if source.suffix.lower()=='.dwg':
        exe=a.dwg2dxf or os.environ.get('DWG2DXF')
        if not exe: ap.error('DWG 입력은 --dwg2dxf 또는 DWG2DXF가 필요합니다.')
        dxf=out/'input.dxf'
        with (out/'conversion.log').open('w',encoding='utf-8') as log:
            subprocess.run([exe,'-y','-o',str(dxf),str(source)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
    base=run(str(dxf),str(out/'architecture'),a.map,a.res,floor=a.floor,
             review_profile=read(a.review_profile) if a.review_profile else None)
    if a.drawing_manifest:
        from cad_source_audit import verify_drawing_manifest
        base['source_coverage']=verify_drawing_manifest(a.drawing_manifest,dxf,a.floor)
    plan=finalize_plan(base,out,floor=a.floor,fire_json=a.fire_json,fire_reference_plan=a.fire_reference_plan,input_source=source)
    print(json.dumps(dict(output=str(out),stats=plan['stats'],quality=plan['quality']['status'],errors=plan['quality']['errors'],
        fire_symbols=len(plan.get('fire',{}).get('symbols',[])),checks=len(plan['checks'])),ensure_ascii=False))
    return 2 if plan['quality']['errors'] else 0


if __name__=='__main__': sys.exit(main())
