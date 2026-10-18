"""CAD 평면 → 벽·문·창·실 추출.
python cad_plan.py <층.dxf> <출력접두어> [--map layer_map.json] [--res 20]
흐름: 레이어 대응 → 선 보정(cad_heal) → 문/창 구역 다리 놓기(문 닫기) → 실 채우기 → 벽=나머지 → 공리 검사"""
import sys, os, json, math, re, argparse, collections, hashlib
from pathlib import Path
import numpy as np, cv2
from shapely.geometry import box, LineString, Polygon, MultiPoint, Point
from shapely.ops import unary_union
from cadio import load, units_to_m
from cad_heal import Healer
from cad_topology import room_rings, jamb_support, connection_status


# ---------------- 레이어 대응 ----------------
class LayerMap:
    def __init__(self, fn):
        j = json.load(open(fn, encoding='utf-8'))
        self.order = j['order']
        self.rules = {k: [re.compile(r, re.I) for r in v] for k, v in j['rules'].items()}
        self.ov = {k.upper(): v for k, v in j.get('overrides', {}).items()}

    def cat(self, layer):
        layer = layer.upper().strip()
        if layer in self.ov: return self.ov[layer]
        for c in self.order:
            if any(r.search(layer) for r in self.rules[c]): return c
        return 'other'


# 표준 여닫이 문짝 폭(mm, 500=PS·점검문). 문 레이어가 아닌 호는 이 값(±STD_TOL)에 맞을 때만 문으로 인정
STD_DOOR_W = [500, 600, 700, 750, 800, 850, 900, 950, 1000, 1100, 1200]
STD_TOL = 50
STD_DOOR_H = 2100      # 표준 문 높이(mm). 외부 출입문(자동문·현관) 2400
STD_DOOR_H_MAIN = 2400
def std_width(r):
    w = min(STD_DOOR_W, key=lambda v: abs(v - r))
    return w if abs(w - r) <= STD_TOL else None

DASHED = re.compile(r'^DASHED:|HID|DASH|CENT|PHAN|DOT|DIVIDE|BORDER|점선|숨은', re.I)


def segs_of(prim):
    p = prim.pts
    out = [(p[i][0], p[i][1], p[i + 1][0], p[i + 1][1]) for i in range(len(p) - 1)]
    if prim.closed and len(p) > 2 and (p[0] != p[-1]):
        out.append((p[-1][0], p[-1][1], p[0][0], p[0][1]))
    return out


def cluster_boxes(items, tol):
    """items: list of (bbox shapely, payload) → 겹치는(tol) 것끼리 묶음"""
    from shapely.strtree import STRtree
    n = len(items)
    if not n: return []
    geoms = [b.buffer(tol) for b, _ in items]
    st = STRtree(geoms)
    par = list(range(n))

    def f(a):
        while par[a] != a: par[a] = par[par[a]]; a = par[a]
        return a
    for i, g in enumerate(geoms):
        for j in st.query(g):
            if j > i and geoms[j].intersects(g): par[f(j)] = f(i)
    gr = collections.defaultdict(list)
    for i in range(n): gr[f(i)].append(i)
    return list(gr.values())


def plan_region(prims, cats, k2m):
    """벽 요소가 몰린 영역(도곽·표제란 제외)"""
    P = np.array([q for p, c in zip(prims, cats) if c in ('wall', 'column') for q in p.pts])
    if not len(P):
        raise ValueError('벽·기둥 레이어를 찾지 못했습니다. layer_map.json의 대응표를 확인하세요.')
    lo, hi = np.percentile(P, 1, 0), np.percentile(P, 99, 0)
    pad = 3.0 / k2m
    return box(lo[0] - pad, lo[1] - pad, hi[0] + pad, hi[1] + pad)


def run(fn, out, mapfn, res_m=0.02, prm=None, floor=None, review_profile=None):
    if not math.isfinite(res_m) or res_m <= 0:
        raise ValueError('res_m은 0보다 큰 유한한 미터 값이어야 합니다.')
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    basement = bool(floor and re.match(r'^B\d', floor))
    cad_diagnostics = []
    doc, prims, inserts = load(fn, diagnostics=cad_diagnostics)
    unit = units_to_m(doc, prims)          # 도면단위 → m
    if doc.header.get('$INSUNITS',0) not in (1,2,4,5,6):
        cad_diagnostics.append(dict(kind='units_inferred',insunits=doc.header.get('$INSUNITS',0),assumed_unit_m=unit))
    k2mm = unit * 1000.0                   # 도면단위 → mm
    lm = LayerMap(mapfn)
    cats = [lm.cat(p.layer) for p in prims]
    from cad_review_rules import apply_source_review
    source_review = apply_source_review(fn, prims, cats, review_profile)
    # 블록 안 0번(·미분류) 레이어 선은 감싸는 블록 이름으로 분류: 창호 블록(FIX_WINDOWS 등)이 0번 레이어로 그려진 경우
    BWIN = re.compile(r'WIN|GLZ|GLASS|CURTAIN|창(?!고)', re.I); BDOOR = re.compile(r'DOOR|(?<![가-힣])문(?![자서])|SHUTTER|셔터', re.I)
    BIGN = re.compile(r'FUR|BATH|TOILET|변기|욕조|세면|CAR|주차|SYM|TEXT|TIT|FORM|COLBUB|LEVEL|기둥열', re.I)
    def blk_cat(iid):
        while iid is not None:
            n = inserts[iid]['name'].split('$')[-1]
            if BIGN.search(n): return None
            if BWIN.search(n): return 'window'
            if BDOOR.search(n): return 'door'
            iid = inserts[iid]['parent']
        return None
    n_blk = collections.Counter()
    for i_, (p, c) in enumerate(zip(prims, cats)):
        if p.ins is not None and (c in ('ignore', 'other') and re.fullmatch(r'0|DEFPOINTS', p.layer, re.I) or c == 'other'):
            b_ = blk_cat(p.ins)
            if b_: cats[i_] = b_; n_blk[b_] += 1
    from cad_layers import cross_layer_evidence
    layer_evidence = cross_layer_evidence(prims, cats, unit, DASHED, std_width)
    reg = plan_region(prims, cats, unit)
    layer_tab = collections.Counter((p.layer, c) for p, c in zip(prims, cats))

    # 영역 안 요소만, 좌표 mm
    def mm(pts): return [(x * k2mm, y * k2mm) for x, y in pts]
    W, Wm, doors, wins, stairs, elevs = [], [], [], [], [], []
    def is_arc_door(p, c):
        return (p.arc and c in ('window', 'other', 'ignore') and std_width(p.arc[2] * k2mm) is not None and not DASHED.search(p.lt)
                and 60 <= (p.arc[4] - p.arc[3]) % 360 <= 190 and not re.search(r'FUR|BATH|TOILET|CAR|SYM|TEXT|DIM', p.layer))
    inreg, hidden, beams = [], [], []
    for p, c in zip(prims, cats):
        xs = [q[0] for q in p.pts]; ys = [q[1] for q in p.pts]
        if reg.intersects(box(min(xs), min(ys), max(xs), max(ys))): inreg.append((p, c))
    # 규칙: 1/4원 호 = 여닫이문 (창호 통합 레이어 WID 등). 호 중심에서 반지름만큼 뻗은 직선 = 문짝 → 문으로
    from cad_auto import repeated_tier_arcs
    auto_excluded, auto_checks = repeated_tier_arcs(inreg, inserts, unit)
    arcs = [p for p, c in inreg if c != 'door' and is_arc_door(p, c)]
    from scipy.spatial import cKDTree as _KD
    hinge = _KD(np.array([[a.arc[0], a.arc[1]] for a in arcs])) if arcs else None
    def is_leaf(p):
        # 문짝: 꼭짓점 하나가 호 중심(경첩) 60mm 안 + 모든 점이 반지름+60mm 안 (선이든 얇은 사각형이든)
        if hinge is None: return False
        from cad_door_rules import diameter_leaf
        if not p.arc and any(diameter_leaf(p.pts,a.arc,unit) for a in arcs
                            if LineString(p.pts).distance(Point(a.arc[:2]))*unit<.06):return True
        for e in p.pts:
            d, i = hinge.query(e)
            if d * k2mm < 60:
                c = arcs[i].arc; r_ = c[2]
                if not all(math.hypot(x - c[0], y - c[1]) <= r_ + 60 / k2mm for x, y in p.pts): return False
                g = MultiPoint(p.pts).minimum_rotated_rectangle
                if g.geom_type != 'Polygon': return math.dist(p.pts[0], p.pts[-1]) >= 0.7 * r_
                xy = np.array(g.exterior.coords[:4]); a_, b_ = math.dist(xy[0], xy[1]), math.dist(xy[1], xy[2])
                return max(a_, b_) >= 0.7 * r_ and min(a_, b_) * k2mm <= 80   # 길고 얇은 것 = 문짝
        return False
    aset = set(map(id, arcs))
    for p, c in inreg:
        if id(p) in auto_excluded: continue
        if c == 'door' or id(p) in aset or (c in ('window', 'other') and is_leaf(p)):
            doors.append(p); continue
        if c in ('wall', 'column', 'window') and DASHED.search(p.lt):
            hidden.append(p.layer)
            # 숨은선 중 폭 0.15~0.5m·길이 0.8m↑ 닫힌 띠 = 머리 위 보(공간은 안 가르고 연기 경계 요소)
            if len(p.pts) >= 4:   # 닫힌 띠 + 열린 ㄷ자 띠(벽에 붙은 보)
                mr = MultiPoint(mm(p.pts)).minimum_rotated_rectangle; g_ = mr
                if mr.geom_type == 'Polygon':
                    xy_ = np.array(mr.exterior.coords[:4]); a_, b_ = math.dist(xy_[0], xy_[1]), math.dist(xy_[1], xy_[2])
                    if 150 <= min(a_, b_) <= 500 and max(a_, b_) >= 800:
                        beams.append([[round(x / 1000, 3), round(y / 1000, 3)] for x, y in g_.exterior.coords[:-1]])
            continue   # 숨은선·점선(상부층 외벽선·보)은 벽으로 안 씀
        if c in ('wall', 'column', 'window'):
            for s in segs_of(p):
                W.append([v * k2mm for v in s]); Wm.append(dict(cat=c, layer=p.layer))
        if c == 'window': wins.append(p)
        if c == 'stair': stairs.append(p)
        if c == 'elev': elevs.append(p)

    # ---- 문 구역: 문 레이어 요소 묶음, 호 반지름 ----
    zones = []
    items = []
    for p in doors:
        q = np.array(mm(p.pts)); items.append((box(*q.min(0), *q.max(0)), p))
    for g in cluster_boxes(items, 50):
        bb = unary_union([items[i][0] for i in g])
        r = None
        for i in g:
            a = items[i][1].arc
            if a:
                sw = (a[4] - a[3]) % 360
                if 60 <= sw <= 190: r = max(r or 0, a[2] * k2mm)
        if bb.area < 200 * 200 and not r: continue
        zones.append(dict(id=f'D{len(zones)}', kind='door', poly=bb.envelope.buffer(150, join_style=2), r=r,
                          tight=bb.envelope))
    # 문 블록(이름에 DOOR·문): 내부 레이어가 제각각(문틀·유리·승강기 레이어 등)이어도 블록 전체 범위를 문 구역으로
    def door_anc(iid):
        while iid is not None:
            n = inserts[iid]['name'].split('$')[-1]
            if BIGN.search(n): return None
            if BDOOR.search(n): return iid
            iid = inserts[iid]['parent']
        return None
    dblk = collections.defaultdict(list)
    for p, c in inreg:
        if p.ins is None: continue
        a_ = door_anc(p.ins)
        if a_ is not None: dblk[a_].append(p)
    for a_, ps in dblk.items():
        q = np.array([v for p in ps for v in mm(p.pts)])
        bb = box(*q.min(0), *q.max(0))
        if bb.area < 300 * 300 or bb.area > 6000 * 6000: continue
        r = max([p.arc[2] * k2mm for p in ps if p.arc and 60 <= (p.arc[4] - p.arc[3]) % 360 <= 190] or [0]) or None
        cov = [z for z in zones if z['kind'] == 'door' and z['tight'].buffer(50).contains(bb)]
        if cov: continue
        zones.append(dict(id=f'D{len(zones)}', kind='door', poly=bb.buffer(150, join_style=2), r=None, tight=bb,
                          block=inserts[a_]['name'].split('$')[-1], r_arc=r))
    nd = len(zones)
    from shapely.strtree import STRtree as _ST
    # ---- 문짝 모델: 경첩·표준 폭·닫힌 위치·열림 방향 (도면 호 그대로) ----
    # 표준 문짝 폭(mm): 여닫이 600~1200. 반지름을 ±40mm 안에서 표준값에 맞춤(아니면 원값, 비표준 표시)
    STD_W = [600, 700, 750, 800, 850, 900, 950, 1000, 1100, 1200]
    door_arcs = [p for p in doors if p.arc and 350 <= p.arc[2] * k2mm <= 1900 and 60 <= (p.arc[4] - p.arc[3]) % 360 <= 190]
    leaf_lines = [p for p in doors if not p.arc and len(p.pts) >= 2]
    wl = [LineString([(a_[0], a_[1]), (a_[2], a_[3])]) for a_ in W]
    wtree = _ST(wl) if wl else None
    from cad_door_rules import gap_axis_score
    axis_walls=[LineString(np.asarray(line.coords)/1000) for line in wl]
    axis_tree=_ST(axis_walls) if axis_walls else None
    # 벽으로 쓰지 않은 칸막이 선(무시·미분류 레이어, 숨은선 제외): 실 내부 문 판정용
    pl_ = []
    for p, c in inreg:
        if c in ('ignore', 'other') and not DASHED.search(p.lt) and len(p.pts) >= 2 and not p.arc:
            q = mm(p.pts)
            for u_, v_ in zip(q, q[1:]):
                if math.dist(u_, v_) > 50: pl_.append(LineString([u_, v_]))
    ptree = _ST(pl_) if pl_ else None
    def near_any(tree, geoms, pt, rad):
        if tree is None: return False
        g = Point(pt)
        return any(geoms[t].distance(g) <= rad for t in tree.query(g.buffer(rad)))
    def par_wall(pt, v, rad=80):
        # pt 근처에 v 방향과 나란한 벽선이 있는가(닫힌 문짝은 벽선과 나란함)
        if wtree is None: return 0
        g = Point(pt).buffer(rad); n_ = 0
        for t in wtree.query(g):
            L_ = wl[t]
            if L_.distance(Point(pt)) > rad or L_.length < 50: continue
            (ax_, ay_), (bx_, by_) = L_.coords
            u_ = np.array([bx_ - ax_, by_ - ay_]) / L_.length
            if abs(u_ @ v) > 0.97: n_ += 1
        return n_
    leaves = []
    for p in door_arcs:
        cx, cy, r0, a0, a1 = p.arc
        hx, hy, r = cx * k2mm, cy * k2mm, r0 * k2mm
        sw = (a1 - a0) % 360
        rs = std_width(r); std = rs is not None; rs = rs or r
        hv = np.array([hx, hy])
        def P_(ang): return hv + r * np.array([math.cos(math.radians(ang)), math.sin(math.radians(ang))])
        e0, e1, em = P_(a0), P_(a1), P_(a0 + sw / 2)
        # 문짝선: 경첩 120mm 안에서 시작, 길이 ≥0.6r, 두께 ≤80
        ldir = None
        # A thin closed leaf outline is stronger than a coincident closed-span
        # construction line. Otherwise the latter can reverse a quarter swing.
        for lp in sorted(leaf_lines,key=lambda q:not(q.closed and len(q.pts)>=4)):
            q = np.array(mm(lp.pts))
            dh = np.hypot(*(q - hv).T)
            if dh.min() > 120 or dh.max() > r + 80 or dh.max() < 0.6 * r: continue
            far = q[np.argmax(dh)]; ldir = (far - hv) / (np.hypot(*(far - hv)) + 1e-9); break
        # 닫힌 위치 후보: 호 양 끝(+반원이면 중간). 점수 = 경첩 반대편 벽선이 나란함 + 그 방향 r+r' 거리에 짝 경첩
        cands = [e0, e1] + ([em] if sw > 150 else [])
        def score(e):
            v = (e - hv) / r; sc_ = min(par_wall(hv - v * 60, v), 2)
            if sw>150:sc_ += gap_axis_score(hv/1000,e/1000,axis_walls,axis_tree)
            for q_ in door_arcs:
                if q_ is p: continue
                h2 = np.array([q_.arc[0] * k2mm, q_.arc[1] * k2mm]); r2 = q_.arc[2] * k2mm
                dv = h2 - hv; dl = np.hypot(*dv)
                if abs(dl - (r + r2)) < 0.12 * (r + r2) and (dv / dl) @ v > 0.97: sc_ += 5
            if ldir is not None and abs(v @ ldir) < 0.3: sc_ += 1      # 문짝선과 직각 = 닫힌 쪽
            if ldir is not None and abs(v @ ldir) > 0.9: sc_ -= 2      # 문짝선과 나란 = 열린 쪽
            return sc_
        scs = [score(e) for e in cands]
        bi = int(np.argmax(scs))
        if sw > 150 and scs[bi] == scs[2]: bi = 2                   # 동점이면 반원 = 양방향 문
        ec = cands[bi]; vc = (ec - hv) / r
        if bi == 2:
            kind_, eo, eo2 = 'double_acting', e0, e1
        else:
            rest = [e for j_, e in enumerate(cands) if j_ != bi]
            eo = min(rest, key=lambda e: abs(((e - hv) / r) @ vc)); kind_, eo2 = 'single', None
        vc = (ec - hv) / r; vo = (eo - hv) / r
        if std:   # 표준 폭으로 닫힌 끝·열린 끝 보정(작도 오차 제거)
            ec = hv + vc * rs; eo = hv + vo * rs
            if eo2 is not None: eo2 = hv + (eo2 - hv) / r * rs
        sgn = 1 if (vc[0] * vo[1] - vc[1] * vo[0]) > 0 else -1     # 닫힘→열림 회전 방향(+ 반시계)
        leaves.append(dict(hinge=hv, r=rs if std else r, r_raw=r, r_std=rs if std else None, closed=ec, open=eo, open2=eo2, kind=kind_, sweep=sw, sgn=sgn,
                           layer=p.layer, leaf_line=ldir is not None))
    # 양개문 짝: 두 문짝의 닫힌 끝이 만남
    for i_, A_ in enumerate(leaves):
        for j_ in range(i_ + 1, len(leaves)):
            B_ = leaves[j_]
            if 'pair' in B_: continue
            if math.dist(A_['closed'], B_['closed']) < 0.15 * min(A_['r'], B_['r']) and \
               abs(math.dist(A_['hinge'], B_['hinge']) - (A_['r'] + B_['r'])) < 0.15 * (A_['r'] + B_['r']):
                A_['pair'] = j_; B_['pair'] = i_
    for L_ in leaves:   # 구역 배정
        for z in zones:
            if z['kind'] == 'door' and z['poly'].contains(Point(*L_['hinge'])): L_['zone'] = z['id']; break
    dz = [z['tight'].buffer(100) for z in zones if z['tight'].area < 12e6]   # 큰 문틀 묶음(유리 칸막이 체계)은 제외
    if dz:
        _t = _ST(dz)
        def _in_door(p):
            q = np.array(mm(p.pts)); b = box(*q.min(0), *q.max(0))
            return any(dz[i].contains(b) for i in _t.query(b))
        wins = [p for p in wins if not _in_door(p)]
    items = []
    for p in wins:
        q = np.array(mm(p.pts)); items.append((box(*q.min(0), *q.max(0)), p))
    dropped_jamb = 0
    for g in cluster_boxes(items, 20):
        bb = unary_union([items[i][0] for i in g]).envelope
        b_ = bb.bounds
        # 문틀 끝 조각·창틀 마구리(긴 변 350mm 미만)는 창 아님
        if max(b_[2] - b_[0], b_[3] - b_[1]) < 350: dropped_jamb += 1; continue
        zones.append(dict(id=f'W{len(zones) - nd}', kind='window', poly=bb.buffer(100, join_style=2), r=None, tight=bb))

    # ---- 선 보정 ----
    # Known closed-leaf spans protect real openings from generic gap sealing.
    for z in zones:
        z['protected_spans'] = [LineString([L_['hinge'], L_['closed']])
                                for L_ in leaves if L_.get('zone') == z['id']]
        zl=[L_ for L_ in leaves if L_.get('zone')==z['id']]
        # Large CAD blocks can group several unrelated doors. They need their
        # own decomposition; do not reinterpret the whole block from one arc.
        z['closed_leaf_bridge_guard']=bool(zl) and len(zl)<=2 and all(L_['sweep']>150 for L_ in zl)
    H = Healer(W, Wm, prm)
    bridges = H.run(zones)

    # ---- 래스터 ----
    R = res_m * 1000.0  # mm/px
    S = np.array(H.S)
    x0, y0 = S[:, [0, 2]].min() - 2000, S[:, [1, 3]].min() - 2000
    x1, y1 = S[:, [0, 2]].max() + 2000, S[:, [1, 3]].max() + 2000
    Wd, Hd = int((x1 - x0) / R) + 1, int((y1 - y0) / R) + 1
    if Wd * Hd > 40_000_000:
        raise ValueError(f'래스터 {Wd}×{Hd}가 너무 큽니다. 도면 범위·단위·해상도를 확인하세요.')
    T = lambda x, y: (int(round((x - x0) / R)), int(round((y1 - y) / R)))
    Ti = lambda u, v: (u * R + x0, y1 - v * R)
    bar = np.zeros((Hd, Wd), np.uint8)
    for s, m in zip(H.S, H.M):
        cv2.line(bar, T(s[0], s[1]), T(s[2], s[3]), 255, 1)
    # 문짝 닫힌 위치(경첩→닫힌 끝) = 문이 닫혔을 때의 경계선. 다리(bridge)가 없어도 문으로 실을 가름
    have_br = {b['zone'] for b in bridges}
    jamb_checks = []
    for L_ in leaves:
        hx_, hy_ = L_['hinge']; cx_, cy_ = L_['closed']
        cv2.line(bar, T(hx_, hy_), T(cx_, cy_), 255, 1)
        # 문 닫힘선의 양쪽 지지 검사. 기존 실 구획용 임시 연결은 별도로 기록.
        if wtree is not None:
            vv = np.array([cx_ - hx_, cy_ - hy_]); vv = vv / (np.hypot(*vv) + 1e-9)
            mates = [LineString([M_['hinge'], M_['closed']]) for M_ in leaves
                     if M_ is not L_ and M_.get('zone') == L_.get('zone')
                     and math.dist(M_['closed'], L_['closed']) <= 3]
            supports = [jamb_support(ex_, sg_ * vv, wl, wtree, mates)
                        for ex_, sg_ in (((hx_, hy_), -1), ((cx_, cy_), 1))]
            confirmed = all(q_ is not None for q_ in supports)
            if not confirmed:
                jamb_checks.append(dict(rule='A문-문틀지지미확인', id=L_.get('zone'),
                                        note='문 닫힘선 양 끝의 축방향 지지 미확인 — 실 구획용 임시 연결을 검토해야 함'))
            # Preserve the established segmentation until a candidate is reviewed.
            # These links are explicitly temporary boundaries, not new wall evidence.
            for ex_ in ((hx_, hy_), (cx_, cy_)):
                pe = Point(ex_); best_ = None
                for index in wtree.query(pe.buffer(300)):
                    distance = wl[index].distance(pe)
                    if 1 < distance <= 300 and (best_ is None or distance < best_[0]):
                        best_ = (distance, index)
                if best_:
                    q_ = wl[best_[1]].interpolate(wl[best_[1]].project(pe))
                    cv2.line(bar, T(*ex_), T(q_.x, q_.y), 255, 1)
                    H.log.append(dict(op='jamb_partition', zone=L_.get('zone'),
                                      at=list(map(float, ex_)), to=[q_.x, q_.y],
                                      dist=round(best_[0], 2), usage='segmentation_only',
                                      axis_support_confirmed=confirmed))
        if L_.get('zone') and L_['zone'] not in have_br:
            bridges.append(dict(seg=[float(hx_), float(hy_), float(cx_), float(cy_)], zone=L_['zone'], kind='door', width=round(L_['r']), src='leaf'))
            H.log.append(dict(op='leaf_close', zone=L_['zone'], at=[round(hx_, 1), round(hy_, 1)], to=[round(cx_, 1), round(cy_, 1)], dist=round(L_['r'], 1)))
    # 기둥 닫힌 도형 채움 + 벽 레이어의 작은 닫힌 도형(2.5㎡ 이하: 기둥·벽 조각)도 채움
    for p, c in zip(prims, cats):
        if c == 'wall' and p.closed and len(p.pts) > 2 and not DASHED.search(p.lt):
            q = np.array(mm(p.pts))
            g_ = Polygon(q)
            # 기둥·벽 조각만 채움: 1.2㎡ 이하 + 문이 붙지 않은 것 (문 달린 작은 닫힌 도형 = 샤프트(PS·EPS) → 실로 남김)
            if g_.area <= 1.2e6 and not any(z['kind'] == 'door' and z['tight'].distance(g_) < 300 for z in zones):
                cv2.fillPoly(bar, [np.int32([T(x, y) for x, y in q])], 255)
        if c == 'column' and p.closed and len(p.pts) > 2:
            q = np.int32([T(x, y) for x, y in mm(p.pts)])
            cv2.fillPoly(bar, [q], 255)
    pass
    if os.environ.get('DUMPBAR'): cv2.imwrite(out + '_bar.png', 255 - bar)
    seal_px = max(1, int(round(H.p.get('seal_max', 550) / 2 / R)))
    _ek = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * seal_px + 1, 2 * seal_px + 1))
    def flood(b):
        # 공리: 외기는 최소 문 폭(seal_max) 미만 통로로 들어오지 않음 → 벽을 반폭만큼 부풀려 채운 뒤, 자유 공간 안에서만 되돌림
        bd = cv2.dilate(b, _ek)
        ff = bd.copy(); msk = np.zeros((Hd + 2, Wd + 2), np.uint8)
        cv2.floodFill(ff, msk, (0, 0), 128, flags=4)
        o = (ff == 128).astype(np.uint8); free_ = (b == 0).astype(np.uint8); k3 = np.ones((3, 3), np.uint8)
        for _ in range(seal_px + 1):
            o = cv2.dilate(o, k3) & free_
        return o.astype(bool)
    outside = flood(bar)
    # 외곽 폐합: 문 기호 없는 공선 틈(자동문·출입구)을 임시로 닫아 보고, 새로 막힌 영역이 생기면
    # 바깥과 맞닿은 틈만 '외곽 개구부(추정)'로 닫는다. 실내 틈(통로)은 닫지 않음.
    gaps = [f for f in H.flags if f['kind'] == 'gap_unlabeled' and f['width'] <= H.p['bridge_max']]
    env_bridges = []
    if gaps:
        b2 = bar.copy()
        for f in gaps: cv2.line(b2, T(*f['at']), T(*f['to']), 255, 1)
        out2 = flood(b2)
        newin = outside & ~out2
        if newin.sum() * (R / 1000) ** 2 > 2.0:
            o2d = cv2.dilate(out2.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
            n2d = cv2.dilate(newin.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
            for f in gaps:
                m = np.zeros_like(bar); cv2.line(m, T(*f['at']), T(*f['to']), 255, 1)
                px = m > 0
                if (o2d & px).any() and (n2d & px).mean() > 0.3:
                    cv2.line(bar, T(*f['at']), T(*f['to']), 255, 1)
                    f['kind'] = 'gap_envelope_closed'
                    env_bridges.append(dict(seg=[*f['at'], *f['to']], zone=f'E{len(env_bridges)}', kind='opening', width=f['width']))
            outside = flood(bar)
    # 승강기 문: 문 기호 없는 틈(0.7~2.5m) 중 승강기 요소 0.8m 안 → 승강장 문으로 닫음
    if elevs:
        eb = [box(*np.array(mm(p.pts)).min(0), *np.array(mm(p.pts)).max(0)).buffer(800) for p in elevs]
        et = _ST(eb)
        n_el = 0
        for f in H.flags:
            if f['kind'] != 'gap_unlabeled' or not (700 <= f['width'] <= 2500): continue
            mid_ = Point((f['at'][0] + f['to'][0]) / 2, (f['at'][1] + f['to'][1]) / 2)
            if any(eb[i].contains(mid_) for i in et.query(mid_)):
                cv2.line(bar, T(*f['at']), T(*f['to']), 255, 1); f['kind'] = 'gap_elev_closed'
                env_bridges.append(dict(seg=[*f['at'], *f['to']], zone=f'EV{n_el}', kind='door_elev', width=f['width'])); n_el += 1
        if n_el: outside = flood(bar)
    # ---- 누락 벽 보완(공리: 문은 두 공간을 가른다) ----
    # 문 양쪽이 같은 영역이면, 그 문 근처(4m) 벽의 열린 끝에 붙어 있는 비(非)벽 레이어 선(트렌치·마감선 등) 중
    # 하나를 벽으로 넣었을 때 문 양쪽이 갈리면 그 선을 '누락 벽(추정)'으로 채택. 원래 없던 선을 만들지는 않음.
    kpx = max(3, int(round(400 / R)))
    def labels_of(b):
        o_ = flood(b)
        f_ = ((b == 0) & ~o_).astype(np.uint8)
        f_ = cv2.morphologyEx(f_, cv2.MORPH_OPEN, np.ones((kpx, kpx), np.uint8))
        _, lb = cv2.connectedComponents(f_, connectivity=4)
        lb[o_] = -1
        return lb
    def door_sides(lb, b):
        s_ = b['seg']; ax_, ay_, bx_, by_ = s_
        L_ = math.hypot(bx_ - ax_, by_ - ay_) or 1
        nx_, ny_ = -(by_ - ay_) / L_, (bx_ - ax_) / L_
        mx_, my_ = (ax_ + bx_) / 2, (ay_ + by_) / 2
        out_ = []
        for sg in (1, -1):
            got = 0
            for d_ in range(250, 1300, 50):
                u_, v_ = T(mx_ + sg * nx_ * d_, my_ + sg * ny_ * d_)
                if 0 <= v_ < Hd and 0 <= u_ < Wd and lb[v_, u_] != 0: got = int(lb[v_, u_]); break
            out_.append(got)
        return out_
    added_walls = []
    door_br = [b for b in bridges if b['kind'] == 'door']
    if door_br:
        lb = labels_of(bar)
        bad = [b for b in door_br if (lambda sd: sd[0] == sd[1] and sd[0] > 0)(door_sides(lb, b))]
        dang = [f for f in H.flags if f['kind'] == 'dangling']
        # 레이어를 믿되 공리 위배 시 다른 레이어 선도 후보: 분류 안 된 레이어 → 무시 레이어(가구·문자틀 등) 순
        others = [p for p, c in inreg if c == 'other' and not DASHED.search(p.lt)] + \
                 [p for p, c in inreg if c == 'ignore' and not DASHED.search(p.lt) and len(p.pts) >= 2]
        tried = set()
        for b in bad:
            bm = ((b['seg'][0] + b['seg'][2]) / 2, (b['seg'][1] + b['seg'][3]) / 2)
            ends = [f['at'] for f in dang if math.dist(f['at'], bm) < 4000]
            cands = []
            for p in others:
                if id(p) in tried: continue
                q = mm(p.pts)
                if any(min(math.dist(e, v) for v in q) < 150 for e in ends) or                    any(LineString(q).distance(Point(e)) < 150 for e in ends if len(q) >= 2):
                    cands.append(p)
            for p in cands:
                tried.add(id(p))
                b2 = bar.copy()
                cv2.polylines(b2, [np.int32([T(x, y) for x, y in mm(p.pts)])], p.closed, 255, 1)
                sd = door_sides(labels_of(b2), b)
                if sd[0] != sd[1] and min(sd) != 0:
                    bar = b2; added_walls.append(dict(layer=p.layer, n=len(p.pts), at=[round(v) for v in mm(p.pts)[0]]))
                    H.log.append(dict(op='missing_wall', layer=p.layer, at=[round(v) for v in mm(p.pts)[0]]))
                    break
        if added_walls: outside = flood(bar)
    from cad_auto import adaptive_close
    protected = np.zeros_like(bar)
    for z in zones:
        g = z['tight'].buffer(max(100,R*2))
        if g.geom_type == 'Polygon' and not g.is_empty:
            cv2.fillPoly(protected,[np.int32([T(x,y) for x,y in g.exterior.coords])],255)
    bar, close_report = adaptive_close(bar, protected>0, labels_of, door_br, door_sides, R)
    auto_checks.append(close_report)
    outside = flood(bar)
    free = ((bar == 0) & ~outside).astype(np.uint8)
    # 실 = 빈 공간 중 폭 0.4m 사각이 들어가는 부분(열림 연산). 벽 두 줄(구조선·마감선) 사이 얇은 띠는
    # 넓은 곳과 이어져 있어도 실에서 떨어져 벽 몸체로 감 (덩어리 단위 두께 판정의 오류 수정)
    free_raw = free
    free = cv2.morphologyEx(free, cv2.MORPH_OPEN, np.ones((kpx, kpx), np.uint8))
    n, lab, st, cen = cv2.connectedComponentsWithStats(free, connectivity=4)
    dt = cv2.distanceTransform(free, cv2.DIST_L2, 3)
    room_ids = []
    rooms = []
    room_mask = np.zeros_like(bar)
    mx = np.zeros(n)
    np.maximum.at(mx, lab.ravel(), dt.ravel())
    for i in range(1, n):
        a = st[i, cv2.CC_STAT_AREA] * (R / 1000) ** 2
        th = mx[i] * 2 * R / 1000
        if th < 0.5 or a < 0.25: continue
        room_ids.append(i)
    rid_of = {}
    for k, i in enumerate(room_ids):
        m = (lab == i)
        room_mask[m] = 255
        rid_of[i] = k
        polys = room_rings(m, Ti)
        poly = polys[0]['o']
        geometry = unary_union([Polygon(p['o'], p['h']) for p in polys])
        a = st[i, cv2.CC_STAT_AREA] * (R / 1000) ** 2
        rooms.append(dict(id=f'R{k}', area=round(geometry.area, 4), raster_area=round(a, 4),
                          poly=poly, holes=polys[0]['h'], polys=polys,
                          center=[round(Ti(*cen[i])[0] / 1000, 3), round(Ti(*cen[i])[1] / 1000, 3)]))
    # 공리: 문 없이 외부와 얇은 선 하나로만 닿는 '실' = 외부 영역(캐노피·테라스 외곽선 등) → 외부로 돌림
    ring_k = max(3, int(round(150 / R)))
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * ring_k + 1, 2 * ring_k + 1))
    reclass = []
    for k, i in enumerate(room_ids):
        m = (lab == i).astype(np.uint8)
        ring = cv2.dilate(m, ker) & (1 - m)
        fr = (ring.astype(bool) & outside).sum() / max(ring.sum(), 1)
        rooms[k]['ext_touch'] = round(float(fr), 3)
        if fr > 0.2:
            reclass.append(k)
    pre_checks = list(auto_checks)
    for k in reclass:
        i = room_ids[k]
        outside |= (lab == i)
        room_mask[lab == i] = 0
        pre_checks.append(dict(rule='A외부-얇은경계', id=rooms[k]['id'], area=rooms[k]['area'], ext_touch=rooms[k]['ext_touch'],
                               note='외기와 얇은 선 하나로 접한 영역 → 외부(캐노피·테라스)로 재분류'))
    keep = [k for k in range(len(rooms)) if k not in reclass]
    room_ids = [room_ids[k] for k in keep]; rooms = [rooms[k] for k in keep]
    rid_of = {i: k for k, i in enumerate(room_ids)}
    for k, r in enumerate(rooms): r['id'] = f'R{k}'
    # 외부로 돌린 영역 사이 선은 벽에서 제외(외부와 붙은 1픽셀 선): 외부 팽창으로 흡수
    foot = (~outside).astype(np.uint8) * 255
    thin = cv2.morphologyEx(foot, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    foot = thin
    wallbody = cv2.bitwise_and(foot, cv2.bitwise_not(room_mask))

    # ---- 계단·승강기 실 표시 ----
    def tag_rooms(plist, tag):
        cov = np.zeros_like(bar)
        for p in plist:
            q = np.array(mm(p.pts))
            u0, v1 = T(*q.min(0)); u1, v0 = T(*q.max(0))
            cv2.rectangle(cov, (u0, v0), (u1, v1), 255, -1)
        for k, i in enumerate(room_ids):
            m = lab == i
            fr = (cov[m] > 0).mean()
            if fr > 0.35: rooms[k].setdefault('tags', set()).add(tag)
            elif fr > 0.02: rooms[k].setdefault('tags', set()).add(tag + '_inside')
    tag_rooms(stairs, 'stair'); tag_rooms(elevs, 'elev')
    # 실 이름: 실 안에 놓인 문자(기둥·치수·도곽 문자 제외)
    import ezdxf as _ez
    skipL = re.compile(r'COL|DIM|TIT|^TX|BATH|CEN', re.I)
    def texts(ents, depth=0):
        for e in ents:
            t = e.dxftype()
            if t in ('TEXT', 'MTEXT'):
                yield e
            elif t == 'INSERT' and depth < 4:
                try: yield from texts(e.virtual_entities(), depth + 1)
                except Exception: pass
    for e in texts(doc.modelspace()):
        if skipL.search(e.dxf.layer): continue
        raw = e.dxf.text if e.dxftype() == 'TEXT' else e.text
        tx = re.sub(r'\\[A-Za-z][^;]*;|[{}]|\\P', ' ', raw).strip()
        if not tx or re.fullmatch(r'[\d\s.,]+|UP|DN|A/C', tx) or re.search(r'\d\s*[xX×]\s*\d|배수|스리브|SV:|%%|^FL\b|^W\.?B|^GL|[+±]\s*\d|^EL\.?$', tx): continue
        ip = e.dxf.insert
        u, v = T(ip.x * k2mm, ip.y * k2mm)
        if 0 <= v < Hd and 0 <= u < Wd and lab[v, u] in rid_of:
            rooms[rid_of[lab[v, u]]].setdefault('names', []).append(tx)
    for r in rooms:
        r['tags'] = sorted(r.get('tags', []))

    # ---- 개구부(문=다리 껍질, 창=창 요소 외접) ∩ 벽체 ----
    openings = []
    checks_pre_door = []
    bz = collections.defaultdict(list)
    for b in bridges: bz[b['zone']].append(b)
    zid = {z['id']: z for z in zones}
    for z in zones:
        if z['kind'] == 'door':
            bs = bz.get(z['id'], [])
            if not bs: continue
            zl = [L_ for L_ in leaves if L_.get('zone') == z['id']]
            if zl:   # 문짝 닫힌 선을 벽 두께 방향으로 부풀린 띠 = 문 개구부
                geom = unary_union([LineString([tuple(L_['hinge']), tuple(L_['closed'])]).buffer(350, cap_style=2) for L_ in zl])
                if geom.geom_type != 'Polygon': geom = geom.convex_hull
            else:
                pts = [(b['seg'][0], b['seg'][1]) for b in bs] + [(b['seg'][2], b['seg'][3]) for b in bs]
                geom = MultiPoint(pts).convex_hull
        else:
            geom = z['tight']
            # 창: 창 요소 선 자체를 벽 두께만큼 부풀려 벽체와 교집합(ㄱ자 커튼월에서 외접사각형이 실내 벽을 먹는 문제 방지)
            m = np.zeros_like(bar)
            for p in wins:
                q = np.array(mm(p.pts))
                if not z['tight'].buffer(5).contains(box(*q.min(0), *q.max(0))): continue
                cv2.polylines(m, [np.int32([T(x, y) for x, y in q])], False, 255, 1)
            k = max(3, int(round(300 / R)) | 1)
            m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))) & wallbody
            if m.sum():
                cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                polys = [[[round(Ti(u, v)[0] / 1000, 3), round(Ti(u, v)[1] / 1000, 3)] for u, v in cv2.approxPolyDP(c, 0.8, True)[:, 0]]
                         for c in cs if cv2.contourArea(c) >= 2]
                if polys:
                    openings.append(dict(id=z['id'], kind='window', polys=polys, r=None, width=None, _mask=m, _geom=z['tight'] if z['tight'].area > 0 else z['tight'].buffer(80)))
            continue
        if geom.is_empty: continue
        if geom.geom_type != 'Polygon' or geom.area < 1e4:
            g2 = geom.buffer(80, cap_style=2, join_style=2) if geom.geom_type == 'LineString' else None
            if g2 is None or g2.is_empty or g2.geom_type != 'Polygon':
                bx = geom.bounds; g2 = box(bx[0] - 80, bx[1] - 80, bx[2] + 80, bx[3] + 80)
            geom = g2
        m = np.zeros_like(bar)
        q = np.int32([T(x, y) for x, y in geom.exterior.coords])
        cv2.fillPoly(m, [q], 255)
        m = cv2.dilate(m, np.ones((3, 3), np.uint8))
        m &= wallbody
        if (m > 0).sum() < 150 and z['kind'] == 'door':
            # 문 자리 벽 몸체가 거의 없을 때(틈이 넓은 문틀): 닫힌 선을 벽 두께(±120mm) 띠로 직접 사용
            zl_ = [L_ for L_ in leaves if L_.get('zone') == z['id']]
            if zl_:
                g3 = unary_union([LineString([tuple(L_['hinge']), tuple(L_['closed'])]).buffer(120, cap_style=2) for L_ in zl_])
                m = np.zeros_like(bar)
                for gg in (g3.geoms if hasattr(g3, 'geoms') else [g3]):
                    cv2.fillPoly(m, [np.int32([T(x, y) for x, y in gg.exterior.coords])], 255)
                m &= foot; geom = g3
        if m.sum() == 0: continue
        cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        polys = []
        for c in cs:
            if cv2.contourArea(c) < 2: continue
            c = cv2.approxPolyDP(c, 0.8, True)
            polys.append([[round(Ti(u, v)[0] / 1000, 3), round(Ti(u, v)[1] / 1000, 3)] for u, v in c[:, 0]])
        if polys:
            zl = [L_ for L_ in leaves if L_.get('zone') == z['id']] if z['kind'] == 'door' else []
            lv = [dict(hinge=[round(L_['hinge'][0] / 1000, 3), round(L_['hinge'][1] / 1000, 3)],
                       closed=[round(L_['closed'][0] / 1000, 3), round(L_['closed'][1] / 1000, 3)],
                       open=[round(L_['open'][0] / 1000, 3), round(L_['open'][1] / 1000, 3)],
                       open2=None if L_['open2'] is None else [round(L_['open2'][0] / 1000, 3), round(L_['open2'][1] / 1000, 3)],
                       r=round(L_['r'] / 1000, 3), r_std=None if L_['r_std'] is None else L_['r_std'] / 1000, kind=L_['kind'],
                       sgn=L_['sgn'], sweep=round(L_['sweep']), leaf_line=L_['leaf_line'], pair=L_.get('pair') is not None) for L_ in zl]
            for L_ in zl:
                if L_['r_std'] is None:
                    checks_pre_door.append(dict(rule='A문-비표준폭', id=z['id'], r=round(L_['r']), note=f"호 반지름 {round(L_['r'])}mm — 표준 문 폭(600~1200)과 안 맞음(점검구·셔터·가구 확인)"))
            openings.append(dict(id=z['id'], kind=z['kind'], polys=polys, leaves=lv, r=None if not z['r'] else round(z['r'] / 1000, 3),
                                 width=max([b['width'] for b in bz.get(z['id'], [])], default=None),
                                 _mask=m, _geom=geom))

    for b in env_bridges:
        g = LineString([b['seg'][:2], b['seg'][2:]]).buffer(250, cap_style=2)
        m = np.zeros_like(bar)
        cv2.fillPoly(m, [np.int32([T(x, y) for x, y in g.exterior.coords])], 255)
        m &= wallbody
        if not m.sum(): m = np.zeros_like(bar); cv2.line(m, T(*b['seg'][:2]), T(*b['seg'][2:]), 255, 3); m &= foot
        cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        polys = [[[round(Ti(u, v)[0] / 1000, 3), round(Ti(u, v)[1] / 1000, 3)] for u, v in cv2.approxPolyDP(c, 0.8, True)[:, 0]] for c in cs if cv2.contourArea(c) >= 1]
        if polys:
            openings.append(dict(id=b['zone'], kind=b.get('kind') if b.get('kind') == 'door_elev' else 'door', polys=polys, leaves=[], r=None, width=b['width'], _mask=m, _geom=g, guessed=True))

    # ---- 공리 검사(표시만) ----
    if hidden:
        pre_checks.append(dict(rule='A숨은선-제외', id='-', n=len(hidden), layers=sorted(set(hidden)),
                               note=f'벽·창 레이어의 숨은선/점선 {len(hidden)}개는 벽에서 제외(상부·하부 요소). 실이 합쳐졌으면 확인'))
    for w in added_walls:
        pre_checks.append(dict(rule='A누락벽-추정', id=w['layer'], at=w['at'], note=f"문이 공간을 못 가름 → 인접 {w['layer']} 선을 벽으로 채택(원도면 벽 누락 추정)"))
    checks = list(pre_checks) + checks_pre_door + [dict(rule='A외곽-개구부추정' if b.get('kind') != 'door_elev' else 'A승강기문-추정', id=b['zone'], width=b['width'],
                                      note='문 기호 없는 외곽 틈을 출입구로 보고 닫음' if b.get('kind') != 'door_elev' else '승강기 옆 틈 = 승강장 문으로 닫음') for b in env_bridges]
    lab2 = lab.copy(); lab2[outside] = -1

    def region_at(x, y):
        u, v = T(x, y)
        if not (0 <= v < Hd and 0 <= u < Wd): return 'out'
        l = lab2[v, u]
        if l == -1: return 'out'
        return f'R{rid_of[l]}' if l in rid_of else None

    door_rooms = collections.defaultdict(set)
    for o in openings:
        g = o['_geom']
        c = g.centroid
        mrr = g.minimum_rotated_rectangle
        xy = np.array(mrr.exterior.coords[:4])
        e1, e2 = xy[1] - xy[0], xy[2] - xy[1]
        nrm = e1 if np.hypot(*e1) < np.hypot(*e2) else e2   # 짧은 변 = 벽 두께 방향
        nrm = nrm / (np.hypot(*nrm) + 1e-9)
        half = np.hypot(*(e1 if np.hypot(*e1) < np.hypot(*e2) else e2)) / 2
        zl = [L_ for L_ in leaves if L_.get('zone') == o['id']]
        if zl:   # 문짝 기준: 닫힌 선의 법선, 닫힌 선 중점에서 탐색
            L_ = zl[0]; v_ = (L_['closed'] - L_['hinge']); v_ = v_ / (np.hypot(*v_) + 1e-9)
            nrm = np.array([-v_[1], v_[0]]); mid_ = (L_['hinge'] + L_['closed']) / 2
            c = Point(*mid_); half = 0
        sides = []
        for sgn in (1, -1):
            got = None
            for d in range(150, 900, 50):
                got = region_at(c.x + sgn * nrm[0] * (half + d), c.y + sgn * nrm[1] * (half + d))
                if got: break
            sides.append(got)
        if zl:   # 문이 열리는 쪽 실(연기·피난 방향 판단용)
            L_ = zl[0]; ov = L_['open'] - L_['hinge']
            o['swing_into'] = sides[0] if ov @ nrm > 0 else sides[1]
        o['sides'] = sides
        if o['kind'] in ('door', 'door_sliding', 'door_internal', 'door_elev'):
            zb = zid.get(o['id'], {}).get('block', '') or ''
            main_ = ('out' in sides) or bool(re.search(r'자동|ENT|현관|MAIN', zb, re.I))
            o['door_h'] = (STD_DOOR_H_MAIN if main_ else STD_DOOR_H) / 1000   # 표준 문 높이(m)
        for sd in sides:
            if sd and sd != 'out': door_rooms[sd].add(o['id'])
        if o['kind'] == 'door' and sides[0] == sides[1] and sides[0] not in (None, 'out') and zl and \
           all(near_any(ptree, pl_, L_['hinge'], 150) and not near_any(wtree, wl, L_['hinge'], 150) for L_ in zl):
            # 근거: 경첩이 벽 레이어가 아닌 칸막이 선(인테리어 등)에 붙음 = 벽으로 안 쓴 칸막이 안의 문
            # 칸막이는 실로 나누지 않음(욕실·화장실은 감지기 제외 장소). 벽에 붙은 문인데 양쪽 같음 = 분할 실패(오류 유지)
            o['kind'] = 'door_internal'
            checks.append(dict(rule='A문-실내부', id=o['id'], room=sides[0], note='경첩이 벽이 아닌 칸막이 선에 붙은 문(욕실·드레스룸 추정) — 실 분할 안 함, 문짝만 유지'))
        elif o['kind'] == 'door' and sides[0] == sides[1] and sides[0] not in (None, 'out') and zl and all(L_['r_std'] is None for L_ in zl):
            # 공간을 가르지 않고 표준 문 폭도 아닌 여닫이 기호 = 붙박이장·가구 문 후보 → 개구부·문짝에서 제외(표시만)
            o['kind'] = 'gap_closed'
            checks.append(dict(rule='A문-가구문후보', id=o['id'], room=sides[0], r=[round(L_['r']) for L_ in zl],
                               note='실을 가르지 않는 비표준 폭 호 → 수납장·가구 문 후보(문에서 제외)'))
        elif o['kind'] == 'door_elev' and not (sides[0] and sides[1] and 'out' not in sides and sides[0] != sides[1]):
            o['kind'] = 'gap_closed'   # 승강기 옆 틈이지만 실과 실 사이가 아님(승강로 공동·외곽) → 개구부 아님, 닫힌 선만 유지
        elif o['kind'] in ('door', 'door_elev') and (sides[0] == sides[1] or None in sides):
            checks.append(dict(rule='A문-양쪽분리', id=o['id'], sides=sides, note='문 양쪽이 같은 영역(또는 미확인) — 실 분리 실패 가능'))
        if o['kind'] == 'window':
            gm = o['_geom'].minimum_rotated_rectangle
            if gm.geom_type == 'Polygon':
                xy_ = np.array(gm.exterior.coords[:4]); span = max(math.dist(xy_[0], xy_[1]), math.dist(xy_[1], xy_[2]))
            else: span = o['_geom'].length
            o['span'] = round(span / 1000, 2)
            if basement and 'out' in sides:
                # 공리: 지하층에는 외기에 면한 창이 없음 → 드라이에어리어·환기구·채광정 후보(3D는 벽으로)
                o['kind'] = 'vent'
                checks.append(dict(rule='A지하-외기창없음', id=o['id'], sides=sides, note='지하층 외곽의 창호 기호 → 환기구·드라이에어리어 후보(창 아님)'))
            elif 'out' not in sides and sides[0] and sides[1] and sides[0] != sides[1]:
                o['kind'] = 'window_inner'
                if 600 <= span <= 2600:
                    o['candidate_kind'] = 'door_sliding'
                    checks.append(dict(rule='A실내창-문종류확인', id=o['id'], sides=sides, span=o['span'],
                                       note='실내창 유지. 폭만으로 미닫이문으로 확정하지 않음 — 창호 표기·소방도면 확인 필요'))
            elif 'out' not in sides:
                o['kind'] = 'window_inner'
                checks.append(dict(rule='A창-외기안닿음', id=o['id'], sides=sides, note='창 한쪽이 외부가 아님 → 실내창 처리(확인 필요)'))
    room_ids_known = {r['id'] for r in rooms}
    for o in openings:
        if o['kind'] == 'gap_closed': continue
        o['connection_status'] = connection_status(o, room_ids_known)
        if o['connection_status'] in ('unresolved', 'same_space'):
            checks.append(dict(rule='A개구부-연결확인', id=o['id'], sides=o['sides'],
                               note='연결 상대 미확정 또는 양쪽 동일 공간 — 외기로 자동 간주하지 않음'))
    checks.extend(jamb_checks)
    for r in rooms:
        if r['id'] not in door_rooms and 'elev' not in r['tags'] and 'stair' not in r['tags']:
            checks.append(dict(rule='A실-출입', id=r['id'], area=r['area'], note='연결된 문·창 미검출(문 미검출 ≠ 실 없음)'))
        if r['area'] < 1.0:
            checks.append(dict(rule='A실-소형', id=r['id'], area=r['area'], note='1㎡ 미만 — 샤프트(PS/AV) 후보'))
    # 외곽 폐합: 바깥이 하나의 연결 영역이고 내부로 새지 않았는지 — 바깥 면적이 비정상적으로 큰 실과 붙었는지는 실 수로 간접 판단
    nout, _ = cv2.connectedComponents(outside.astype(np.uint8), connectivity=4)
    if nout - 1 != 1:
        checks.append(dict(rule='A1-외부단일', n=nout - 1, note='외부 영역이 여러 개'))
    # 벽 두께 분포
    wdt = cv2.distanceTransform((wallbody > 0).astype(np.uint8), cv2.DIST_L2, 3)
    thick = np.percentile(wdt[wdt > 0] * 2 * R, [50, 90]).round().tolist() if (wdt > 0).any() else None

    # ---- 벽 다각형 ----
    def polys_of(mask, eps=0.8):
        cs, hi = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        out = []
        if hi is None: return out
        for i, c in enumerate(cs):
            if hi[0][i][3] != -1 or cv2.contourArea(c) < 3: continue
            c = cv2.approxPolyDP(c, eps, True)
            holes = []; j = hi[0][i][2]
            while j != -1:
                h = cv2.approxPolyDP(cs[j], eps, True)
                if cv2.contourArea(h) > 3:
                    holes.append([[round(Ti(u, v)[0] / 1000, 3), round(Ti(u, v)[1] / 1000, 3)] for u, v in h[:, 0]])
                j = hi[0][j][0]
            out.append(dict(o=[[round(Ti(u, v)[0] / 1000, 3), round(Ti(u, v)[1] / 1000, 3)] for u, v in c[:, 0]], h=holes))
        return out
    walls = polys_of(wallbody)
    footprint = polys_of(foot)

    # 기둥 중심(층 정렬용): 기둥 요소를 붙어 있는 것끼리 묶어 외접 사각형 중심
    cols = []
    it = []
    for p, c in zip(prims, cats):
        if c != 'column': continue
        q = np.array(mm(p.pts))
        bb = box(*q.min(0), *q.max(0))
        if reg.intersects(bb): it.append((bb, p))
    for g in cluster_boxes(it, 5):
        bb = unary_union([it[i][0] for i in g]).envelope
        if 2e3 < bb.area < 2.5e6: cols.append([round(bb.centroid.x / 1000, 3), round(bb.centroid.y / 1000, 3)])

    # 코어(계단·승강기): 층 정렬·수직 공간 기준
    # 1순위 계단 = 계단 태그 실(계단실 전체), 승강기 = 이름이 승강기·ELEV·N인승인 블록(카) 범위
    cores = []
    for r in rooms:
        if 'stair' in r.get('tags', []) and r['area'] >= 3:
            q = np.array(r['poly']); b = (*q.min(0), *q.max(0))
            cores.append(dict(kind='stair', cx=round((b[0] + b[2]) / 2, 3), cy=round((b[1] + b[3]) / 2, 3), w=round(b[2] - b[0], 3), h=round(b[3] - b[1], 3), n=0, src='room'))
    EVN = re.compile(r'승강기|엘리베이터|ELEV|(?<!\d)\d+\s*인승|LIFT|E/V', re.I)
    ev_ins = collections.defaultdict(list)
    for p, c in inreg:
        iid = p.ins
        while iid is not None:
            nm_ = inserts[iid]['name'].split('$')[-1]
            if EVN.search(nm_) and not BIGN.search(nm_): ev_ins[iid].append(p); break
            iid = inserts[iid]['parent']
    for iid, ps in ev_ins.items():
        q = np.array([v for p in ps for v in mm(p.pts)]); b = (*q.min(0), *q.max(0))
        w, h = (b[2] - b[0]) / 1000, (b[3] - b[1]) / 1000
        if 0.8 <= min(w, h) and max(w, h) <= 4.5:
            cores.append(dict(kind='elev', cx=round((b[0] + b[2]) / 2000, 3), cy=round((b[1] + b[3]) / 2000, 3), w=round(w, 3), h=round(h, 3), n=len(ps), src='block'))
    have = {c['kind'] for c in cores}
    for kind, plist in (('stair', stairs), ('elev', elevs)):
        if kind in have: continue   # 2순위: 같은 종류 선 묶음 외접 사각형
        it = []
        for p in plist:
            q = np.array(mm(p.pts)); it.append((box(*q.min(0), *q.max(0)), p))
        for g in cluster_boxes(it, 300):
            bb = unary_union([it[i][0] for i in g]).envelope
            b = bb.bounds; w, h = (b[2] - b[0]) / 1000, (b[3] - b[1]) / 1000
            if 1.0 <= max(w, h) <= 20 and min(w, h) >= 0.8 and len(g) >= 3:
                cores.append(dict(kind=kind, cx=round(bb.centroid.x / 1000, 3), cy=round(bb.centroid.y / 1000, 3),
                                  w=round(w, 3), h=round(h, 3), n=len(g)))
    # 용도 단서: 도면 전체 문자에서 용도 낱말 빈도
    use_kw = dict(exhibit=r'견본|모델하우스|단지모형|홍보관|전시|세대입구|분양|미건립', factory=r'공장|작업장|생산', warehouse=r'창고(?!\s*\d)|물류|하역', parking=r'주차', apartment=r'세대|침실|거실|발코니|드레스룸',
                  office=r'사무|회의|업무', retail=r'판매|매장|근린|점포|상가', edu=r'교실|강의|교무', medical=r'병실|진료|수술', lodging=r'객실|숙박')
    alltx = []
    for e in texts(doc.modelspace()):
        try: alltx.append(e.dxf.text if e.dxftype() == 'TEXT' else e.plain_text())
        except Exception: pass
    big = ' '.join(alltx)
    use_hint = {k: len(re.findall(v, big)) for k, v in use_kw.items()}

    foot_d = cv2.dilate(foot, np.ones((int(500 / R) * 2 + 1,) * 2, np.uint8))
    def _inside(c):
        u, v = T(c.x, c.y)
        return bool(0 <= v < Hd and 0 <= u < Wd and foot_d[v, u] > 0)
    # Keep original CAD vectors separate from raster geometry and healed lines.
    source_vectors = []
    used_blocks=set()
    cross_door_indices={e['primitive_index'] for e in layer_evidence['accepted'] if e['to_category']=='door'}
    for index, (p, category) in enumerate(zip(prims,cats)):
        is_door = id(p) in aset or (category in ('window','other') and is_leaf(p))
        iid=p.ins
        while iid is not None:
            used_blocks.add(iid); iid=inserts[iid]['parent']
        source_vectors.append(dict(id=f'V{index}', category='door' if is_door else category,
            classification_rule='paired_face_supported_interval' if p.source.get('derived') else 'cross_layer_swing_leaf_boundary' if index in cross_door_indices else 'arc_leaf_geometry' if is_door else 'block_name' if lm.cat(p.layer)!=category else 'layer_map',
            entity=p.kind, layer=p.raw, source=p.source, closed=bool(p.closed), linetype=p.lt,
            excluded_from_boundary=bool(DASHED.search(p.lt)) or category not in ('wall','column','door','window'),
            excluded_by_auto=id(p) in auto_excluded,
            points=[[round(x*unit,6),round(y*unit,6)] for x,y in p.pts],
            arc=None if p.arc is None else [p.arc[0]*unit,p.arc[1]*unit,p.arc[2]*unit,p.arc[3],p.arc[4]]))
    res = dict(src=Path(fn).name, unit_m=unit, res_m=res_m, cores=cores, use_hint=use_hint, beams=beams,
               source_vectors=source_vectors, source_blocks=[inserts[i] for i in sorted(used_blocks)], cad_diagnostics=cad_diagnostics,source_review=source_review,
               layer_evidence=layer_evidence,
               geometry_precision=dict(source_lines='CAD WCS coordinates rounded to 1 micrometre',
                   curves='tessellated; circular door arcs additionally retained analytically',
                   room_wall_polygons='raster-derived', raster_resolution_m=res_m),
               provenance=dict(pipeline='cad-plan-connectivity-20261014-v4',
                               source_sha256=hashlib.sha256(Path(fn).read_bytes()).hexdigest(),
                               map_sha256=hashlib.sha256(Path(mapfn).read_bytes()).hexdigest(),
                               code_sha256={name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                                            for name in ('cad_plan.py', 'cad_heal.py', 'cad_topology.py', 'cad_evidence.py', 'cad_auto.py', 'cadio.py','cad_door_rules.py','cad_review_rules.py','cad_layers.py','cad_swing.py')},
                               tolerances_mm=H.p),
               raster=dict(x0=x0, y1=y1, R=R, W=Wd, H=Hd),
               rooms=rooms, walls=walls, footprint=footprint,
               door_zones=[dict(id=z['id'], bbox=[round(v / 1000, 3) for v in z['tight'].bounds], r=None if not z['r'] else round(z['r']), leaves=sum(L_.get('zone') == z['id'] for L_ in leaves),
                                bridged=z['id'] in {b['zone'] for b in bridges}, opened=z['id'] in {o['id'] for o in openings}, inside=_inside(z['tight'].centroid)) for z in zones if z['kind'] == 'door'],
               openings=[{k: v for k, v in o.items() if not k.startswith('_')} for o in openings if o['kind'] != 'gap_closed'],
               columns=cols, checks=checks,
               heal=dict(summary=H.summary(), flags=H.flags, log=H.log),
               stats=dict(rooms=len(rooms), doors_zone=nd, doors_open=sum(o['kind'] == 'door' for o in openings), doors_elev=sum(o['kind'] == 'door_elev' for o in openings), gaps_closed=sum(o['kind'] == 'gap_closed' for o in openings), doors_internal=sum(o['kind'] == 'door_internal' for o in openings), sliding=sum(o['kind'] == 'door_sliding' for o in openings),
                          windows=sum(o['kind'] == 'window' for o in openings), windows_inner=sum(o['kind'] == 'window_inner' for o in openings),
                          vents=sum(o['kind'] == 'vent' for o in openings), leaves=len(leaves), leaves_std=sum(L_['r_std'] is not None for L_ in leaves),
                          jamb_dropped=dropped_jamb, wall_thick_mm_p50_p90=thick),
               layers=sorted([[l, c, n] for (l, c), n in layer_tab.items()], key=lambda x: (x[1], -x[2])))
    from cad_evidence import normalize_plan
    res = normalize_plan(res)
    json.dump(res, open(out + '.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0, default=list)

    # ---- 그림: 실(색)·벽(검정)·문(초록)·창(파랑)·자동보정(주황 점)·애매한 틈(빨강 원) ----
    vis = np.full((Hd, Wd, 3), 255, np.uint8)
    rng = np.random.default_rng(7)
    for i in room_ids: vis[lab == i] = rng.integers(170, 245, 3)
    vis[wallbody > 0] = (60, 60, 60)
    for o in openings:
        vis[o['_mask'] > 0] = {'door': (0, 170, 0), 'door_sliding': (180, 200, 0), 'door_elev': (120, 170, 0), 'door_internal': (150, 230, 150), 'window_inner': (230, 180, 120), 'vent': (120, 120, 200)}.get(o['kind'], (255, 140, 0))
    # 문짝: 평면도 관례 — 닫힌 문짝(경첩→닫힌 위치, 굵은 선) + 열림 호(닫힌 위치→열린 위치, 도면 호 방향 그대로). 기본 = 닫힘
    from cad_swing import swing_points
    for L_ in leaves:
        if not L_.get('zone') or L_['zone'] not in {o['id'] for o in openings if o['kind'] in ('door', 'door_internal')}: continue
        cv2.polylines(vis, [np.int32([T(*q) for q in swing_points(L_)])], False, (0, 120, 0), 1, cv2.LINE_AA)
        cv2.line(vis, T(*L_['hinge']), T(*L_['closed']), (0, 90, 0), 3)
        cv2.circle(vis, T(*L_['hinge']), 3, (0, 60, 0), -1)
    for b in bridges:
        s = b['seg']; cv2.line(vis, T(s[0], s[1]), T(s[2], s[3]), (0, 120, 0), 1)
    for l in H.log:
        if l['op'] in ('extend', 'trim', 'close', 't_join', 'snap') and l.get('dist', 0) > 0.5:
            cv2.circle(vis, T(*l['at']), 3, (0, 140, 255), -1)
    for f in H.flags:
        cv2.circle(vis, T(*f['at']), 9, (0, 0, 255), 2)
        if 'to' in f: cv2.line(vis, T(*f['at']), T(*f['to']), (0, 0, 255), 1)
    for c in checks:
        if c['rule'].startswith('A문'):
            o = next((o for o in openings if o['id'] == c.get('id')), None)
            if o is None: continue
            cc = o['_geom'].centroid
            if c['rule'] == 'A문-문틀지지미확인':
                cv2.drawMarker(vis, T(cc.x, cc.y), (180, 60, 150), cv2.MARKER_SQUARE, 16, 2)
            else:
                cv2.drawMarker(vis, T(cc.x, cc.y), (255, 0, 255), cv2.MARKER_TILTED_CROSS, 22, 3)
    for bq in beams:   # 상부 보: 갈색 테두리(공간은 안 가름). 바닥 밖 띠는 3D에서 제외
        if not foot[min(max(T(*(np.mean(bq, 0) * 1000))[1], 0), Hd - 1), min(max(T(*(np.mean(bq, 0) * 1000))[0], 0), Wd - 1)]: continue
        cv2.polylines(vis, [np.int32([T(x * 1000, y * 1000) for x, y in bq])], True, (43, 90, 139), 2)
    for r in rooms:
        u, v = T(r['center'][0] * 1000, r['center'][1] * 1000)
        cv2.putText(vis, r['id'], (u - 12, v + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
    cv2.imencode('.png', vis)[1].tofile(out + '_plan.png')
    return res


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('dxf'); ap.add_argument('out')
    ap.add_argument('--map', default=str(Path(__file__).with_name('layer_map.json')))
    ap.add_argument('--floor', help='층 이름(예: 4F, B1). 지하층 창호 분류에 사용')
    ap.add_argument('--res', type=float, default=0.02)
    a = ap.parse_args()
    r = run(a.dxf, a.out, a.map, a.res, floor=a.floor)
    print(json.dumps(dict(stats=r['stats'], heal=r['heal']['summary'],
                          checks=dict(collections.Counter(c['rule'] for c in r['checks']))), ensure_ascii=False))
