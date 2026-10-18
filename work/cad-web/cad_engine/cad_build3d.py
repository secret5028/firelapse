"""층별 평면 JSON → 층 정렬 → 3D(벽 압출, 문·창 구멍) → building.json + 뷰어 HTML.
python cad_build3d.py <출력접두어> F1.json F2.json ... [--elev 입면.dxf] [--levels 1.0,7.5,15.0]
  --levels: 각 층 바닥 높이(m) + 마지막에 지붕 높이. 없으면 입면도 문자(+7,500 / 2nd FLOOR)에서 읽고, 그것도 없으면 3.5m 간격.
기본 개구부 치수(조정 가능): 문 높이 2.1, 창대 0.9, 창 머리 2.2"""
import sys, json, re, math, argparse, collections
import numpy as np
from shapely.geometry import Polygon, MultiPolygon, Point
from shapely.ops import unary_union

DOOR_H, SILL, HEAD = 2.1, 0.9, 2.2


def P(o, h=()):
    g = Polygon(o, [x for x in h if len(x) >= 3])
    return g if g.is_valid else g.buffer(0)


def to_list(g, dx, dy, min_area=0.002):
    out = []
    geoms = [g] if g.geom_type == 'Polygon' else list(getattr(g, 'geoms', []))
    for p in geoms:
        if p.geom_type != 'Polygon' or p.area < min_area: continue
        p = p.simplify(0.005)
        if p.is_empty or p.geom_type != 'Polygon': continue
        out.append(dict(o=[[round(x - dx, 3), round(y - dy, 3)] for x, y in p.exterior.coords[:-1]],
                        h=[[[round(x - dx, 3), round(y - dy, 3)] for x, y in r.coords[:-1]] for r in p.interiors if Polygon(r).area > min_area]))
    return out


def levels_from_elev(fn):
    import ezdxf
    d = ezdxf.readfile(fn)
    fl, lv = [], []
    for e in d.modelspace().query('TEXT MTEXT'):
        t = (e.dxf.text if e.dxftype() == 'TEXT' else e.plain_text()).strip()
        y = e.dxf.insert.y
        m = (re.match(r'^(\d+)\s*(st|nd|rd|th)\s*FLOOR', t, re.I) or re.match(r'^(\d+)\s*층', t)
             or re.match(r'^(\d+)\s*FL?$', t, re.I) or re.match(r'^(\d+)\s*F\s*F?L', t, re.I))
        if m: fl.append((int(m.group(1)), y))
        elif re.match(r'^(PH|RF|ROOF|옥탑|지붕)', t, re.I): fl.append((t.upper(), y))
        m = re.match(r'^(?:EL\.?\s*)?([+-])\s*([\d,. ]+)$', t)
        if m:
            try: lv.append((float(re.sub(r'[,. ]', '', m.group(2))) * (1 if m.group(1) == '+' else -1) / 1000, y))
            except ValueError: pass
    floors = {}
    for n, y in fl:
        c = min(lv, key=lambda v: abs(v[1] - y)) if lv else None
        if c and abs(c[1] - y) < 1500: floors[n] = c[0]
    nums = {k: v for k, v in floors.items() if isinstance(k, int)}
    extra = {k: v for k, v in floors.items() if not isinstance(k, int)}
    floors = nums
    vals = sorted(v for v, _ in lv)
    top = None
    if extra:
        cand = [v for v in extra.values() if not floors or v > max(floors.values())]
        if cand: top = min(cand)   # 옥탑/지붕 바닥 = 최상층 천장
    elif floors and vals:
        above = [v for v in vals if v > max(floors.values()) + 2.0]
        if above:
            top = above[-1]
            if len(above) > 1 and above[-1] - above[-2] <= 1.5: top = above[-2]   # 난간(파라펫) 제외
    floors['_extra'] = sorted(extra.values())   # 옥탑·옥탑지붕 등 숫자 아닌 층 높이들
    return floors, top


def align(base_cols, cols):
    if len(base_cols) < 3 or len(cols) < 3: return (0.0, 0.0), 'none'
    A, B = np.array(base_cols), np.array(cols)
    D = (A[None, :, :] - B[:, None, :]).reshape(-1, 2)
    k = collections.Counter(map(tuple, np.round(D / 0.05).astype(int)))
    (kx, ky), cnt = k.most_common(1)[0]
    m = D[np.hypot(D[:, 0] - kx * 0.05, D[:, 1] - ky * 0.05) < 0.08]
    t = m.mean(0)
    return (float(t[0]), float(t[1])), f'columns {cnt}/{min(len(A), len(B))}'


def align_xcorr(A, B, res=0.1):
    """기둥 대응 부족 시: 벽 그림 위상상관(phaseCorrelate)으로 평행이동 추정"""
    import cv2
    def bounds(f):
        xs = [x for w in f['walls'] for x, y in w['o']]; ys = [y for w in f['walls'] for x, y in w['o']]
        return min(xs), min(ys), max(xs), max(ys)
    ba, bb = bounds(A), bounds(B)
    W = int(max(ba[2] - ba[0], bb[2] - bb[0]) / res) + 200; H = int(max(ba[3] - ba[1], bb[3] - bb[1]) / res) + 200
    def ras(f, b):
        im = np.zeros((H, W), np.float32)
        for w in f['walls']:
            q = np.int32([[(x - b[0]) / res + 100, (y - b[1]) / res + 100] for x, y in w['o']])
            cv2.fillPoly(im, [q], 1.0)
        return cv2.GaussianBlur(im, (0, 0), 3)
    ia, ib = ras(A, ba), ras(B, bb)
    (dx, dy), resp = cv2.phaseCorrelate(ib, ia, np.outer(np.hanning(H), np.hanning(W)).astype(np.float32))
    t = (ba[0] - bb[0] + dx * res, ba[1] - bb[1] + dy * res)
    return (float(t[0]), float(t[1])), f'walls-xcorr r={resp:.2f}'


def align_cores(A, B, colsA=(), colsB=()):
    """계단·승강기 코어로 가설-검증 정렬.
    가설: 같은 종류 코어 쌍의 중심/왼·오른 모서리/위·아래 모서리 맞춤 조합(최상층 계단처럼 한쪽만 짧아져도 됨).
    검증 점수: 일치하는 코어 모서리 수(0.15m) + 일치 기둥 수×0.5(0.3m). 축척은 일치 코어 크기비로 확인만."""
    if not A or not B: return None
    E = lambda c: (c['cx'] - c['w'] / 2, c['cx'] + c['w'] / 2, c['cy'] - c['h'] / 2, c['cy'] + c['h'] / 2)
    EA = [(c['kind'], E(c)) for c in A]; EB = [(c['kind'], E(c)) for c in B]
    CA = np.array(colsA) if len(colsA) else np.zeros((0, 2)); CB = np.array(colsB) if len(colsB) else np.zeros((0, 2))
    cands = set()
    for ka, ea in EA:
        for kb, eb in EB:
            if ka != kb: continue
            dxs = {(ea[0] + ea[1] - eb[0] - eb[1]) / 2, ea[0] - eb[0], ea[1] - eb[1]}
            dys = {(ea[2] + ea[3] - eb[2] - eb[3]) / 2, ea[2] - eb[2], ea[3] - eb[3]}
            for dx in dxs:
                for dy in dys: cands.add((round(dx, 2), round(dy, 2)))
    def score(t):
        se, full = 0, 0
        for kb, eb in EB:
            e2 = (eb[0] + t[0], eb[1] + t[0], eb[2] + t[1], eb[3] + t[1])
            best = 0
            for ka, ea in EA:
                if ka != kb: continue
                best = max(best, sum(abs(p - q) < 0.15 for p, q in zip(ea, e2)))
            se += best; full += best == 4
        sc_ = 0
        if len(CA) and len(CB):
            d = np.hypot(*(CA[None, :, :] - (CB + t)[:, None, :]).transpose(2, 0, 1)).min(1)
            sc_ = int((d < 0.3).sum())
        return se + 0.5 * sc_, se, full, sc_
    best = max(cands, key=lambda t: score(t)[0])
    tot, se, full, nc = score(best)
    if not (se >= 6 or (se >= 4 and nc >= 2) or (se >= 2 and nc >= 2)): return None
    # 미세 보정: 일치 기둥 중앙값
    t = np.array(best, float)
    if nc >= 3:
        d = CA[None, :, :] - (CB + t)[:, None, :]
        dist = np.hypot(d[..., 0], d[..., 1]); jj = dist.argmin(1); ok = dist.min(1) < 0.3
        t = t + np.median(d[np.arange(len(CB))[ok], jj[ok]], 0)
    # Two core edges plus two independent column locations constrain a
    # clipped top-floor stair. Do not discard this already-accepted match.
    weak = ''
    return (float(t[0]), float(t[1])), 1.0, f'cores edges {se} (full {full}) + columns {nc}{weak}'


def pick_use(F, names, force=None):
    """건물 주용도(층별): 문자 빈도. B층 주차 우세 → parking, PH → penthouse"""
    if force: return [force] * len(F)
    tot = collections.Counter()
    for f in F:
        for k, v in f.get('use_hint', {}).items():
            if k != 'parking': tot[k] += v
    main = tot.most_common(1)[0][0] if tot and tot.most_common(1)[0][1] > 0 else 'default'
    # 층별 적응: 실 이름(실 안 문자)이 가장 강한 근거. 없으면 건물 전체 문자 빈도
    RN = [('lodging', r'객실|게스트룸|GUEST\s*ROOM|숙박'), ('retail', r'근린|음식점|판매|매장|카페|상가|로\s*비|프론트|LOBBY'),
          ('parking', r'주차|기계식|PARKING'), ('office', r'사무|업무|회의'), ('apartment', r'침실|거실|세대|드레스'),
          ('medical', r'병실|진료|수술'), ('edu', r'교실|강의'), ('factory', r'공장|작업장|생산'), ('warehouse', r'창고|물류')]
    out = []
    for f, n in zip(F, names):
        h = f.get('use_hint', {})
        rn = [x for r in f.get('rooms', []) for x in r.get('names', [])]
        sc = collections.Counter({u: sum(bool(re.search(p, x, re.I)) for x in rn) for u, p in RN})
        best = sc.most_common(1)[0] if sc else (None, 0)
        if n == 'PH': out.append('penthouse')
        elif n.startswith('B') and any(re.search(r'주차|PARKING',' '.join(r.get('names',[])),re.I) and r['area']>=.5*sum(q['area'] for q in f['rooms']) for r in f['rooms']): out.append('parking')
        elif best[1] >= 1: out.append(best[0])
        elif n.startswith('B') and h.get('parking', 0) == 0: out.append('default')   # 지하인데 근거 없음 → 일반 기본값(주용도 전파 안 함)
        elif n.startswith('B') and h.get('parking', 0) >= max([v for k, v in h.items() if k != 'parking'] + [1]): out.append('parking')
        else: out.append(main)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out'); ap.add_argument('floors', nargs='+')
    ap.add_argument('--elev'); ap.add_argument('--levels', help='도면 층 높이(공장·창고 또는 --heights drawing 일 때 사용)')
    ap.add_argument('--names'); ap.add_argument('--use', help='용도 강제: office/apartment/retail/factory/warehouse…')
    ap.add_argument('--heights', choices=['auto', 'std', 'drawing'], default='auto')
    a = ap.parse_args()
    F = [json.load(open(f, encoding='utf-8')) for f in a.floors]
    from cad_core_contract import normalize_cores
    F = [normalize_cores(f) for f in F]
    names = a.names.split(',') if a.names else [f'{i + 1}F' for i in range(len(F))]
    from pathlib import Path
    STD = json.loads(Path(__file__).with_name('standard_heights.json').read_text(encoding='utf-8'))
    uses = pick_use(F, names, a.use)
    main_use = collections.Counter(u for u in uses if u not in ('parking', 'penthouse')).most_common(1)
    main_use = main_use[0][0] if main_use else uses[0]
    Ld = None
    if a.levels: Ld = [float(x) for x in a.levels.split(',')]   # 'nan' = 도면에 없음
    elif a.elev:
        fl, top = levels_from_elev(a.elev)
        keys = [int(re.sub(r'\D', '', n) or 0) for n in names]
        if all(k in fl for k in keys): Ld = [fl[k] for k in keys] + [fl.get(keys[-1] + 1) or top or fl[keys[-1]] + 3.5]
    spec = [STD.get(u, STD['default']) for u in uses]
    # 층 높이: 도면에 있으면 도면값(용도 무관), 없는 층만 용도별 기본 층고로 채움. --heights std 면 전부 기본값
    n_ = len(F)
    if Ld and a.heights != 'std':
        L = [float(v) for v in Ld] + [float('nan')] * max(0, n_ + 1 - len(Ld))
        L = L[:n_ + 1]
    else:
        L = [float('nan')] * (n_ + 1)
    known = [i for i, v in enumerate(L) if v == v]
    filled = []
    if not known:
        gi = next((i for i, n in enumerate(names) if not n.startswith('B')), 0); L[gi] = 0.0; known = [gi]; filled.append(names[gi])
    k0 = known[0]
    for i in range(k0 - 1, -1, -1):
        if L[i] != L[i]: L[i] = L[i + 1] - spec[i]['floor_h']; filled.append(names[i])
    for i in range(k0 + 1, n_ + 1):
        if L[i] != L[i]:
            L[i] = L[i - 1] + spec[i - 1]['floor_h']; filled.append(names[i] if i < n_ else '지붕')
    lev_src = ('도면 층 높이' if Ld and a.heights != 'std' else '기본 층고') + \
              (f' + 기본값 채움({", ".join(filled)}; 용도 ' + ', '.join(f"{n} {u}" for n, u in zip(names, uses)) + ')' if filled else '')
    base = L[0]
    # ---- 정렬: 계단·승강기 → 기둥 → 벽 상관 ----
    bi = next((i for i, n in enumerate(names) if n == '1F'), max(range(len(F)), key=lambda i: len(F[i].get('cores', []))))
    def rel_align(A, Bf):
        """Bf 를 A 에 맞추는 (t, s, how). 코어 → 기둥 미세보정 → 기둥 → 벽 상관"""
        r = align_cores(A.get('cores', []), Bf.get('cores', []), A['columns'], Bf['columns'])
        if r: return r
        return (0.,0.), 1., 'unconfirmed_core_alignment'
    # 기준층에서 위·아래로 이웃층 순서대로 맞춤(위아래 층 코어가 가장 비슷)
    shifts = [None] * len(F); shifts[bi] = ((0.0, 0.0), 1.0, 'base')
    for rng in (range(bi + 1, len(F)), range(bi - 1, -1, -1)):
        for i in rng:
            j = i - 1 if i > bi else i + 1
            (tn, sn, _) = shifts[j]
            t, sc, how = rel_align(F[j], F[i])
            if 'unconfirmed' in how:   # Neighbour symbols may be clipped; try other aligned floors.
                alternatives=[]
                for k,known in enumerate(shifts):
                    if known is None or 'unconfirmed' in known[2]:continue
                    t2,sc2,how2=rel_align(F[k],F[i])
                    if 'unconfirmed' not in how2:
                        alternatives.append((abs(k-i),k,t2,sc2,how2))
                if alternatives:
                    _,k,t2,sc2,how2=min(alternatives)
                    tk,sk,_=shifts[k]
                    shifts[i]=((sk*t2[0]+tk[0],sk*t2[1]+tk[1]),sk*sc2,how2+f' (core reference {names[k]})');continue
            shifts[i] = ((sn * t[0] + tn[0], sn * t[1] + tn[1]), sn * sc, how + f' (←{names[j]})')
    # 기둥 식별: 정렬 후 여러 층에서 같은 자리(0.3m)에 있는 기둥 = 관통 기둥
    world = [np.array(f['columns']) * sc + np.array(t) if len(f['columns']) else np.zeros((0, 2)) for f, (t, sc, _) in zip(F, shifts)]
    col_info = []
    for i, Wc in enumerate(world):
        cnt = []
        for c in Wc:
            k = sum(1 for j, Wj in enumerate(world) if j != i and len(Wj) and np.hypot(*(Wj - c).T).min() < 0.3)
            cnt.append(k)
        col_info.append(cnt)
    # 공통 원점
    allx, ally = [], []
    for f, (t, sc, _) in zip(F, shifts):
        for w in f['footprint']:
            for x, y in w['o']: allx.append(sc * x + t[0]); ally.append(sc * y + t[1])
    ox, oy = min(allx), min(ally)
    core_all = []; dropped_parts = []
    B = dict(levels=L, levels_src=lev_src, use=main_use, origin=[round(ox, 4), round(oy, 4)], floors=[])
    from shapely import affinity
    for i, f in enumerate(F):
        (tx, ty), sc, how = shifts[i]
        dx, dy = ox - tx, oy - ty
        z, H = L[i] - base, L[i + 1] - L[i]
        sp = spec[i]
        # 반자 기본: 천장 마감 있음(용도 기본) → max(바닥 기준 하한, 층고 - 천장 속 깊이), 층고-0.3 이하
        if sp.get('ceiling') and sp.get('plenum') is not None:
            ch = round(min(max(sp['min_h'], H - sp['plenum']), H - 0.3), 2)
        else:
            ch = None
        ch_rule = dict(ceiling=bool(sp.get('ceiling')), min_h=sp.get('min_h'), plenum=sp.get('plenum'))
        def P(o, h=(), _sc=sc):
            if len(o) < 3: return Polygon()
            g = Polygon(o, [x for x in h if len(x) >= 3])
            g = g if g.is_valid else g.buffer(0)
            return affinity.scale(g, _sc, _sc, origin=(0, 0)) if _sc != 1 else g
        W = unary_union([P(w['o'], w['h']) for w in f['walls']])
        foot = unary_union([P(w['o'], w['h']) for w in f['footprint']])
        # 같은 시트의 다른 도면(옥탑·지붕 나란히, 상세도 등) 제거: 계단·승강기 코어를 품은 바닥 덩어리 + 3m 안에 붙은 덩어리만 이 층
        KEEP = None
        cps = [Point(sc * c_['cx'], sc * c_['cy']) for c_ in f.get('cores', [])]
        comps = [g_ for g_ in getattr(foot, 'geoms', [foot]) if not g_.is_empty]
        if cps and len(comps) > 1:
            # A detached, already accepted room is not an inset merely because
            # it lacks a stair/elevator. Keep the 2D/3D compartment set aligned.
            room_points=[Point(sc*r['center'][0],sc*r['center'][1]) for r in f['rooms']]
            keep = [g_ for g_ in comps if any(g_.buffer(1.0).contains(p_) for p_ in cps)
                    or any(g_.covers(p_) for p_ in room_points)]
            if keep:
                grown = True
                while grown:
                    grown = False; ku = unary_union(keep).buffer(3.0)
                    for g_ in comps:
                        if not any(g_ is k_ for k_ in keep) and g_.intersects(ku): keep.append(g_); grown = True
                KEEP = unary_union(keep).buffer(0.5)
                drop = sum(g_.area for g_ in comps) - sum(g_.area for g_ in keep)
                if drop > 1: dropped_parts.append(dict(floor=names[i], area=round(drop, 1)))
                W = W.intersection(KEEP); foot = foot.intersection(KEEP)
        inK = lambda g_: KEEP is None or KEEP.contains(g_.representative_point())
        op = collections.defaultdict(list)
        from cad_evidence import opening_parts
        f['openings'] = [o for o in f['openings'] if any(len(p['o']) >= 3 and inK(P(p['o'],p['h'])) for p in opening_parts(o))]
        for o in f['openings']:
            for p in opening_parts(o):
                if len(p['o']) >= 3: op[o['kind']].append(P(p['o'],p['h']))
        dk = op['door'] + op['door_sliding'] + op['door_elev'] + op['door_internal']
        Od = unary_union(dk) if dk else Polygon()
        # 문 높이별(표준 2.1m / 외부 출입문 2.4m) 문 위 벽 띠
        byh = collections.defaultdict(list)
        for o in f['openings']:
            if o['kind'] in ('door', 'door_sliding', 'door_elev', 'door_internal'):
                for p in opening_parts(o):
                    if len(p['o']) >= 3: byh[round(o.get('door_h') or sp['door_h'], 2)].append(P(p['o'],p['h']))
        wk = op['window'] + op['window_inner']          # vent(지하 외곽 창호 기호)는 구멍 없이 벽으로
        Ow = unary_union(wk) if wk else Polygon()
        Ow = Ow.difference(Od)
        solid = W.difference(Od).difference(Ow)
        top = ch if ch else H - 0.2
        dh = min(sp['door_h'], top); s0 = min(sp['sill'], H * 0.3); hd = min(sp['head'], top)
        bands = [dict(kind='wall', z0=0, z1=H, polys=to_list(solid, dx, dy)),
                 *[dict(kind='door_head', z0=min(h_, top), z1=H, polys=to_list(W.intersection(unary_union(g_)), dx, dy)) for h_, g_ in sorted(byh.items())],
                 dict(kind='win_low', z0=0, z1=s0, polys=to_list(W.intersection(Ow), dx, dy)),
                 dict(kind='win_head', z0=hd, z1=H, polys=to_list(W.intersection(Ow), dx, dy))]
        glass = dict(z0=s0, z1=hd, polys=to_list(W.intersection(Ow), dx, dy))
        ceil = to_list(foot.difference(W), dx, dy)
        bd = sp.get('beam_d', 0.6)
        # 보 후보 중 70% 이상이 실내(바닥판 안)인 것만: 바깥쪽 띠는 처마·캐노피·기초선
        bms = [P(q) for q in f.get('beams', []) if len(q) >= 3 and inK(P(q))]
        bms = [g_ for g_ in bms if g_.area > 0 and g_.intersection(foot).area / g_.area >= 0.7]
        BM = unary_union(bms) if bms else Polygon()
        # 보는 반자가 없거나(노출 구조) 반자보다 아래로 내려올 때만 실내 요소. 반자 위면 천장 속에 묻힘 → 기록만
        beam_state = 'none'
        if not BM.is_empty:
            bands.append(dict(kind='beam', z0=round(H - bd, 3), z1=H, polys=to_list(BM.difference(W), dx, dy)))
            beam_state = 'exposed' if (ch is None or H - bd < ch) else 'above_ceiling'
        cols_out = [dict(x=round(float(c[0]) - ox, 3), y=round(float(c[1]) - oy, 3), floors_shared=k) for c, k in zip(world[i], col_info[i])]
        lone = sum(1 for k in col_info[i] if k == 0)
        rooms = []
        for r in f['rooms']:
            parts = r.get('polys') or [dict(o=r['poly'], h=r.get('holes', []))]
            g = unary_union([P(part['o'], part.get('h', [])) for part in parts])
            if g.is_empty or not inK(g): continue
            rooms.append(dict(id=r['id'], area=round(g.area, 4), names=r.get('names', []), tags=r.get('tags', []),
                              fire_evidence=r.get('fire_evidence'), usage_candidate=r.get('usage_candidate'),
                              polys=to_list(g, dx, dy), c=[round(sc * r['center'][0] - dx, 2), round(sc * r['center'][1] - dy, 2)]))
        tp = lambda q: None if q is None else [round(sc * q[0] - dx, 3), round(sc * q[1] - dy, 3)]
        doors = [dict(id=o['id'], kind=o['kind'], sides=o.get('sides'), connection_status=o.get('connection_status'),
                      fire_evidence=o.get('fire_evidence'), kind_before_fire=o.get('kind_before_fire'), operation=o.get('operation'),
                      candidate_kind=o.get('candidate_kind'), swing_into=o.get('swing_into'), span=sc*o['span'] if o.get('span') else None, door_h=o.get('door_h'),
                      guessed=o.get('guessed',False), connection_evidence=o.get('connection_evidence'),
                      leaves=[dict(L, hinge=tp(L['hinge']), closed=tp(L['closed']), open=tp(L['open']), open2=tp(L.get('open2')),
                                   r=round(sc * L['r'], 3)) for L in o.get('leaves', [])],
                      geometry_polys=to_list(unary_union([P(p['o'],p['h']) for p in opening_parts(o)]),dx,dy),
                      polys=[[[round(sc * x - dx, 3), round(sc * y - dy, 3)] for x, y in p] for p in o['polys']]) for o in f['openings']]
        for c_ in f.get('cores', []):   # 계단·승강기 코어(층 좌표 → 건물 좌표)
            room_id=c_.get('room_id')
            if room_id is None and not c_.get('core_id'):
                cp=Point(sc*c_['cx']-dx,sc*c_['cy']-dy)
                matches=[r['id'] for r in rooms if c_['kind'] in r.get('tags',[]) and unary_union([Polygon(p['o'],p['h']) for p in r['polys']]).contains(cp)]
                room_id=matches[0] if len(matches)==1 else None
            core_all.append(dict(kind=c_['kind'], x=sc * c_['cx'] - dx, y=sc * c_['cy'] - dy, w=sc * c_['w'], h=sc * c_['h'], z0=z, z1=z + H, floor=names[i],room_id=room_id,align=how,
                core_id=c_.get('core_id'),access_room_ids=c_.get('access_room_ids',[]),association=c_.get('association')))
        B['floors'].append(dict(name=names[i], src=f['src'], use=uses[i], z=round(z, 3), h=round(H, 3), ceil_h=ch,
                                ramps=[dict(r,polys=to_list(geometry_r,dx,dy)) for r in f.get('ramps',[]) for geometry_r in [unary_union([P(p['o'],p.get('h',[])) for p in r['polys']])]],
                                door_h=dh, sill=s0, head=hd, beams=beam_state, ceil_rule=ch_rule, beam_d=bd, shift=[round(tx, 3), round(ty, 3)], scale=sc, align=how,
                                slab=to_list(foot, dx, dy), bands=bands, glass=glass, ceiling=ceil, rooms=rooms, openings=doors, columns=cols_out,
                                quality=f.get('quality'), provenance=f.get('provenance'),
                                fire_symbols=[dict(s,x=round(sc*s['x']-dx,4),y=round(sc*s['y']-dy,4))
                                              for s in f.get('fire',{}).get('symbols',[])],
                                fire_registration=f.get('fire',{}).get('registration'),
                                simulation_graph=f.get('simulation_graph'), automatic_repairs=f.get('automatic_repairs',[]),
                                checks=f['checks'] + ([dict(rule='A층정렬-불확실', id=names[i], note=f'정렬 근거 약함({how}) — 확인 필요')]
                                                      if 'xcorr' in how or how == 'none' or '약함' in how else [])
                                       + ([dict(rule='A기둥-단독층', id=names[i], n=lone, note=f'다른 층과 자리가 안 맞는 기둥 {lone}개(전이·오인식 확인)')]
                                          if len(F) > 1 and lone else []), stats=f['stats']))
    from cad_connectivity import build_graph, match_vertical_cores
    B['dropped_parts'] = dropped_parts
    B['shafts'], B['unconfirmed_vertical_cores'] = match_vertical_cores(core_all)
    B['core_nodes']=core_all
    B['vertical_connections']=[dict(kind=s['kind'],from_floor=a['floor'],from_core=a.get('core_id'),to_floor=b['floor'],to_core=b.get('core_id'),evidence='aligned_cad_core_overlap',overlap=s.get('overlaps',[])[k]) for s in B['shafts'] for k,(a,b) in enumerate(zip(s['nodes'],s['nodes'][1:]))]
    B['opening_unit'] = 'percent'
    B['schema_version'] = 2
    for floor in B['floors']:
        floor['simulation_graph'] = build_graph(floor['rooms'],floor['openings'],
            dict(room_h=floor.get('ceil_h') or floor['h'],door_h=floor['door_h'],sill=floor['sill'],head=floor['head']))
        floor['vertical_status'] = 'matched_adjacent_floors' if any(floor['name'] in shaft['floors'] for shaft in B['shafts']) else 'unconfirmed'
    json.dump(B, open(a.out + '.json', 'w', encoding='utf-8'), ensure_ascii=False)
    html = Path(__file__).with_name('viewer_template.html').read_text(encoding='utf-8')
    open(a.out + '.html', 'w', encoding='utf-8').write(html.replace('/*__DATA__*/null', json.dumps(B, ensure_ascii=False)))
    for fl in B['floors']:
        print(fl['name'], fl['use'], 'z', fl['z'], 'h', fl['h'], 'ceil', fl['ceil_h'], 'shift', fl['shift'], fl['align'],
              'walls', len(fl['bands'][0]['polys']), 'rooms', len(fl['rooms']), 'open', len(fl['openings']))
    print('levels', L, lev_src)


if __name__ == '__main__':
    main()
