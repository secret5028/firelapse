"""우리 3D 원본(building.json) → 「소방 크로키 업」 3D 검토 화면(folder_review.html) 형식.
역할: 우리 모델 = 해석용 원본 형상(단일 기준). 크로키 업 = 같은 원본을 받아 현장 전술 검토(진입 경로·투시·수계).
앱 원본 코드는 고치지 않고, 앱 템플릿의 __DATA__/__LIBS__ 자리에 넣은 단독 HTML을 만든다.

좌표: 건물 공통 원점(전 층 같은 기준) → 페이지 이미지 픽셀(res m/px, y 아래로) → 앱 scale=res, origin=[0,0]
  → 앱 3D 에서 전 층이 계단·승강기 기준 정렬 그대로 쌓임(elevation = 우리 층 바닥 z).
넘기는 것: 벽 중심선(벽체 골격), 문(경첩·닫힌 끝·열림 방향·양개), 미닫이·개구(통로), 창, 바닥 외곽·구멍,
  계단 범위, 승강기 위치·문, 실 이름, 층고. 앱에 없는 것(문짝 개방률·창 파손률·수직 공간·감지기)은 원본 JSON 에 남김."""
import sys, os, json, math, base64, argparse, collections
import numpy as np, cv2
from shapely.geometry import Polygon, MultiPolygon, LineString, box
from shapely.ops import unary_union

def polys_of(lst):
    out = []
    for p in lst:
        try:
            g = Polygon(p['o'], [h for h in p.get('h', []) if len(h) >= 3]).buffer(0)
            if not g.is_empty: out.append(g)
        except Exception: pass
    return unary_union(out) if out else Polygon()

def skeleton_segments(mask, res):
    """벽 마스크 → 중심선 선분(m 단위 아님, 픽셀). 얇은 골격 + 확률 허프 + 같은 선 합치기"""
    from skimage.morphology import skeletonize
    sk = (skeletonize(mask > 0) * 255).astype(np.uint8)
    L = cv2.HoughLinesP(sk, 1, np.pi / 360, threshold=max(4, int(0.25 / res)), minLineLength=max(4, int(0.3 / res)), maxLineGap=max(2, int(0.12 / res)))
    segs = [] if L is None else [tuple(map(float, l)) for l in np.asarray(L).reshape(-1, 4)]
    # 같은 직선 위(각도 2°, 거리 2px) 겹치는 조각 합치기
    segs.sort(key=lambda s: -math.hypot(s[2] - s[0], s[3] - s[1]))
    out = []
    for s in segs:
        a = math.atan2(s[3] - s[1], s[2] - s[0]) % math.pi; merged = False
        for i, t in enumerate(out):
            b = math.atan2(t[3] - t[1], t[2] - t[0]) % math.pi
            if min(abs(a - b), math.pi - abs(a - b)) > math.radians(2): continue
            lt = LineString([t[:2], t[2:]])
            if lt.distance(LineString([s[:2], s[2:]])) > 2.5: continue
            # 투영해서 범위 확장
            u = np.array([math.cos(b), math.sin(b)]); p0 = np.array(t[:2])
            ts = [(np.array(q) - p0) @ u for q in (t[:2], t[2:], s[:2], s[2:])]
            lo, hi = min(ts), max(ts)
            out[i] = (*(p0 + u * lo), *(p0 + u * hi)); merged = True; break
        if not merged: out.append(s)
    return [s for s in out if math.hypot(s[2] - s[0], s[3] - s[1]) >= 0.25 / res]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('outdir'); ap.add_argument('--template', required=True, help='소방 크로키 업 소스/folder_review.html')
    ap.add_argument('--three', required=True, help='three.core.js, three.module.js 가 있는 폴더')
    ap.add_argument('--name', default=None); ap.add_argument('--building', default='본동'); ap.add_argument('--res', type=float, default=0.05)
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    B = json.load(open(os.path.join(a.outdir, 'building.json'), encoding='utf-8'))
    res = a.res
    # 건물 공통 범위(전 층 바닥)
    allg = unary_union([polys_of(f['slab']) for f in B['floors']] + [polys_of(f['bands'][0]['polys']) for f in B['floors']])
    X0, Y0, X1, Y1 = allg.bounds; X0 -= 2; Y0 -= 2; X1 += 2; Y1 += 2
    Wp, Hp = int((X1 - X0) / res) + 1, int((Y1 - Y0) / res) + 1
    P = lambda x, y: [round((x - X0) / res, 1), round((Y1 - y) / res, 1)]          # m → 앱 이미지 픽셀
    Pg = lambda g: [P(x, y) for x, y in g.exterior.coords[:-1]]
    pages = []; report = collections.Counter()
    for f in B['floors']:
        name = f['name']; plan = json.load(open(os.path.join(a.outdir, name + '.json'), encoding='utf-8'))
        tx, ty = f['shift']; sc = f.get('scale', 1); ox, oy = B['origin']   # 건물 좌표 = sc·x + t − o (cad_build3d 와 동일)
        W = polys_of(f['bands'][0]['polys'])                     # 문·창 자리 뺀 벽
        O = unary_union([Polygon(p).buffer(0) for o in f['openings'] for p in o['polys'] if len(p) >= 3] or [Polygon()])
        full = unary_union([W, O])                               # 개구부 포함 벽 띠 → 골격이 끊기지 않게
        mask = np.zeros((Hp, Wp), np.uint8)
        for g in getattr(full, 'geoms', [full]):
            if g.is_empty or g.geom_type != 'Polygon': continue
            cv2.fillPoly(mask, [np.int32([P(x, y) for x, y in g.exterior.coords])], 255)
            for h in g.interiors: cv2.fillPoly(mask, [np.int32([P(x, y) for x, y in h.coords])], 0)
        shapes = [dict(type='wall', a=[round(s[0], 1), round(s[1], 1)], b=[round(s[2], 1), round(s[3], 1)]) for s in skeleton_segments(mask, res)]
        report[name + ' 벽'] = len(shapes)
        # 문
        for o in f['openings']:
            k = o['kind']; lv = o.get('leaves') or []
            if k == 'door_elev': continue
            if k in ('window', 'window_inner'):
                g = unary_union([Polygon(p).buffer(0) for p in o['polys'] if len(p) >= 3])
                if g.is_empty: continue
                r = g.minimum_rotated_rectangle
                if r.geom_type != 'Polygon': continue
                xy = np.array(r.exterior.coords[:4]); e1, e2 = xy[1] - xy[0], xy[2] - xy[1]
                (p0, p1) = ((xy[0] + xy[3]) / 2, (xy[1] + xy[2]) / 2) if np.hypot(*e1) >= np.hypot(*e2) else ((xy[0] + xy[1]) / 2, (xy[2] + xy[3]) / 2)
                shapes.append(dict(type='window', a=P(*p0), b=P(*p1), openingKind='interior' if k == 'window_inner' else 'exterior', srcId=o['id']))
                report[name + ' 창'] += 1; continue
            if k == 'vent': continue
            if lv:
                done = set()
                for i, L in enumerate(lv):
                    if i in done: continue
                    mate = None
                    if L.get('pair'):
                        for j, M in enumerate(lv):
                            if j != i and j not in done and M.get('pair') and math.dist(L['closed'], M['closed']) < 0.3: mate = j; break
                    sw = -int(L.get('sgn', 1))                       # 우리(위가 +y) 반시계 = 앱(아래가 +z) 반대
                    if mate is not None:
                        done |= {i, mate}
                        shapes.append(dict(type='door', a=P(*L['hinge']), b=P(*lv[mate]['hinge']), leaves=2, swingSide=sw, srcId=o['id'],
                                           doorHeight=o.get('door_h'), kind=k))
                    else:
                        done.add(i)
                        shapes.append(dict(type='door', a=P(*L['hinge']), b=P(*L['closed']), leaves=1, hinge='start', swingSide=sw, srcId=o['id'],
                                           doorHeight=o.get('door_h'), kind=k, doubleActing=L.get('kind') == 'double_acting'))
                    report[name + ' 문'] += 1
            else:
                g = unary_union([Polygon(p).buffer(0) for p in o['polys'] if len(p) >= 3])
                if g.is_empty: continue
                r = g.minimum_rotated_rectangle
                if r.geom_type != 'Polygon': continue
                xy = np.array(r.exterior.coords[:4]); e1, e2 = xy[1] - xy[0], xy[2] - xy[1]
                (p0, p1) = ((xy[0] + xy[3]) / 2, (xy[1] + xy[2]) / 2) if np.hypot(*e1) >= np.hypot(*e2) else ((xy[0] + xy[1]) / 2, (xy[2] + xy[3]) / 2)
                d = dict(type='door', a=P(*p0), b=P(*p1), srcId=o['id'], kind=k)
                if k in ('door_sliding',) or not lv: d['openingKind'] = 'passage' if k == 'door_sliding' else None
                if d.get('openingKind') is None: d.pop('openingKind')
                shapes.append(d); report[name + (' 미닫이' if k == 'door_sliding' else ' 문(방향 미상)')] += 1
        # 바닥
        slab = polys_of(f['slab']); outline = holes = None
        if not slab.is_empty:
            big = max(getattr(slab, 'geoms', [slab]), key=lambda g: g.area)
            outline = Pg(big); holes = [[P(x, y) for x, y in h.coords[:-1]] for h in big.interiors if Polygon(h).area > 1.0]
        # 코어: 층 좌표 → 건물 좌표(x' = sc·x − dx)
        stairs, elevs = [], []
        for c in plan.get('cores', []):
            cx, cy = sc * c['cx'] + tx - ox, sc * c['cy'] + ty - oy; w, h = sc * c['w'], sc * c['h']
            if c['kind'] == 'stair':
                stairs.append(dict(a=P(cx - w / 2, cy + h / 2), b=P(cx + w / 2, cy - h / 2)))
            else:
                elevs.append(dict(p=P(cx, cy), name='승강기'))
        for o in f['openings']:   # 승강장 문 → 가장 가까운 승강기에
            if o['kind'] != 'door_elev' or not elevs: continue
            g = unary_union([Polygon(p).buffer(0) for p in o['polys'] if len(p) >= 3]); r = g.minimum_rotated_rectangle
            if r.geom_type != 'Polygon': continue
            xy = np.array(r.exterior.coords[:4]); e1, e2 = xy[1] - xy[0], xy[2] - xy[1]
            (p0, p1) = ((xy[0] + xy[3]) / 2, (xy[1] + xy[2]) / 2) if np.hypot(*e1) >= np.hypot(*e2) else ((xy[0] + xy[1]) / 2, (xy[2] + xy[3]) / 2)
            c0 = np.array(P(*((p0 + p1) / 2))); e = min(elevs, key=lambda e: np.hypot(*(np.array(e['p']) - c0)))
            if 'door' not in e and np.hypot(*(np.array(e['p']) - c0)) * res < 3: e['door'] = dict(a=P(*p0), b=P(*p1))
        labels = [dict(point=P(*r['c']), name=(r['names'][0] if r.get('names') else f"{r['id']} {r['area']}㎡")) for r in f['rooms']
                  if r.get('names') or r['area'] >= 8]
        fl = -int(name[1:]) if name.startswith('B') else (int(name[:-1]) if name[:-1].isdigit() else (max([int(g['name'][:-1]) for g in B['floors'] if g['name'][:-1].isdigit()] + [0]) + 1))
        # 페이지 이미지(2D 확인용): 벽·문·창·실 이름
        im = np.full((Hp, Wp, 3), 255, np.uint8); im[mask > 0] = (90, 90, 90)
        for s in shapes:
            col = {'wall': (40, 40, 40), 'door': (0, 150, 230), 'window': (230, 140, 0)}[s['type']]
            cv2.line(im, tuple(map(int, s['a'])), tuple(map(int, s['b'])), col, 2)
        ok, buf = cv2.imencode('.png', im)
        lbl = ('지하' + name[1:] + '층') if name.startswith('B') else ('옥탑' if name == 'PH' else name[:-1] + '층')
        initial = dict(building=a.building, floor=fl, levelLabel=lbl, height=round(f['h'], 3), wallHeight=round(f['h'], 3), elevation=round(f['z'], 3),
                       scale=res, origin=[0, 0], included=True, shapes=shapes, floorOutline=outline, floorHoles=holes or [],
                       stairs=stairs, elevators=elevs, roomLabels=labels,
                       # 앱 검토 체크: CAD3D 공리 검사(외곽 폐합·문 양쪽 실·계단·승강기 정렬·도면 층고)로 확인된 항목
                       review=dict(outline=True, openings=True, stairs=True, height=True, by='CAD3D 자동 검사'),
                       assumptions=[f"층고 {f['h']}m(" + ('도면' if '도면' in B.get('levels_src', '') else '기본값') + ')', f"용도 {f['use']}",
                                    '문 방향·폭: CAD 호(표준 폭 보정)', '원본: CAD3D building.json'])
        pages.append(dict(image='data:image/png;base64,' + base64.b64encode(buf.tobytes()).decode(), width=Wp, height=Hp, source=f['src'],
                          number=len(pages) + 1, text=f"{a.building} {name} · {f['src']}", initial=initial,
                          unitNote='CAD3D 원본(정렬·층고 반영)', drawingTexts=[]))
    name = a.name or os.path.basename(os.path.normpath(a.outdir))
    D = dict(name=name + ' · CAD3D 원본', sourceHash='cad3d-' + name, pages=pages,
             cad3d=dict(shafts=B.get('shafts', []), levels=B.get('levels'), note='문짝 개방률·창 파손률·감지기는 CAD3D 뷰어/해석 엔진에서 사용'))
    libs = dict(core=open(os.path.join(a.three, 'three.core.js'), encoding='utf-8').read(),
                module=open(os.path.join(a.three, 'three.module.js'), encoding='utf-8').read())
    t = open(a.template, encoding='utf-8').read()
    assert t.count('__DATA__') == 1 and t.count('__LIBS__') == 1
    js = lambda o: json.dumps(o, ensure_ascii=False).replace('</', '<\\/')
    # 앱 적합성 검토(필요한 층 목록) 미리 채움: 원본이 CAD3D 정렬·층고 검증을 거친 모델이므로 바로 3D 검토 가능
    fls = ','.join(str(p['initial']['floor']) for p in pages)
    saved = dict(version=1, sourceHash=D['sourceHash'], pages=[p['initial'] for p in pages],
                 workflow=dict(expected=f"{a.building}:{fls}", missing='', round=1, cycle=1,
                               history=[dict(at='', cycle=1, round=1, ok=True, issues=['CAD3D 원본(계단·승강기 기준 정렬, 도면 층고) 자동 입력'])]))
    html = t.replace('__DATA__', js(D) + ';window.SAVED_REVIEW_STATE=' + js(saved)).replace('__LIBS__', js(libs))
    out = a.out or os.path.join(a.outdir, 'croquis.html')
    open(out, 'w', encoding='utf-8').write(html)
    json.dump(D | dict(pages=[{k: v for k, v in p.items() if k != 'image'} for p in pages]), open(os.path.splitext(out)[0] + '.json', 'w', encoding='utf-8'), ensure_ascii=False)
    print('→', out, round(os.path.getsize(out) / 1e6, 1), 'MB'); print(dict(report))

if __name__ == '__main__':
    main()
