"""레이어에 기대지 않는 형상 판독 1차: 개구부(문·창) 인식 + 벽 선망 추적.
레이어는 쓰지 않음. 제외 기준은 엔티티 종류(문자·치수·해치는 cadio가 애초에 안 읽음)와 선종류(숨은선)뿐.

1) 문짝: 호(ARC·폴리선 볼록) r 0.35~1.9m, 각 60~190° + 경첩에서 반지름만큼 뻗은 길고 얇은 문짝선
2) 문틀(jamb): 짧은 선(60~600mm) 양 끝에 서로 평행한 두 선(벽 양면)이 같은 쪽으로 붙은 것 = 벽 끝면
3) 개구부: 마주보는 문틀 쌍(0.3~8m, 같은 벽 띠). 사이 내용으로 판정
     - 문틀~문틀을 잇는 평행선 있음 → 창(또는 미닫이)
     - 문짝 있음 → 문 / 없음 → 열린 개구부
4) 선망: 보정기(중복·스냅·T·연장·폐합) → 노드 분할 → 연결 성분 중 개구부·문틀이 붙은 성분만 → 열린 가지 반복 제거
     - 떨어진 닫힌 도형(섬) = 가구·기호, 그중 반복되는 작은 정사각형 = 기둥 후보
python geo_net.py 층.dxf 출력접두어"""
import sys, json, math, re, collections
import numpy as np
from scipy.spatial import cKDTree
from shapely.geometry import LineString, Point, Polygon, MultiPoint, box
from shapely.strtree import STRtree
from shapely.ops import unary_union
from cadio import load, units_to_m
from cad_heal import Healer

DASHED = re.compile(r'^DASHED:|HID|DASH|CENT|PHAN|DOT|DIVIDE|BORDER|점선|숨은', re.I)


def segs_of(pts, closed):
    out = [(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]) for i in range(len(pts) - 1)]
    if closed and len(pts) > 2 and pts[0] != pts[-1]:
        out.append((pts[-1][0], pts[-1][1], pts[0][0], pts[0][1]))
    return out


def ang(s):
    return math.atan2(s[3] - s[1], s[2] - s[0])


def angdiff(a, b):  # 0~90°
    d = abs((a - b) % math.pi); d = min(d, math.pi - d)
    return math.degrees(d)


def analyze(fn):
    doc, prims, _ = load(fn)
    k = units_to_m(doc, prims) * 1000.0
    P_all = prims                                         # 문짝·호는 점선으로 그리는 경우가 많아 선종류로 거르지 않음
    P = [p for p in prims if not DASHED.search(p.lt)]     # 선망(벽 후보)만 숨은선·중심선 제외
    mm = lambda pts: [(x * k, y * k) for x, y in pts]

    # ---- 1) 문짝 ----
    arcs = []
    for p in P_all:
        if p.arc:
            r = p.arc[2] * k; sw = (p.arc[4] - p.arc[3]) % 360
            if 350 <= r <= 1900 and 60 <= sw <= 190: arcs.append(p)
    hinge = cKDTree(np.array([[a.arc[0] * k, a.arc[1] * k] for a in arcs])) if arcs else None
    leaf_of = collections.defaultdict(list)
    leaf_ids = set()
    # 호 자신(폴리선)에 문짝 직선이 같이 들어 있는 경우
    for i, a in enumerate(arcs):
        if a.kind != 'LWPOLYLINE': continue
        cx, cy, r = a.arc[0] * k, a.arc[1] * k, a.arc[2] * k
        q = mm(a.pts)
        for u, v in zip(q, q[1:]):
            if min(math.hypot(u[0] - cx, u[1] - cy), math.hypot(v[0] - cx, v[1] - cy)) < 120 and math.dist(u, v) >= 0.6 * r:
                leaf_of[i].append(a); break
    if hinge is not None:
        for p in P_all:
            if p.arc or len(p.pts) < 2: continue
            q = mm(p.pts)
            for e in q:
                d, i = hinge.query(e)
                if d >= 120: continue
                c = arcs[i].arc; cx, cy, r = c[0] * k, c[1] * k, c[2] * k
                if not all(math.hypot(x - cx, y - cy) <= r + 60 for x, y in q): continue
                g = MultiPoint(q).minimum_rotated_rectangle
                if g.geom_type == 'Polygon':
                    xy = np.array(g.exterior.coords[:4]); a_, b_ = math.dist(xy[0], xy[1]), math.dist(xy[1], xy[2])
                    L, Wd = max(a_, b_), min(a_, b_)
                else:
                    L, Wd = math.dist(q[0], q[-1]), 0
                if L >= 0.6 * r and Wd <= 80:
                    leaf_of[i].append(p); leaf_ids.add(id(p)); break
    doors = []
    door_ids = set()
    for i, a in enumerate(arcs):
        c = a.arc
        doors.append(dict(hinge=(c[0] * k, c[1] * k), r=c[2] * k, sweep=(c[4] - c[3]) % 360, leaf=bool(leaf_of.get(i)),
                          arc_pts=mm(a.pts)))
        door_ids.add(id(a))
    # 영역: 문짝 외접 + 12m (도곽·표제란 배제)
    if doors:
        H_ = np.array([d['hinge'] for d in doors])
        lo, hi = H_.min(0) - 12000, H_.max(0) + 12000
    else:
        allp = np.array([v for p in P for v in mm(p.pts)]); lo, hi = np.percentile(allp, 1, 0), np.percentile(allp, 99, 0)
    reg = box(*lo, *hi)

    # ---- 선분 모음(문짝·호 제외) ----
    S, M = [], []
    for p in P:
        if id(p) in door_ids or id(p) in leaf_ids: continue
        q = mm(p.pts)
        xs = [v[0] for v in q]; ys = [v[1] for v in q]
        if not reg.intersects(box(min(xs), min(ys), max(xs), max(ys))): continue
        for s in segs_of(q, p.closed):
            if math.hypot(s[2] - s[0], s[3] - s[1]) > 0.5:
                S.append(s); M.append(dict(cat='wall', layer=p.layer, closed=p.closed, src=id(p)))
    n_raw = len(S)
    Hl = Healer(S, M)
    Hl.merge(); Hl.snap(); Hl.connect()
    S = [tuple(s) for s in Hl.S]; M = Hl.M
    n = len(S)
    L = np.array([math.hypot(s[2] - s[0], s[3] - s[1]) for s in S])
    A = np.array([ang(s) for s in S])

    # ---- 2) 문틀 ----
    E = np.array([[s[0], s[1]] for s in S] + [[s[2], s[3]] for s in S])
    kd = cKDTree(E)
    jambs = []
    for i, s in enumerate(S):
        if not (60 <= L[i] <= 600): continue
        att = []
        for end in (0, 1):
            pt = E[i + end * n]
            cand = []
            for kk in kd.query_ball_point(pt, 30):
                j = kk % n
                if j == i or L[j] < 150: continue
                if abs(angdiff(A[i], A[j]) - 90) > 4: continue
                # 붙은 끝에서 몸통 방향
                o = E[(kk + n) % (2 * n)] if kk < n else E[kk - n]
                v = o - E[kk]; v = v / (np.hypot(*v) + 1e-9)
                cand.append((j, v))
            att.append(cand)
        best = None
        for ja, va in att[0]:
            for jb, vb in att[1]:
                if ja != jb and va @ vb > 0.99:     # 두 면이 같은 쪽으로 뻗음
                    best = (ja, jb, va); break
            if best: break
        if best:
            ja, jb, va = best
            # 작은 닫힌 상자(기둥·가구)의 한 변이면 문틀 아님: 두 면 끝을 잇는 평행 변이 있으면 상자
            fa = [E[ja], E[ja + n]]; fb = [E[jb], E[jb + n]]
            ea = max(fa, key=lambda e: np.hypot(*(e - E[i])) if True else 0); eb = max(fb, key=lambda e: np.hypot(*(e - E[i + n])))
            if max(L[ja], L[jb]) <= 1300:
                closed_box = any(kk % n not in (i, ja, jb) and np.hypot(*(E[(kk + n) % (2 * n)] - eb)) < 40
                                 for kk in kd.query_ball_point(ea, 40))
                if closed_box: continue
            c = (E[i] + E[i + n]) / 2
            jambs.append(dict(seg=i, faces=(ja, jb), c=c, out=-va, w=L[i]))   # out: 개구부 쪽(벽 몸통 반대)

    # ---- 3a) 문 개구부: 문짝 있는 호 → 경첩~닫힌 위치(호 끝점) 선분 ----
    seg_tree0 = STRtree([LineString([(s[0], s[1]), (s[2], s[3])]) for s in S])
    def wall_along(pt, direction):
        # pt 근처(30mm)에 direction과 나란한 선이 지나가면 그쪽은 벽
        for t in seg_tree0.query(Point(pt).buffer(30)):
            if angdiff(A[t], math.atan2(direction[1], direction[0])) < 5 and seg_tree0.geometries[t].distance(Point(pt)) < 30: return True
        return False
    def near_d(pt):
        g = Point(pt); best_ = 1e9
        for t in seg_tree0.query(g.buffer(200)):
            best_ = min(best_, seg_tree0.geometries[t].distance(g))
        return best_
    door_open = []
    for i, d in enumerate(doors):
        hx, hy = d['hinge']; r = d['r']; ap = d['arc_pts']
        e1, e2 = np.array(ap[0]), np.array(ap[-1]); hv = np.array([hx, hy])
        if not d['leaf']:
            # 문짝 없이 호만 그린 문: 경첩이 벽·문틀에 붙어 있고(150mm), 호 끝 하나가 맞은편 벽에 닿음(150mm)
            if near_d(hv) > 150: continue
            d1, d2 = near_d(e1), near_d(e2)
            if min(d1, d2) > 150: continue
            if (d['sweep'] > 150):
                cands = [(e, (e - hv) / (np.hypot(*(e - hv)) + 1e-9)) for e in (e1, e2)]
                free_ = [c for c in cands if not wall_along(hv + c[1] * 0.5 * r, c[1])]
                e, v = (free_ or cands)[0]
            else:
                e = e1 if d1 <= d2 else e2
            d['leaf'] = 'arc_only'
            door_open.append(dict(kind='door', door=i, width=round(r), seg=[float(hx), float(hy), float(e[0]), float(e[1])], leaf=False))
            continue
        lf = leaf_of[i][0]; q = np.array(mm(lf.pts))
        if lf is arcs[i]:   # 자기 문짝: 경첩에서 r 떨어진 꼭짓점 중 호 끝이 아닌 것
            q = np.array([v for v in q if abs(math.hypot(v[0] - hx, v[1] - hy) - r) < 0.2 * r])
            if not len(q): continue
        far = q[np.argmax(np.hypot(*(q - hv).T))]
        ldir = (far - hv) / (np.hypot(*(far - hv)) + 1e-9)
        cands = []
        for e in (e1, e2):
            v = (e - hv) / (np.hypot(*(e - hv)) + 1e-9)
            if abs(v @ ldir) < 0.5: cands.append((e, v))      # 문짝과 직각인 끝 = 닫힌 위치 후보
        if not cands:   # 문짝이 벽과 나란히(닫힌 상태로) 그려진 경우: 문짝 자체가 개구부
            door_open.append(dict(kind='door', door=i, width=round(r), seg=[float(hx), float(hy), float(far[0]), float(far[1])], leaf=True))
            continue
        if len(cands) == 2:   # 반원(양방향문): 벽이 이어지지 않는 쪽이 개구부
            free_ = [c for c in cands if not wall_along(hv + c[1] * 0.5 * r, c[1])]
            cands = free_ or cands[:1]
        e, v = cands[0]
        door_open.append(dict(kind='door', door=i, width=round(r), seg=[float(hx), float(hy), float(e[0]), float(e[1])]))
    # ---- 3) 개구부: 마주보는 문틀 쌍 ----
    tree = STRtree([LineString([(s[0], s[1]), (s[2], s[3])]) for s in S])
    lines = tree.geometries
    used = set(); openings = []
    jc = np.array([j['c'] for j in jambs]) if jambs else np.zeros((0, 2))
    jk = cKDTree(jc) if len(jc) else None
    for a_i, ja in enumerate(jambs):
        if a_i in used: continue
        best = None
        for b_i in jk.query_ball_point(ja['c'], 8000):
            if b_i == a_i or b_i in used: continue
            jb = jambs[b_i]
            if ja['out'] @ jb['out'] > -0.99: continue                 # 서로 마주봄
            v = jb['c'] - ja['c']; d = float(np.hypot(*v))
            if d < 300: continue
            if abs(v @ ja['out']) / d < 0.995: continue                 # 같은 축 위
            if v @ ja['out'] <= 0: continue
            if abs(ja['w'] - jb['w']) > max(80, 0.3 * ja['w']): continue
            if best is None or d < best[0]: best = (d, b_i)
        if not best: continue
        d, b_i = best; jb = jambs[b_i]
        # 사이에 벽 몸통을 가로막는 선(같은 축에 수직인 다른 문틀/벽)이 있으면 쌍 아님
        quad = MultiPoint([E[ja['seg']], E[ja['seg'] + n], E[jb['seg']], E[jb['seg'] + n]]).convex_hull
        if quad.geom_type != 'Polygon' or quad.area < 1e4: continue
        inner = quad.buffer(-15)
        para, perp = [], 0
        for t in tree.query(inner):
            if t in (ja['seg'], jb['seg']) or t in ja['faces'] or t in jb['faces']: continue
            g = lines[t]
            if not g.intersects(inner): continue
            seg_in = g.intersection(quad)
            if seg_in.length < 50: continue
            ad = angdiff(A[t], math.atan2(ja['out'][1], ja['out'][0]))
            if ad < 5: para.append(seg_in.length)
            elif ad > 85 and seg_in.length > 0.6 * ja['w']: perp += 1
        span = sum(1 for x in para if x >= 0.7 * d)
        # 문짝: 경첩이 개구부 근처
        dz = None
        if hinge is not None:
            for hi_ in hinge.query_ball_point(np.array(quad.centroid.coords[0]), d / 2 + 400):
                if quad.buffer(250).contains(Point(doors[hi_]['hinge'])): dz = hi_; break
        if any(quad.buffer(150).intersects(LineString([o_['seg'][:2], o_['seg'][2:]])) for o_ in door_open): continue
        if dz is not None: kind = 'door'
        elif span >= 1 and perp <= max(2, int(d / 600)): kind = 'window'
        elif perp > max(2, int(d / 600)): continue        # 사이에 칸막이 많음 → 개구부 아님
        else: kind = 'open'
        used |= {a_i, b_i}
        openings.append(dict(kind=kind, a=a_i, b=b_i, width=round(d), wall=round((ja['w'] + jb['w']) / 2), lines=span,
                             door=dz, quad=[list(map(float, c)) for c in quad.exterior.coords[:-1]]))
    # 문틀 쌍 없이 호만 있는 문(한쪽이 기둥·모서리)
    # ---- 3b) 창(벽 띠 안 내부선): 벽 양면(나란한 긴 두 선, 간격 80~450mm) 사이에 그보다 짧은 평행선이 있으면 그 구간 = 창
    #      (면이 창에서 끊기지 않고 이어 그린 도면용. 면이 끊긴 도면은 3) 문틀 쌍에서 잡힘)
    wins = []
    door_lines = [LineString([o_['seg'][:2], o_['seg'][2:]]).buffer(300) for o_ in door_open]
    inner_hits = collections.defaultdict(list)   # (face a, face b) → [(t0,t1)]
    for j in range(n):
        if not (300 <= L[j] <= 6000): continue
        sj = S[j]; u = np.array([sj[2] - sj[0], sj[3] - sj[1]]) / L[j]; nrm = np.array([-u[1], u[0]]); o0 = np.array(sj[:2])
        pos, neg = [], []
        for t in tree.query(lines[j].buffer(460)):
            if t == j or L[t] < 600 or angdiff(A[t], A[j]) > 1: continue
            st_ = S[t]; pa, pb = np.array(st_[:2]) - o0, np.array(st_[2:]) - o0
            off = (pa @ nrm + pb @ nrm) / 2
            if abs(off) < 15 or abs(off) > 435: continue
            ta, tb = sorted([pa @ u, pb @ u])
            ov = min(tb, L[j]) - max(ta, 0)
            if ov < 0.9 * L[j] or L[j] > 0.85 * L[t]: continue
            (pos if off > 0 else neg).append((abs(off), t, ta, tb))
        if not pos or not neg: continue
        fa = min(pos)[1]; fb = min(neg)[1]
        if min(pos)[0] + min(neg)[0] > 450 or min(pos)[0] + min(neg)[0] < 80: continue
        key_ = tuple(sorted((fa, fb)))
        # 구간: 면 fa 기준 좌표
        sa = S[key_[0]]; ua = np.array([sa[2] - sa[0], sa[3] - sa[1]]) / L[key_[0]]; oa = np.array(sa[:2])
        t0, t1 = sorted([(np.array(sj[:2]) - oa) @ ua, (np.array(sj[2:]) - oa) @ ua])
        inner_hits[key_].append((t0, t1))
    for (fa, fb), iv in inner_hits.items():
        iv.sort(); merged = [list(iv[0])]
        for t0, t1 in iv[1:]:
            if t0 <= merged[-1][1] + 150: merged[-1][1] = max(merged[-1][1], t1)
            else: merged.append([t0, t1])
        sa, sb = S[fa], S[fb]; ua = np.array([sa[2] - sa[0], sa[3] - sa[1]]) / L[fa]; oa = np.array(sa[:2])
        nb = np.array([-ua[1], ua[0]]); offb = ((np.array(sb[:2]) - oa) @ nb + (np.array(sb[2:]) - oa) @ nb) / 2
        for t0, t1 in merged:
            if t1 - t0 < 300: continue
            p0, p1 = oa + ua * t0, oa + ua * t1
            quad = [p0, p1, p1 + nb * offb, p0 + nb * offb]
            qg = Polygon(quad)
            if any(qg.intersects(dl) for dl in door_lines): continue
            wins.append(dict(kind='window', width=round(t1 - t0), wall=round(abs(offb)), quad=[list(map(float, c)) for c in quad]))
    # 문틀 쌍 창과 띠 창 중복 제거
    wq = [Polygon(w['quad']) for w in wins]
    openings = [o for o in openings if not (o['kind'] == 'window' and any(Polygon(o['quad']).buffer(100).intersects(q) for q in wq))]
    openings = door_open + openings + wins
    door_paired = {o['door'] for o in openings if o.get('door') is not None}

    # ---- 4) 선망 ----
    noded = unary_union(lines)
    pieces = list(noded.geoms) if hasattr(noded, 'geoms') else [noded]
    key = lambda c: (round(c[0]), round(c[1]))
    adj = collections.defaultdict(list)
    for ei, g in enumerate(pieces):
        a_, b_ = key(g.coords[0]), key(g.coords[-1])
        adj[a_].append(ei); adj[b_].append(ei)
    par = {}
    def f(x):
        par.setdefault(x, x)
        while par[x] != x: par[x] = par[par[x]]; x = par[x]
        return x
    for ei, g in enumerate(pieces):
        ra_, rb_ = f(key(g.coords[0])), f(key(g.coords[-1]))
        if ra_ != rb_: par[rb_] = ra_
    comp_of_edge = [f(key(g.coords[0])) for g in pieces]
    # 개구부·문틀 닿은 성분
    ptree = STRtree(pieces)
    anchor_comps = set()
    for j in jambs:
        for t in ptree.query(Point(j['c']).buffer(40)): anchor_comps.add(comp_of_edge[t])
    for d_ in doors:
        for t in ptree.query(Point(d_['hinge']).buffer(80)): anchor_comps.add(comp_of_edge[t])
    comp_len = collections.Counter()
    for ei, g in enumerate(pieces): comp_len[comp_of_edge[ei]] += g.length
    keep = np.array([comp_of_edge[ei] in anchor_comps for ei in range(len(pieces))])
    # 열린 가지 반복 제거(차수 1 끝을 가진 조각 삭제, 반복)
    deg = collections.Counter()
    for ei, g in enumerate(pieces):
        if keep[ei]: deg[key(g.coords[0])] += 1; deg[key(g.coords[-1])] += 1
    alive = keep.copy(); pruned = 0
    changed = True
    while changed:
        changed = False
        for ei, g in enumerate(pieces):
            if not alive[ei]: continue
            a_, b_ = key(g.coords[0]), key(g.coords[-1])
            if deg[a_] == 1 or deg[b_] == 1:
                alive[ei] = False; deg[a_] -= 1; deg[b_] -= 1; pruned += 1; changed = True
    # 섬: 앵커 없는 성분 → 닫힌 작은 정사각형 반복 = 기둥 후보, 나머지 = 가구·기호
    islands = collections.defaultdict(list)
    for ei in range(len(pieces)):
        if not keep[ei]: islands[comp_of_edge[ei]].append(ei)
    cols, furn = [], 0
    sizes = []
    for cid, es in islands.items():
        g = unary_union([pieces[e] for e in es]); b = g.bounds
        w, h = b[2] - b[0], b[3] - b[1]
        sizes.append((cid, round(w / 50) * 50, round(h / 50) * 50, b))
    rep = collections.Counter((w, h) for _, w, h, _ in sizes)
    for cid, w, h, b in sizes:
        if 200 <= min(w, h) and max(w, h) <= 1300 and max(w, h) / max(min(w, h), 1) < 1.6 and rep[(w, h)] >= 4:
            cols.append([round((b[0] + b[2]) / 2), round((b[1] + b[3]) / 2), w, h])
        else: furn += 1
    net = [pieces[e] for e in range(len(pieces)) if alive[e]]
    off = [pieces[e] for e in range(len(pieces)) if not alive[e]]
    # 레이어 대조(참고용 통계): 선망에 들어간 선의 원래 레이어 구성
    lay_net = collections.Counter()
    st_src = STRtree([LineString([(s[0], s[1]), (s[2], s[3])]) for s in S])
    for g in net[:: max(1, len(net) // 3000)]:
        m = g.interpolate(0.5, normalized=True)
        for t in st_src.query(m.buffer(1)):
            if st_src.geometries[t].distance(m) < 1: lay_net[M[t]['layer']] += 1; break
    res = dict(src=fn.split('/')[-1], unit_mm=k,
               doors=[dict(hinge=[round(v) for v in d['hinge']], r=round(d['r']), sweep=round(d['sweep']), leaf=d['leaf'],
                           paired=(i in door_paired)) for i, d in enumerate(doors)],
               door_openings=[o for o in openings if o['kind'] == 'door'],
               jambs=len(jambs), jamb_pts=[[round(float(j['c'][0])), round(float(j['c'][1])), round(float(j['w'])), round(float(j['out'][0]), 2), round(float(j['out'][1]), 2)] for j in jambs], openings=openings, columns=cols,
               net=[[[round(x), round(y)] for x, y in g.coords] for g in net],
               stats=dict(lines_raw=n_raw, lines_healed=n, pieces=len(pieces), anchor_components=len(anchor_comps),
                          net_pieces=len(net), pruned=pruned, islands=len(islands), furniture_islands=furn, columns=len(cols),
                          arcs=len(doors), doors_with_leaf=sum(d['leaf'] is True for d in doors), doors_arc_only=sum(d['leaf'] == 'arc_only' for d in doors),
                          openings=dict(collections.Counter(o['kind'] for o in openings)),
                          heal=Hl.summary()['ops']),
               net_layers=lay_net.most_common(25))
    res['_off'] = off; res['_net'] = net; res['_cols_pieces'] = cols
    return res


if __name__ == '__main__':
    r = analyze(sys.argv[1])
    r = {k_: v for k_, v in r.items() if not k_.startswith('_')}
    json.dump(r, open(sys.argv[2] + '_geo.json', 'w', encoding='utf-8'), ensure_ascii=False)
    print(json.dumps(r['stats'], ensure_ascii=False))
    print('선망 레이어(참고):', r['net_layers'][:15])
