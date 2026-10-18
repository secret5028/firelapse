"""CAD 선 보정기.
입력: 선분 목록(mm), 각 선분에 분류(wall/column/window/door)와 원레이어.
단계: 1 중복·겹침 병합 → 2 끝점 스냅 → 3 T자 붙이기 → 4 짧은 연장/돌출 자르기 → 5 폐합(짧은 틈)
       → 6 개구부 구역(문·창) 안의 같은 선 위 마주보는 틈 잇기(bridge)
자동 보정은 허용치 이내만. 허용치 넘는 애매한 틈은 고치지 않고 flags에 기록(표시만).
모든 수정은 log에 (op, 전, 후, 거리) 기록."""
import math
import numpy as np
from shapely.geometry import LineString, Point, box
from shapely.strtree import STRtree

DEF = dict(
    merge_ang=0.3,      # 도: 겹침 병합 각도 허용
    merge_off=2.0,      # mm: 같은 선으로 보는 수직 거리
    merge_gap=1.0,      # mm: 이 이하로 떨어진 공선 조각은 하나로
    snap=3.0,           # mm: 끝점 묶기
    tjoin=3.0,          # mm: 끝점이 다른 선 몸통에 이만큼 붙어 있으면 T자로 붙임
    ext_auto=30.0,      # mm: 자동 연장/자르기/폐합
    ext_flag=300.0,     # mm: 이 이하 틈은 표시만
    bridge_ang=1.0,     # 도: 개구부 양쪽 선 공선 판정
    bridge_off=6.0,     # mm
    bridge_min=400.0,   # mm: 개구부 폭 최소
    bridge_max=3200.0,  # mm: 개구부 폭 최대(양개문·셔터)
    flag_gap_min=400.0,  # 구역 밖 공선 틈 중 표시할 최소 폭
    seal_max=550.0,     # mm: 기존 공간 구획용 봉합 허용치. 실제 개구부/누기 판정 기준이 아님.
    cap_min=60.0,       # mm: 벽 끝 막음 두께 범위
    cap_max=450.0,
)


def _ang(s):
    a = math.atan2(s[3] - s[1], s[2] - s[0]) % math.pi
    return a


class Healer:
    def __init__(self, segs, meta, prm=None):
        """segs: (N,4) x1,y1,x2,y2 mm / meta: list of dict(cat, layer)"""
        self.p = dict(DEF, **(prm or {}))
        self.S = [list(map(float, s)) for s in segs]
        self.M = [dict(m) for m in meta]
        self.log, self.flags = [], []
        self.protected_spans = []
        self._protect_tree = None

    def protects_opening(self, a, b):
        connector = LineString([a, b])
        if self._protect_tree is None: return False
        for index in self._protect_tree.query(connector):
            oid = self._protect_ids[index]
            if connector.intersection(self._protect_tree.geometries[index]).length > self.p['snap']:
                self.log.append(dict(op='protect_opening', zone=oid,
                                     at=list(map(float, a)), to=list(map(float, b))))
                return True
        return False

    # ---------- 1 중복·겹침 병합 ----------
    def merge(self):
        p = self.p
        S = np.array(self.S)
        n = len(S)
        L = np.hypot(S[:, 2] - S[:, 0], S[:, 3] - S[:, 1])
        keep = L > 0.5
        for i in np.where(~keep)[0]:
            self.log.append(dict(op='drop_zero', seg=S[i].round(1).tolist(), layer=self.M[i]['layer']))
        idx = np.where(keep)[0]
        ang = np.array([_ang(S[i]) for i in range(n)])
        # 각도 버킷 + 선 offset 버킷
        parent = list(range(n))

        def f(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a
        tree = STRtree([LineString([(S[i, 0], S[i, 1]), (S[i, 2], S[i, 3])]) for i in idx])
        geoms = tree.geometries
        for k, i in enumerate(idx):
            g = geoms[k]
            for kk in tree.query(g.buffer(p['merge_off'] + p['merge_gap'])):
                j = idx[kk]
                if j <= i or self.M[i]['cat'] != self.M[j]['cat']:
                    continue
                da = abs(ang[i] - ang[j]); da = min(da, math.pi - da)
                if math.degrees(da) > p['merge_ang']:
                    continue
                d = max(g.distance(Point(S[j, 0], S[j, 1])) if True else 0, 0)
                # 두 끝점 모두 i의 무한직선 근처인지
                ux, uy = math.cos(ang[i]), math.sin(ang[i])
                off = lambda x, y: abs((x - S[i, 0]) * uy - (y - S[i, 1]) * ux)
                if off(S[j, 0], S[j, 1]) > p['merge_off'] or off(S[j, 2], S[j, 3]) > p['merge_off']:
                    continue
                # 투영 구간 겹침/근접
                t = lambda x, y: (x - S[i, 0]) * ux + (y - S[i, 1]) * uy
                a0, a1 = sorted([t(S[i, 0], S[i, 1]), t(S[i, 2], S[i, 3])])
                b0, b1 = sorted([t(S[j, 0], S[j, 1]), t(S[j, 2], S[j, 3])])
                if b0 > a1 + p['merge_gap'] or a0 > b1 + p['merge_gap']:
                    continue
                parent[f(j)] = f(i)
        groups = {}
        for i in idx:
            groups.setdefault(f(i), []).append(i)
        newS, newM = [], []
        for r, g in groups.items():
            if len(g) == 1:
                newS.append(S[g[0]].tolist()); newM.append(self.M[g[0]]); continue
            # 가장 긴 선 방향으로 투영 후 구간 합집합
            m = max(g, key=lambda i: L[i])
            ux, uy = (S[m, 2] - S[m, 0]) / L[m], (S[m, 3] - S[m, 1]) / L[m]
            ox, oy = S[m, 0], S[m, 1]
            iv = []
            for i in g:
                a = (S[i, 0] - ox) * ux + (S[i, 1] - oy) * uy
                b = (S[i, 2] - ox) * ux + (S[i, 3] - oy) * uy
                iv.append(sorted([a, b]))
            iv.sort()
            out = [iv[0][:]]
            for a, b in iv[1:]:
                if a <= out[-1][1] + p['merge_gap']:
                    out[-1][1] = max(out[-1][1], b)
                else:
                    out.append([a, b])
            for a, b in out:
                newS.append([ox + ux * a, oy + uy * a, ox + ux * b, oy + uy * b]); newM.append(self.M[m])
            self.log.append(dict(op='merge_overlap', n_in=len(g), n_out=len(out), layer=self.M[m]['layer'],
                                 at=[round(ox + ux * out[0][0]), round(oy + uy * out[0][0])]))
        self.S, self.M = newS, newM

    # ---------- 2 끝점 스냅 ----------
    def snap(self):
        tol = self.p['snap']
        E = np.array([[s[0], s[1]] for s in self.S] + [[s[2], s[3]] for s in self.S])
        n = len(self.S)
        from scipy.spatial import cKDTree
        tr = cKDTree(E)
        pairs = tr.query_pairs(tol, output_type='ndarray')
        parent = np.arange(len(E))

        def f(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]; a = parent[a]
            return a
        for a, b in pairs:
            ra, rb = f(a), f(b)
            if ra != rb: parent[rb] = ra
        roots = np.array([f(i) for i in range(len(E))])
        moved = 0
        for r in np.unique(roots):
            m = np.where(roots == r)[0]
            if len(m) < 2: continue
            c = E[m].mean(0)
            dmax = np.hypot(*(E[m] - c).T).max()
            if dmax < 1e-3: continue
            for k in m:
                si, end = (k, 0) if k < n else (k - n, 1)
                self.S[si][2 * end:2 * end + 2] = c.tolist()
            moved += 1
            self.log.append(dict(op='snap', n=len(m), at=c.round(1).tolist(), dist=round(float(dmax), 2)))
        self._drop_zero()

    def _drop_zero(self):
        k = [i for i, s in enumerate(self.S) if math.hypot(s[2] - s[0], s[3] - s[1]) > 0.5]
        self.S = [self.S[i] for i in k]; self.M = [self.M[i] for i in k]

    # ---------- 끝점 차수 ----------
    def _ends(self):
        from scipy.spatial import cKDTree
        n = len(self.S)
        E = np.array([[s[0], s[1]] for s in self.S] + [[s[2], s[3]] for s in self.S])
        tr = cKDTree(E)
        cnt = np.array([len(tr.query_ball_point(e, 0.01)) for e in E])
        lines = [LineString([(s[0], s[1]), (s[2], s[3])]) for s in self.S]
        st = STRtree(lines)
        return E, cnt, lines, st

    def _dangling(self, E, cnt, lines, st, tol):
        """다른 선 끝점과도 안 만나고 다른 선 몸통에도 안 닿는 끝점"""
        n = len(self.S); out = []
        for k in range(len(E)):
            if cnt[k] > 1: continue
            si = k % n
            pt = Point(E[k])
            touch = False
            for j in st.query(pt.buffer(tol)):
                if j != si and lines[j].distance(pt) <= tol:
                    touch = True; break
            if not touch: out.append(k)
        return out

    # ---------- 3·4·5 T자/연장/자르기/폐합 ----------
    def connect(self):
        p = self.p
        n = len(self.S)
        E, cnt, lines, st = self._ends()
        # 3 T자: 끝점이 다른 선 몸통에 tjoin 이내 → 투영점으로
        for k in range(len(E)):
            if cnt[k] > 1: continue
            si, end = k % n, k // n
            pt = Point(E[k])
            best = None
            for j in st.query(pt.buffer(p['tjoin'])):
                if j == si: continue
                d = lines[j].distance(pt)
                if 1e-3 < d <= p['tjoin'] and (best is None or d < best[0]):
                    best = (d, j)
            if best:
                q = lines[best[1]].interpolate(lines[best[1]].project(pt))
                self.S[si][2 * end:2 * end + 2] = [q.x, q.y]
                self.log.append(dict(op='t_join', at=[round(q.x, 1), round(q.y, 1)], dist=round(best[0], 2),
                                     layer=self.M[si]['layer']))
        E, cnt, lines, st = self._ends()
        dang = self._dangling(E, cnt, lines, st, 0.05)
        n = len(self.S)
        dset = set(dang)
        done = set()
        add = []
        # 4 연장/자르기: 선 방향으로 광선
        for k in dang:
            si, end = k % n, k // n
            s = self.S[si]
            x0, y0 = (s[0], s[1]) if end == 0 else (s[2], s[3])
            x1, y1 = (s[2], s[3]) if end == 0 else (s[0], s[1])
            L = math.hypot(x0 - x1, y0 - y1)
            ux, uy = (x0 - x1) / L, (y0 - y1) / L
            RL = max(p['ext_flag'], p['seal_max'])
            ray = LineString([(x0, y0), (x0 + ux * RL, y0 + uy * RL)])
            hit = None
            for j in st.query(ray):
                if j == si: continue
                ip = ray.intersection(lines[j])
                if ip.is_empty: continue
                pts = [ip] if ip.geom_type == 'Point' else [Point(c) for c in getattr(ip, 'coords', [])] if ip.geom_type == 'LineString' else list(getattr(ip, 'geoms', []))
                for q in pts:
                    d = math.hypot(q.x - x0, q.y - y0)
                    if d > 0.05 and (hit is None or d < hit[0]):
                        hit = (d, q.x, q.y, j)
            # 자르기: 이 끝점 바로 안쪽에서 다른 선과 교차(돌출) → 교차점까지 자름
            back = LineString([(x0, y0), (x0 - ux * min(p['ext_auto'], L * 0.5), y0 - uy * min(p['ext_auto'], L * 0.5))])
            trim = None
            for j in st.query(back):
                if j == si: continue
                ip = back.intersection(lines[j])
                if ip.geom_type == 'Point':
                    d = math.hypot(ip.x - x0, ip.y - y0)
                    if d > 0.05 and (trim is None or d > trim[0]):
                        trim = (d, ip.x, ip.y)
            if trim and (hit is None or hit[0] > p['ext_auto']):
                self.S[si][2 * end:2 * end + 2] = [trim[1], trim[2]]
                self.log.append(dict(op='trim', at=[round(trim[1], 1), round(trim[2], 1)], dist=round(trim[0], 2),
                                     layer=self.M[si]['layer']))
                done.add(k); continue
            okc = ('wall', 'column', 'window')
            if hit and (hit[0] <= p['ext_auto'] or (hit[0] < p['seal_max'] and self.M[si]['cat'] in okc and self.M[hit[3]]['cat'] in okc)):
                if self.protects_opening((x0, y0), (hit[1], hit[2])): continue
                # 최소 문 폭 미만 틈은 통로가 아님 → 끝까지 연장해 막음
                self.S[si][2 * end:2 * end + 2] = [hit[1], hit[2]]
                self.log.append(dict(op='extend', at=[round(hit[1], 1), round(hit[2], 1)], dist=round(hit[0], 2),
                                     layer=self.M[si]['layer']))
                done.add(k)
        # 4b 봉합: 남은 열린 끝(벽·창·기둥)에서 최소 문 폭 미만(seal_max) 거리의 다른 벽·기둥·창에 잇기(방향 무관)
        okc = ('wall', 'column', 'window')
        for k in dang:
            if k in done: continue
            si, end = k % n, k // n
            if self.M[si]['cat'] not in okc: continue
            s = self.S[si]; pe = Point((s[0], s[1]) if end == 0 else (s[2], s[3]))
            best = None
            for j in st.query(pe.buffer(p['seal_max'])):
                if j == si or self.M[j]['cat'] not in okc: continue
                sj = self.S[j]
                # 같은 끝점으로 이어진 선은 제외(자기 벽 몸통)
                if min(math.hypot(sj[0] - pe.x, sj[1] - pe.y), math.hypot(sj[2] - pe.x, sj[3] - pe.y)) < 1: continue
                d = lines[j].distance(pe)
                if p['ext_auto'] < d < p['seal_max'] and (best is None or d < best[0]): best = (d, j)
            if best:
                q = lines[best[1]].interpolate(lines[best[1]].project(pe))
                if self.protects_opening((pe.x, pe.y), (q.x, q.y)): continue
                add.append(([pe.x, pe.y, q.x, q.y], dict(self.M[si], added='seal')))
                self.log.append(dict(op='seal_link', at=[round(pe.x, 1), round(pe.y, 1)], to=[round(q.x, 1), round(q.y, 1)], dist=round(best[0], 1)))
                done.add(k)
        # 5 폐합: 남은 끝점끼리 가까우면 잇기
        rest = [k for k in dang if k not in done]
        from scipy.spatial import cKDTree
        if rest:
            P = np.array([E[k] for k in rest])
            tr = cKDTree(P)
            used = set()
            for a, b in sorted(tr.query_pairs(p['ext_auto']), key=lambda ab: np.hypot(*(P[ab[0]] - P[ab[1]]))):
                if a in used or b in used: continue
                d = float(np.hypot(*(P[a] - P[b])))
                if d <= p['ext_auto']:
                    if self.protects_opening(P[a], P[b]): continue
                    add.append(([*P[a], *P[b]], self.M[rest[a] % n]))
                    self.log.append(dict(op='close', at=P[a].round(1).tolist(), to=P[b].round(1).tolist(), dist=round(d, 2)))
                    used |= {a, b}
            # 5b 벽 끝 막음(cap): 평행한 두 선의 열린 끝이 벽 두께만큼 떨어져 수직으로 마주보면 잇기
            def _dir(k):
                s_ = self.S[k % n]; L_ = math.hypot(s_[2] - s_[0], s_[3] - s_[1])
                return ((s_[2] - s_[0]) / L_, (s_[3] - s_[1]) / L_)
            for a, b in sorted(tr.query_pairs(p['cap_max']), key=lambda ab: np.hypot(*(P[ab[0]] - P[ab[1]]))):
                if a in used or b in used: continue
                ka, kb = rest[a], rest[b]
                if self.M[ka % n]['cat'] not in ('wall', 'column', 'window') or self.M[kb % n]['cat'] not in ('wall', 'column', 'window'): continue
                da, db = _dir(ka), _dir(kb)
                if abs(da[0] * db[1] - da[1] * db[0]) > 0.02: continue          # 평행
                v = P[b] - P[a]; d = float(np.hypot(*v))
                if d < p['cap_min']: continue
                if abs((v[0] * da[0] + v[1] * da[1]) / d) > 0.1: continue      # 끝이 나란히(수직 연결)
                # 두 선이 같은 쪽으로 뻗어 있어야 함(끝 → 몸통 방향 동일)
                sa = self.S[ka % n]; sb = self.S[kb % n]
                ba = (np.array(sa[2:]) - np.array(sa[:2])) * (1 if ka < n else -1)
                bb = (np.array(sb[2:]) - np.array(sb[:2])) * (1 if kb < n else -1)
                if ba @ bb <= 0: continue
                if self.protects_opening(P[a], P[b]): continue
                add.append(([*P[a], *P[b]], self.M[ka % n]))
                self.log.append(dict(op='cap', at=P[a].round(1).tolist(), to=P[b].round(1).tolist(), dist=round(d, 1)))
                used |= {a, b}
            for i, k in enumerate(rest):
                if i in used or self.M[k % n]['cat'] not in ('wall', 'column'): continue
                # 표시만: ext_flag 이내 다른 선/끝점이 있는 애매한 틈
                pt = Point(E[k]); near = None
                for j in st.query(pt.buffer(p['ext_flag'])):
                    if j == k % n: continue
                    d = lines[j].distance(pt)
                    if p['ext_auto'] < d <= p['ext_flag'] and (near is None or d < near): near = d
                self.flags.append(dict(kind='dangling', at=E[k].round(1).tolist(), layer=self.M[k % n]['layer'],
                                       cat=self.M[k % n]['cat'], near=None if near is None else round(near, 1)))
        for s, m in add:
            self.S.append(list(map(float, s))); self.M.append(dict(m, added=m.get('added', 'close')))

    # ---------- 6 개구부 구역 안 공선 틈 잇기 ----------
    def bridge(self, zones):
        """zones: list of dict(kind='door'|'window', poly=shapely Polygon, r=반지름 or None, id)
        구역 안: 같은 직선 위, 서로 마주보는 두 끝점, 사이에 아무 선 없음 → 잇기.
        구역 밖 같은 조건 틈은 flags(gap_unlabeled)로 표시만."""
        p = self.p
        n = len(self.S)
        if not n: return []
        lines = [LineString([(s[0], s[1]), (s[2], s[3])]) for s in self.S]
        st = STRtree(lines)
        zt = STRtree([z['poly'] for z in zones]) if zones else None
        ang = [_ang(s) for s in self.S]
        bridges = []; seals = []
        seen = set()
        for i, s in enumerate(self.S):
            if self.M[i]['cat'] not in ('wall', 'column', 'window'): continue
            Li = lines[i].length
            if Li < 1: continue
            for end in (0, 1):
                x0, y0 = (s[0], s[1]) if end == 0 else (s[2], s[3])
                x1, y1 = (s[2], s[3]) if end == 0 else (s[0], s[1])
                ux, uy = (x0 - x1) / Li, (y0 - y1) / Li
                ray = LineString([(x0 + ux * 0.5, y0 + uy * 0.5), (x0 + ux * p['bridge_max'], y0 + uy * p['bridge_max'])])
                cand = None
                for j in st.query(ray.buffer(p['bridge_off'])):
                    if j == i or self.M[j]['cat'] not in ('wall', 'column', 'window'): continue
                    da = abs(ang[i] - ang[j]); da = min(da, math.pi - da)
                    if math.degrees(da) > p['bridge_ang']: continue
                    sj = self.S[j]
                    for e2 in (0, 1):
                        qx, qy = sj[2 * e2], sj[2 * e2 + 1]
                        ox, oy = sj[2 * (1 - e2)], sj[2 * (1 - e2) + 1]
                        t = (qx - x0) * ux + (qy - y0) * uy
                        off = abs((qx - x0) * uy - (qy - y0) * ux)
                        to = (ox - x0) * ux + (oy - y0) * uy
                        if t < 1.0 or t > p['bridge_max'] or off > p['bridge_off'] or to <= t:
                            continue
                        if cand is None or t < cand[0]: cand = (t, qx, qy, j)
                if not cand: continue
                t, qx, qy, j = cand
                key = tuple(sorted([(round(x0), round(y0)), (round(qx), round(qy))]))
                if key in seen: continue
                seen.add(key)
                br = LineString([(x0, y0), (qx, qy)])
                inner = br.interpolate(20).coords[0], br.interpolate(br.length - 20).coords[0]
                core = LineString(inner)
                blocked = any(lines[k].intersects(core) for k in st.query(core) if k not in (i, j))
                if blocked: continue
                mid = br.interpolate(0.5, normalized=True)
                z = None
                if zt is not None:
                    for zi in zt.query(mid):
                        if zones[zi]['poly'].contains(mid): z = zones[zi]; break
                if t < p['seal_max'] and (z is None or t < p['bridge_min'] * 0.5) and not self.protects_opening((x0, y0), (qx, qy)):
                    # 공리: 최소 문 폭보다 좁은 틈(창 멀리언·문틀 자리·작도 오차)은 통로가 아님 → 막기(개구부 아님)
                    seals.append(dict(seg=[x0, y0, qx, qy], zone=None, kind='seal', width=round(t, 1)))
                    self.log.append(dict(op='seal', at=[round(x0, 1), round(y0, 1)], to=[round(qx, 1), round(qy, 1)], dist=round(t, 1)))
                    continue
                if z is None:
                    if t >= p['flag_gap_min'] and self.M[i]['cat'] != 'window' and self.M[j]['cat'] != 'window':
                        self.flags.append(dict(kind='gap_unlabeled', at=[round(x0, 1), round(y0, 1)], to=[round(qx, 1), round(qy, 1)],
                                               width=round(t, 1), layer=self.M[i]['layer']))
                    continue
                spans=z.get('protected_spans') or []
                if z['kind']=='door' and z.get('closed_leaf_bridge_guard') and spans and not any(
                        br.intersection(span.buffer(200,cap_style=3)).length>=br.length*.6
                        for span in spans):
                    self.log.append(dict(op='reject_bridge_away_from_closed_leaf',zone=z['id'],
                                         at=[round(x0,1),round(y0,1)],to=[round(qx,1),round(qy,1)]))
                    continue
                r = z.get('r')
                if r and not (0.45 * r <= t <= 2.3 * r + 300):
                    self.flags.append(dict(kind='gap_zone_size', zone=z['id'], at=[round(x0, 1), round(y0, 1)], width=round(t, 1), r=round(r, 1)))
                    continue
                bridges.append(dict(seg=[x0, y0, qx, qy], zone=z['id'], kind=z['kind'], width=round(t, 1)))
                self.log.append(dict(op='bridge_' + z['kind'], zone=z['id'], at=[round(x0, 1), round(y0, 1)],
                                     to=[round(qx, 1), round(qy, 1)], dist=round(t, 1)))
        for b in bridges + seals:
            self.S.append(b['seg']); self.M.append(dict(cat='bridge', layer='*' + b['kind'], zone=b['zone']))
        # 표시 중복 제거(양방향)
        u, fl = set(), []
        for f in self.flags:
            k = (f['kind'], tuple(sorted([tuple(map(round, f['at'])), tuple(map(round, f.get('to', f['at'])))])))
            if k in u: continue
            u.add(k); fl.append(f)
        self.flags = fl
        return bridges

    def run(self, zones=None):
        self.protected_spans = []
        for z in zones or []:
            spans = z.get('protected_spans') or []
            # Only protect spans supported by opening geometry. A window block's
            # bounding rectangle can contain mullions or several openings; its
            # inferred centreline must not suppress room-boundary repairs.
            self.protected_spans.extend((z['id'], s) for s in spans)
        protected = [(oid, LineString([span.interpolate(self.p['snap']),
                                      span.interpolate(span.length - self.p['snap'])]).buffer(self.p['snap'], cap_style=2))
                     for oid, span in self.protected_spans if span.length > 2 * self.p['snap']]
        self._protect_ids = [oid for oid, _ in protected]
        self._protect_tree = STRtree([geometry for _, geometry in protected]) if protected else None
        self.merge(); self.snap(); self.connect()
        br = self.bridge(zones or [])
        return br

    def summary(self):
        from collections import Counter
        return dict(ops=dict(Counter(l['op'] for l in self.log)), flags=dict(Counter(f['kind'] for f in self.flags)),
                    segs=len(self.S))
