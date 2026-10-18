"""레이어 무관 2차: 선망 → 면 → 공리로 실·문·창 확정.
공리: 실 = 벽·문·창 선의 폐곡선 / 문은 두 공간을 가른다 / 창은 실과 외부(또는 실) 경계에 있다.
1) 장벽 = 선망(1px) + 문 닫기 선(경첩~닫힌 위치) + 기둥 후보 채움
2) 바깥 = 가장자리에서 채움, 면 = 빈 공간(0.4m 열림) 연결 성분
3) 합치기: 문·창이 하나도 닿지 않는 면은 홑선(1~2px) 경계 너머 이웃 면과 합침(가구·계단 안쪽).
   두 줄 벽(벽 몸체)으로 갈린 면은 합치지 않음 → '문 미검출 = 실 없음'으로 보지 않음
4) 문 검사: 양쪽이 같은 면이면, 선망에서 빠진 선(가지·섬) 중 되살렸을 때 갈리는 선을 복원
5) 창 확정: 창 후보 띠의 양쪽이 서로 다른 영역(실|외부, 실|실)일 때만
python geo_rooms.py 층.dxf 출력접두어 [--layer-json 레이어방식 nF.json]"""
import sys, json, math, argparse, collections
import numpy as np, cv2
from shapely.geometry import LineString, Polygon, Point
from geo_net import analyze

RES = 20.0  # mm/px


def run(fn, out, layer_json=None):
    g = analyze(fn)
    net, off = g['_net'], g['_off']
    xs = [c[0] for l in net for c in l.coords]; ys = [c[1] for l in net for c in l.coords]
    x0, y0, x1, y1 = min(xs) - 2000, min(ys) - 2000, max(xs) + 2000, max(ys) + 2000
    W, H = int((x1 - x0) / RES) + 1, int((y1 - y0) / RES) + 1
    T = lambda x, y: (int(round((x - x0) / RES)), int(round((y1 - y) / RES)))
    Ti = lambda u, v: (u * RES + x0, y1 - v * RES)
    def draw(img, geom, val=255):
        cs = list(geom.coords)
        cv2.polylines(img, [np.int32([T(*c) for c in cs])], False, val, 1)
    bar = np.zeros((H, W), np.uint8)
    for l in net: draw(bar, l)
    doors = []
    for o in g['openings']:
        if o['kind'] != 'door': continue
        if 'seg' not in o:   # 문틀 쌍으로 잡힌 문: 사각형 긴 축 중심선
            q = np.array(o['quad']); P_ = Polygon(q).minimum_rotated_rectangle; xy = np.array(P_.exterior.coords[:4])
            e1, e2 = xy[1] - xy[0], xy[2] - xy[1]
            if np.hypot(*e1) >= np.hypot(*e2): a_, b_ = (xy[0] + xy[3]) / 2, (xy[1] + xy[2]) / 2
            else: a_, b_ = (xy[0] + xy[1]) / 2, (xy[3] + xy[2]) / 2
            o = dict(o, seg=[*map(float, a_), *map(float, b_)])
        doors.append(o)
    for o in doors: draw(bar, LineString([o['seg'][:2], o['seg'][2:]]))
    for cx, cy, w, h in g['_cols_pieces']:
        cv2.rectangle(bar, T(cx - w / 2, cy - h / 2), T(cx + w / 2, cy + h / 2), 255, -1)
    kpx = max(3, int(round(400 / RES)))

    def faces(b):
        ff = b.copy(); m = np.zeros((H + 2, W + 2), np.uint8); cv2.floodFill(ff, m, (0, 0), 128, flags=4)
        outside = ff == 128
        free = ((b == 0) & ~outside).astype(np.uint8)
        free = cv2.morphologyEx(free, cv2.MORPH_OPEN, np.ones((kpx, kpx), np.uint8))
        n, lab = cv2.connectedComponents(free, connectivity=4)
        lab[outside] = -1
        return n, lab, outside

    def side_labels(lab, seg, dmin=150, dmax=1300):
        ax, ay, bx, by = seg; L = math.hypot(bx - ax, by - ay) or 1
        nx, ny = -(by - ay) / L, (bx - ax) / L; mx, my = (ax + bx) / 2, (ay + by) / 2
        res = []
        for sg in (1, -1):
            got = None
            for d in range(dmin, dmax, 40):
                u, v = T(mx + sg * nx * d, my + sg * ny * d)
                if not (0 <= v < H and 0 <= u < W): got = -1; break
                if lab[v, u] != 0: got = int(lab[v, u]); break
            res.append(got)
        return res

    # ---- 4) 문 검사 + 누락선 복원 ----
    n, lab, outside = faces(bar)
    restored = []
    offs = [l for l in off if l.length >= 300]
    from shapely.strtree import STRtree
    otree = STRtree(offs) if offs else None
    for o in doors:
        sd = side_labels(lab, o['seg'])
        if sd[0] is None or sd[1] is None or sd[0] != sd[1] or sd[0] == -1: continue
        mid = Point((o['seg'][0] + o['seg'][2]) / 2, (o['seg'][1] + o['seg'][3]) / 2)
        if otree is None: continue
        cands = sorted(otree.query(mid.buffer(4000)), key=lambda t: offs[t].distance(mid))[:40]
        for t in cands:
            b2 = bar.copy(); draw(b2, offs[t])
            n2, lab2, _ = faces(b2)
            s2 = side_labels(lab2, o['seg'])
            if s2[0] and s2[1] and s2[0] != s2[1]:
                bar = b2; n, lab = n2, lab2; restored.append([[round(c[0]), round(c[1])] for c in offs[t].coords]); break
    n, lab, outside = faces(bar)

    # ---- 3-000) 선망 외곽 경계(도곽·대지선)에 붙은 면 = 외부: 실은 벽 두께만큼 안쪽에 있어 닿지 않음 ----
    bx0, by0 = T(min(xs), max(ys)); bx1, by1 = T(max(xs), min(ys))
    edge = np.zeros_like(bar); cv2.rectangle(edge, (bx0, by0), (bx1, by1), 1, 5)
    for i in np.unique(lab[(edge > 0) & (lab > 0)]):
        lab[lab == i] = -1
    # ---- 3-00) 감싸는 면 = 외부: 바깥 윤곽 안에 다른 면 면적의 절반 이상을 품는 면(도곽·대지 안쪽)은 실이 아님 ----
    for _ in range(5):
        ids, cnt = np.unique(lab[lab > 0], return_counts=True)
        if not len(ids): break
        tot = cnt.sum(); hit = None
        for i, c in sorted(zip(ids, cnt), key=lambda x: -x[1])[:3]:
            m = (lab == i).astype(np.uint8)
            cs_, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            mf = np.zeros_like(m); cv2.drawContours(mf, cs_, -1, 1, -1)
            inner = ((mf > 0) & (lab > 0) & (lab != i)).sum()
            if inner > 0.5 * (tot - c): hit = i; break
        if hit is None: break
        lab[lab == hit] = -1
    # ---- 3-0) 외부 띠: 바깥과 홑선으로 둘레 30% 이상 맞닿은 면(입면 장식선·슬래브 끝선 사이) → 외부, 반복 ----
    ext_faces = 0
    ker3 = np.ones((7, 7), np.uint8)
    for _ in range(10):
        outm = (lab == -1).astype(np.uint8)
        near_out = cv2.dilate(outm, ker3) > 0
        ids, cnt = np.unique(lab[(lab > 0)], return_counts=True)
        conv = []
        for i, c in zip(ids, cnt):
            m = (lab == i).astype(np.uint8)
            # 바깥 테두리만(구멍=안쪽 건물 경계는 제외): 외곽 윤곽을 채운 뒤 그 둘레
            cs_, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            mf = np.zeros_like(m); cv2.drawContours(mf, cs_, -1, 1, -1)
            ring = (cv2.dilate(mf, np.ones((3, 3), np.uint8)) > 0) & (mf == 0)
            # 둘레에서 3px(60mm) 안에 바깥이 있는 비율
            per = ring.sum()
            if per == 0: continue
            frac = (ring & near_out).sum() / per
            if frac <= 0.3: continue
            # 둘레 대부분(60%↑)이 홑선 너머 바깥 = 도곽·대지경계 안쪽 같은 '바깥의 연장' → 크기 무관 외부
            # 그 외(30~60%)는 띠 모양(내접 폭 ≤2m)만: 홑선 커튼월로 둘러진 실은 외부로 돌리지 않음
            if frac <= 0.6:
                ys_, xs_ = np.nonzero(m); sub = m[ys_.min():ys_.max() + 1, xs_.min():xs_.max() + 1]
                wmax = cv2.distanceTransform(np.pad(sub, 1), cv2.DIST_L2, 3).max() * 2 * RES
                if wmax > 2000: continue
            # 외곽 테두리 80%↑가 바깥에 홑선으로 붙음(도곽 안쪽) → 문·창이 닿아도 외부(외부 계단·출입문 바깥쪽)
            if frac > 0.8 or not any(side_labels(lab, o['seg'])[k_] == i for o in doors for k_ in (0, 1)):
                conv.append(i)
        if not conv: break
        for i in conv: lab[lab == i] = -1
        ext_faces += len(conv)
    # ---- 3) 면 합치기 ----
    area = np.bincount(lab[lab > 0].ravel(), minlength=n)
    # 면별 문·창 닿음
    touch = collections.defaultdict(set)
    for o in doors:
        for s in side_labels(lab, o['seg']):
            if s and s > 0: touch[s].add('door')
    wins_c = [o for o in g['openings'] if o['kind'] == 'window']
    def quad_sides(lab_, q):
        P_ = Polygon(q); mrr = np.array(P_.minimum_rotated_rectangle.exterior.coords[:4])
        e1, e2 = mrr[1] - mrr[0], mrr[2] - mrr[1]
        long_ = e1 if np.hypot(*e1) >= np.hypot(*e2) else e2
        c = np.array(P_.centroid.coords[0]); u = long_ / (np.hypot(*long_) + 1e-9)
        seg = [*(c - u * 100), *(c + u * 100)]
        half = min(np.hypot(*e1), np.hypot(*e2)) / 2
        return side_labels(lab_, seg, dmin=int(half + 120), dmax=int(half + 1300))
    for w in wins_c:
        for s in quad_sides(lab, w['quad']):
            if s and s > 0: touch[s].add('window')
    # 홑선 이웃: 면 마스크를 3px 팽창했을 때 닿는 다른 면 (벽 몸체는 그보다 두꺼움)
    parent = list(range(n))
    def f(a):
        while parent[a] != a: parent[a] = parent[parent[a]]; a = parent[a]
        return a
    changed = True; merges = 0
    ker = np.ones((9, 9), np.uint8)   # 4px=80mm 이하 경계 = 홑선(칸막이·가구선), 벽 몸체(≥100mm)는 넘지 않음
    while changed:
        changed = False
        roots = {}
        for i in range(1, n):
            if area[i] == 0: continue
            r = f(i); roots.setdefault(r, []).append(i)
        for r, members in roots.items():
            if any(touch.get(m) for m in members): continue
            m = np.isin(lab, members).astype(np.uint8)
            ys_, xs_ = np.nonzero(m)
            if not len(ys_): continue
            yA, yB, xA, xB = max(0, ys_.min() - 3), ys_.max() + 4, max(0, xs_.min() - 3), xs_.max() + 4
            sub = m[yA:yB, xA:xB]; ring = cv2.dilate(sub, ker) & (1 - sub)
            nb = lab[yA:yB, xA:xB][ring > 0]
            nb = nb[(nb > 0)]
            nb = [x for x in nb if f(int(x)) != r]
            if not nb: continue
            best = collections.Counter(f(int(x)) for x in nb).most_common(1)[0][0]
            parent[r] = best; merges += 1; changed = True
            for mm_ in members: touch[best] |= touch.get(mm_, set())
            break   # 다시 계산
    rid = np.zeros(n, int)
    roots = sorted({f(i) for i in range(1, n) if area[i] > 0})
    rmap = {r: k + 1 for k, r in enumerate(roots)}
    for i in range(1, n):
        if area[i] > 0: rid[i] = rmap[f(i)]
    L2 = np.where(lab > 0, rid[np.clip(lab, 0, None)], np.where(lab < 0, -1, 0))
    rooms = []
    for r, k in rmap.items():
        m = (L2 == k).astype(np.uint8)
        a = m.sum() * (RES / 1000) ** 2
        if a < 0.25: continue
        cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        c = max(cs, key=cv2.contourArea); c = cv2.approxPolyDP(c, 1.0, True)
        rooms.append(dict(id=f'R{len(rooms)}', k=k, area=round(a, 2), has=sorted(touch.get(r, [])),
                          poly=[[round(Ti(u, v)[0]), round(Ti(u, v)[1])] for u, v in c[:, 0]]))
    # ---- 5) 문·창 최종 ----
    door_ok, door_bad = [], []
    for o in doors:
        sd = side_labels(L2, o['seg'])
        (door_ok if (sd[0] and sd[1] and sd[0] != sd[1]) else door_bad).append(dict(o, sides=sd))
    win_ok = []
    for w in wins_c:
        sd = quad_sides(L2, w['quad'])
        if sd[0] and sd[1] and sd[0] != sd[1] and max(sd) > 0:
            win_ok.append(dict(w, sides=sd, ext=(-1 in sd)))
    # 공리: 실은 문·창을 가짐 (두 줄 벽으로 닫힌 면은 문 미검출이어도 실로 둠 → 표시만)
    no_open = [r['id'] for r in rooms if not r['has']]
    res = dict(src=g['src'], rooms=[{k: v for k, v in r.items() if k != 'k'} for r in rooms],
               doors=door_ok, doors_unseparated=door_bad, windows=win_ok, restored_lines=restored,
               stats=dict(faces_raw=int(n - 1), exterior_strips=ext_faces, merges=merges, rooms=len(rooms), doors=len(doors), doors_ok=len(door_ok),
                          window_candidates=len(wins_c), windows_ok=len(win_ok), windows_ext=sum(w['ext'] for w in win_ok),
                          restored=len(restored), rooms_without_opening=len(no_open)),
               raster=dict(x0=x0, y1=y1, R=RES, W=W, H=H))
    if layer_json:
        res['vs_layer'] = compare_layer(rooms, layer_json)
    json.dump(res, open(out + '_georooms.json', 'w', encoding='utf-8'), ensure_ascii=False)
    np.save(out + '_georooms_lab.npy', L2.astype(np.int16))
    return res


def compare_layer(rooms, lj):
    """레이어 방식 실과 겹침 비교(IoU 0.5 이상 짝)"""
    l = json.load(open(lj, encoding='utf-8'))
    LP = [Polygon([(x * 1000, y * 1000) for x, y in r['poly']]).buffer(0) for r in l['rooms'] if len(r['poly']) >= 3]
    GP = [Polygon(r['poly']).buffer(0) for r in rooms if len(r['poly']) >= 3]
    matched = 0; used = set(); ious = []
    for gp in GP:
        best = (0, None)
        for j, lp in enumerate(LP):
            if j in used or not gp.intersects(lp): continue
            iou = gp.intersection(lp).area / (gp.union(lp).area or 1)
            if iou > best[0]: best = (iou, j)
        if best[0] >= 0.5: matched += 1; used.add(best[1]); ious.append(best[0])
    big_l = [p for p in LP if p.area > 4e6]; big_g = [p for p in GP if p.area > 4e6]
    return dict(geo_rooms=len(GP), layer_rooms=len(LP), matched_iou50=matched, mean_iou=round(float(np.mean(ious)), 3) if ious else None,
                geo_big=len(big_g), layer_big=len(big_l),
                layer_big_matched=sum(1 for j in used if LP[j].area > 4e6))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('dxf'); ap.add_argument('out'); ap.add_argument('--layer-json')
    a = ap.parse_args()
    r = run(a.dxf, a.out, a.layer_json)
    print(json.dumps(r['stats'], ensure_ascii=False)); print(json.dumps(r.get('vs_layer'), ensure_ascii=False))
