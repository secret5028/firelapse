# -*- coding: utf-8 -*-
"""경량 2층 존 화재·연기 해석 (시제품)

입력: building.json(CAD3D 원본 형상) 한 층 + 시나리오(발화 실, 문 개방률, 창 개방·파손률, 외기)
모델: 실마다 상부(연기)층·하부(공기)층 2층 존 — CFAST 계열 보존식
  dP/dt  = (γ-1)/V·(h_u+h_l)
  dV_u/dt= [(γ-1)h_u − V_u dP/dt]/(γ p0)
  dT_x/dt= [h_x − cp T_x ṁ_x + V_x dP/dt]/(cp m_x)
  화재 플룸(Heskestad) 유입, 개구부 높이별 베르누이 유량(층 경계·외기 정수압),
  산소 제한 연소(13.1 MJ/kg-O2, 하한 산소 농도), 미연 연료 이월, 벽 열손실(열관성 + 대류·복사),
  계단실·승강로는 전체 높이를 가진 수직 존(연돌 효과).
판정(시점별): 플래시오버(상부 600℃), 백드래프트 잠재(미연연료 Y_f≥0.10 & O2<LOC),
  FGI(연기 폭발) 잠재(Y_f≥LFL(T) & O2≥LOC & T<자연발화), 피난 한계(연기층<1.8m & 60℃↑).
가정은 모두 PRM 딕셔너리 한 곳에 — 근거는 문서에 정리.
"""
import json, math, sys, re
import numpy as np
from scipy.integrate import solve_ivp
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union

G = 9.81; RG = 287.0; CP = 1012.0; GAM = 1.4; P0 = 101325.0
Y_O2_AIR = 0.232; H_O2 = 13.1e6          # J/kg-O2 (Huggett)

from pyrocast_cfbt.physics_config import defaults as physics_defaults
_LEAKAGE = physics_defaults('leakage')

PRM = dict(
    pyro_feedback=True,                # legacy compatibility; L1 adapter sets False
    oxygen_limit_model='legacy_volume_linear',
    T_in=293.15, T_out=273.15,           # 실내·외기 온도 (겨울 기본 → 연돌 효과)
    Cd=0.68, n_slab=10,
    door_leak=0.02, win_leak=0.003,      # 닫힌 문·창 틈새 면적 ㎡
    elev_leak=_LEAKAGE['elevator_area_m2'], shaft_floor_leak=_LEAKAGE['stair_area_m2'], shaft_top_vent=0.10,
    chi_r=0.30, dHc=20.0e6,              # 복사 분율, 연료 유효 연소열 J/kg
    lol_lo=0.10, lol_hi=0.15,            # 하한 산소(부피분율) 연소 소멸~완전
    kpc=1.35e6,                          # 벽 kρc — EN1991-1-2 표준 구획 b≈1160 (콘크리트+경량 칸막이 혼합)
    h_conv=15.0, eps=0.9,
    LOC=0.12, Yf_backdraft=0.10, LFL0_hrr=1.4e6, T_ai=873.0,
    T_fo=873.0, d_min=0.3, T_pyro=600.0, T_pyro0=373.0, T_pyro_span=500.0, T_ten=333.15, z_ten=1.8,
)


def oxygen_factor(mass_fraction, parameters):
    """Native tanhsmooth uses mass fraction; legacy branch is kept unchanged."""
    if parameters.get('oxygen_limit_model') == 'native_mass_tanh':
        lo = parameters['native_lower_oxygen_limit_mass']
        hi = lo + 0.01
        return min(max(0.5 + 0.5025*math.tanh(6.0/(hi-lo)*(mass_fraction-lo)-3.0),0.0),1.0)
    return min(max((mass_fraction*29/32-parameters['lol_lo']) /
                   (parameters['lol_hi']-parameters['lol_lo']),0.0),1.0)

# 실별 화재하중·성장: EN 1991-1-2 부록 E 표 E.4/E.5 (fire_load_table.json — 데이터로 분리)
import os
FLT = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fire_load_table.json'), encoding='utf-8'))
from building_rules import load_rules
_USAGE_RULES = load_rules()['usage']
_FLT_RE = [(c, re.compile(p, re.I)) for c, p in _USAGE_RULES['names']]


def fire_class(names, floor_use):
    """실 이름 키워드 → 분류, 없으면 층 용도. 반환: dict(cls, label, mean, q80, alpha, rhrf, basis, by)"""
    for c, rx in _FLT_RE:
        if any(rx.search(n or '') for n in names or []):
            by = 'name'; break
    else:
        c = _USAGE_RULES['floor_use'].get(floor_use or 'default', 'default'); by = 'floor_use'
    d = dict(FLT['classes'][c]); d.update(cls=c, by=by, alpha=1000.0 / d['t_alpha'] ** 2)
    return d


def gumbel_params(mean, q80):
    """EN E.4: Gumbel, 평균·80% 분위 → (위치 μ, 척도 β)"""
    beta = (q80 - mean) / (-math.log(-math.log(0.8)) - 0.5772)
    return mean - 0.5772 * beta, beta


def _poly(r):
    ps = []
    for p in r['polys']:
        try:
            q = Polygon(p['o'], p.get('h') or []).buffer(0)
            if not q.is_empty: ps.append(q)
        except Exception: pass
    return unary_union(ps) if ps else Polygon()


def _span(o):
    if o.get('span'): return float(o['span'])
    if o.get('leaves'): return float(sum(l.get('r_std') or l.get('r') or 0.9 for l in o['leaves']))
    try:
        q = unary_union([Polygon(p).buffer(0) for p in o['polys']]).minimum_rotated_rectangle
        xy = list(q.exterior.coords)
        L = sorted([math.dist(xy[0], xy[1]), math.dist(xy[1], xy[2])])
        return min(max(L[1], 0.5), 2.4)
    except Exception: return 0.9


class Model:
    """한 층 + 수직 공간 네트워크"""
    def __init__(self, B, floor, scen=None, prm=None):
        self.P = dict(PRM); self.P.update(prm or {})
        P = self.P; scen = scen or {}
        F = [f for f in B['floors'] if f['name'] == floor][0]
        self.floor = floor; zf = F['z']
        H_room = F.get('ceil_h') or F['h']
        from cad_connectivity import opening_fraction, build_graph
        unit = scen.get('opening_unit', 'percent')
        doors = {k: opening_fraction(v,unit) for k,v in scen.get('doors',{}).items()}
        wins = {k: opening_fraction(v,unit) for k,v in scen.get('windows',{}).items()}
        if any(k not in {o['id'] for o in F['openings'] if o['kind'].startswith('door')} for k in doors):
            raise ValueError('Unknown door ID in scenario')
        if any(k not in {o['id'] for o in F['openings'] if o['kind'] in ('window','window_inner')} for k in wins):
            raise ValueError('Unknown window ID in scenario')
        dflt_door = opening_fraction(scen.get('door_open_default',0),unit)
        dflt_win = opening_fraction(scen.get('window_open_default',0),unit)
        graph = build_graph(F['rooms'],F['openings'],dict(room_h=H_room,
            door_h=F.get('door_h',2.1),sill=F.get('sill',.9),head=F.get('head',2.2)))
        self.input_graph = graph
        self.input_issues = dict(isolated_rooms=graph['isolated_rooms'],excluded_openings=graph['excluded_openings'],
            vertical_status=F.get('vertical_status','unconfirmed'))
        link_map = {o['id']:o for o in graph['connections']}

        # ── 수직 공간(계단·승강로) ──
        nodes = []; idx = {}
        floor_ids = {r['id'] for r in F['rooms']}
        shafts = [s for s in B.get('shafts', []) if floor in s.get('floors', [])
                  and s.get('room_ids',{}).get(floor) in floor_ids]
        self.input_issues['unmapped_shafts'] = sum(floor in s.get('floors', [])
            and s.get('room_ids',{}).get(floor) not in floor_ids for s in B.get('shafts', []))
        for k, s in enumerate(shafts):
            nm = f"{'계단' if s['kind']=='stair' else '승강로'}{k}"
            idx[('S', k)] = len(nodes)
            nodes.append(dict(id=f"S{k}", name=nm, kind=s['kind'], zf=s['z0'], H=s['z1'] - s['z0'],
                              A=s['w'] * s['h'], per=2 * (s['w'] + s['h']), shaft=s,
                              geom=Polygon([(s['x']-s['w']/2, s['y']-s['h']/2), (s['x']+s['w']/2, s['y']-s['h']/2),
                                            (s['x']+s['w']/2, s['y']+s['h']/2), (s['x']-s['w']/2, s['y']+s['h']/2)])))
        # ── 실 ──
        rmap = {}
        for r in F['rooms']:
            g = _poly(r)
            if g.is_empty: raise ValueError('Empty room geometry: '+r['id'])
            matches=[k for k,s in enumerate(shafts) if s.get('room_ids',{}).get(floor)==r['id']]
            if len(matches)>1: raise ValueError('Room mapped to multiple shafts: '+r['id'])
            if matches:
                rmap[r['id']]=idx[('S',matches[0])]; continue
            rmap[r['id']] = len(nodes)
            nodes.append(dict(id=r['id'], name=(r['names'] or [r['id']])[0], kind=next((k for k in ('elev','stair') if k in r.get('tags',[])),'room'), zf=zf, H=H_room,
                              A=g.area, per=g.length, geom=g, use_names=r['names']))
        self.nodes = nodes; self.rmap = rmap; N = len(nodes); self.N = N
        OUT = N

        V = []   # 개구부: (i, j, w_full, zb, zt, id, kind, p0, w_leak)
        def add(i, j, w, zb, zt, oid, kind, p0=1.0, wl=0.0):
            if i == j: return
            if i == OUT: i, j = j, i
            V.append([i, j, w, zb, zt, oid, kind, p0, wl])
        for o in F['openings']:
            if o['id'] not in link_map: continue
            dim = link_map[o['id']]['dimensions']
            s = [rmap.get(x, OUT if x == 'out' else None) for x in o['sides']]
            if None in s or len(s) != 2: continue
            w = dim['width_m']
            if o['kind'] in ('window', 'window_inner'):
                p = wins.get(o['id'], dflt_win)
                zb, zt = zf + dim['bottom_m'], zf + dim['top_m']
                add(s[0], s[1], w, zb, zt, o['id'], o['kind'], p, P['win_leak'] / (zt - zb)); continue
            else:
                p = doors.get(o['id'], dflt_door)
                dh = dim['height_m']
                zb, zt = zf, zf + dh
                add(s[0], s[1], w, zb, zt, o['id'], o['kind'], p, (P['elev_leak'] if o['kind']=='door_elev' else P['door_leak']) / dh)
        # 승강로 ↔ 해당 층 승강기 홀(승강장 문 틈) + 다른 층·상부
        for k, s in enumerate(shafts):
            i = idx[('S', k)]
            if s['kind'] == 'elev':
                # Landing doors above already connect explicit room IDs to this shaft.
                add(i, OUT, P['shaft_top_vent'] / 0.5, s['z1'] - 0.5, s['z1'], f"EV{k}", 'shaft_top')
            # 다른 층의 계단·승강장 문 틈새 → 건물 누기(외기로 근사)
            for f2 in B['floors']:
                if f2['name'] == floor or f2['name'] not in s['floors']: continue
                a = P['elev_leak'] if s['kind'] == 'elev' else P['shaft_floor_leak']
                add(i, OUT, a / 2.1, f2['z'], f2['z'] + 2.1, f"SL{k}_{f2['name']}", 'shaft_leak')
        self.vents = V
        self.vi = np.array([v[0] for v in V],dtype=int); self.vj = np.array([v[1] for v in V],dtype=int)
        self.vw = np.array([v[2] for v in V]); self.vp0 = np.array([v[7] for v in V]); self.vl = np.array([v[8] for v in V])
        # 창 열파손(비가역): 실 상부층이 T_break에 이르면 탈락 진행
        Tb = scen.get('T_break')                     # ℃, None이면 끔
        self.wb = np.array([k for k, v in enumerate(V) if v[6] == 'window' and v[1] == N and v[7] < 1]) if Tb is not None else np.array([], int)
        self.wb = self.wb.astype(int); self.nb = len(self.wb)
        self.Tb = (Tb or 0) + 273.15
        zb = np.array([v[3] for v in V]); zt = np.array([v[4] for v in V])
        ns = P['n_slab']; t = (np.arange(ns) + 0.5) / ns
        self.Z = zb[:, None] + (zt - zb)[:, None] * t[None, :]           # (nv, ns) 절대 높이
        self.dZ = ((zt - zb) / ns)[:, None] * np.ones((1, ns))
        self.zfa = np.array([n['zf'] for n in nodes]); self.Ha = np.array([n['H'] for n in nodes])
        self.Aa = np.array([n['A'] for n in nodes]); self.Va = self.Aa * self.Ha
        self.pera = np.array([n['per'] for n in nodes])
        self.Vmin = np.maximum(1e-3 * self.Va, 0.005)

        # ── 화재 ── 화점 좌표(fire_point=[x,y]) 우선, 없으면 발화 실 id
        self.fire_point = scen.get('fire_point'); self.plume_k = 1; self.fire_info = None
        ig = scen.get('fire_room')
        if self.fire_point is not None:
            pt = Point(*self.fire_point); best = None
            for r in F['rooms']:
                if r['id'] not in rmap: continue
                d = _poly(r).distance(pt)
                if best is None or d < best[0]: best = (d, r['id'])
            if best is None or best[0] > 1.0: raise ValueError('화점이 실 안에 있지 않습니다')
            ig = best[1]
            if nodes[rmap[ig]]['kind'] != 'room': raise ValueError('화점이 계단·승강로입니다')
            # 벽·모서리 화원: 경계 0.5m 안 변의 방향 수 → 1(중앙)·2(벽)·4(모서리) — 거울상 플룸
            g = nodes[rmap[ig]]['geom']; dirs = []
            for ring in [g.exterior] + list(g.interiors) if g.geom_type == 'Polygon' else [q.exterior for q in g.geoms]:
                c = list(ring.coords)
                for p1, p2 in zip(c[:-1], c[1:]):
                    from shapely.geometry import LineString
                    if math.dist(p1, p2) < 0.2 or LineString([p1, p2]).distance(pt) > 0.5: continue
                    a_ = math.degrees(math.atan2(p2[1] - p1[1], p2[0] - p1[0])) % 180
                    if all(min(abs(a_ - b_), 180 - abs(a_ - b_)) > 30 for b_ in dirs): dirs.append(a_)
            self.plume_k = 1 if not dirs else (2 if len(dirs) == 1 else 4)
        self.ig = rmap.get(ig, None) if ig else None
        if self.ig is not None:
            r = [r for r in F['rooms'] if r['id'] == ig][0]
            fc = fire_class(r['names'], F.get('use') or B.get('use'))
            fc.update(scen.get('fire', {}) and {k: v for k, v in scen['fire'].items() if k in ('alpha', 'qf_MJ', 'rhrf')})
            self.alpha = fc['alpha']; self.qf = fc.get('qf_MJ', fc['mean']) * 1e6
            A = self.Aa[self.ig]
            self.Qpk = fc['rhrf'] * 1e3 * A; self.Etot = self.qf * A
            self.fire_info = dict(room=ig, name=nodes[self.ig]['name'], cls=fc['cls'], label=fc['label'], by=fc['by'],
                                  basis=fc['basis'], qf_MJ=self.qf / 1e6, alpha=self.alpha, rhrf=fc['rhrf'],
                                  Qpk_kW=float(self.Qpk / 1e3), area=float(A), plume=self.plume_k, point=self.fire_point)
        self.rho_out = P0 / (RG * P['T_out'])

    # 상태 배열: [P(N), Vu(N), Tu(N), Tl(N), Yo_u(N), Yo_l(N), Yf_u(N), Yf_l(N), E]  (Y=질량분율)
    def y0(self):
        N = self.N; T = self.P['T_in']; rho = P0 / (RG * T)
        Pf = -self.rho_out * G * self.zfa                     # 바닥 압력 = 외기 정수압(초기)
        Vu = self.Vmin * 1.0; Vl = self.Va - Vu
        y = np.concatenate([Pf, Vu, np.full(N, T), np.full(N, T),
                            np.full(N, Y_O2_AIR), np.full(N, Y_O2_AIR), np.zeros(N), np.zeros(N), [0.0], np.zeros(self.nb)])
        return y

    def unpack(self, y):
        N = self.N
        return [y[k*N:(k+1)*N] for k in range(8)] + [0. if self.P.get('remove_cumulative_state') else y[8*N]]

    def fire(self, t, E):
        if self.ig is None: return 0.0
        q = min(self.alpha * 1e3 * t * t, self.Qpk)
        dec = min(max((self.Etot - E) / (0.3 * self.Etot), 0.0), 1.0)
        return q * dec

    def fire_sources(self, t, E):
        """Legacy single source. L1 supplies one prescribed source per room/cell."""
        q = self.fire(t, E)
        if self.ig is None or q <= 0:
            return []
        return [(self.ig, q, self.P['dHc'], self.P['chi_r'], self.plume_k, 0.3)]

    def rhs(self, t, y, diag=False):
        P = self.P; N = self.N
        Pf, Vu, Tu, Tl, Mou, Mol, Mfu, Mfl, E = self.unpack(y)
        extra=8*N+(0 if P.get('remove_cumulative_state') else 1)
        bk = np.clip(y[extra:extra + self.nb], 0, 1)
        pe = self.vp0.copy()
        if self.nb: pe[self.wb] = pe[self.wb] + (1 - pe[self.wb]) * bk
        vw = self.vw * pe + (1 - pe) * self.vl
        raw_Vu=Vu
        smooth=P.get('smooth_state_bounds',False)
        if smooth:
            from .numerics import lower,bounded
            atol=self.integration_atol()
            Vu=bounded(Vu,self.Vmin,self.Va-self.Vmin,10*atol[N:2*N])
            Tu=lower(Tu,200.,10*atol[2*N:3*N]);Tl=lower(Tl,200.,10*atol[3*N:4*N])
        else:
            Vu = np.clip(Vu, self.Vmin, self.Va - self.Vmin)
            Tu = np.maximum(Tu, 200); Tl = np.maximum(Tl, 200)
        Vl = self.Va - Vu
        ru = P0 / (RG * Tu); rl = P0 / (RG * Tl)
        mu = ru * Vu; ml = rl * Vl
        hl = Vl / self.Aa
        Yo = np.stack([Mou, Mol]); Yf = np.stack([np.maximum(Mfu, 0), np.maximum(Mfl, 0)])  # (2,N) [0]=상부
        if smooth:
            Yo=lower(np.stack([Mou,Mol]),0.,10*atol[4*N:6*N].reshape(2,N))
            Yf=lower(np.stack([Mfu,Mfl]),0.,10*atol[6*N:8*N].reshape(2,N))
        su = np.clip((Vu - self.Vmin) / (2 * self.Vmin), 0, 1)     # 층이 최소 체적이면 그 층에서 못 빠짐
        sl = np.clip((Vl - self.Vmin) / (2 * self.Vmin), 0, 1)

        # ── 개구부 유량 ──
        Z = self.Z; vi, vj = self.vi, self.vj
        out = vj == N
        def side(k, isout):
            kk = np.where(isout, 0, k)
            zrel = Z - self.zfa[kk][:, None]
            hlk = hl[kk][:, None]
            p = Pf[kk][:, None] - G * (rl[kk][:, None] * np.clip(zrel, 0, hlk) + ru[kk][:, None] * np.clip(zrel - hlk, 0, None))
            up = 0.5 * (1 + np.tanh((zrel - hlk) / 0.02))            # 상부층 비율(경계 매끄럽게)
            up = up * su[kk][:, None]; up = 1 - (1 - up) * sl[kk][:, None]
            rho = up * ru[kk][:, None] + (1 - up) * rl[kk][:, None]
            T = up * Tu[kk][:, None] + (1 - up) * Tl[kk][:, None]
            yo = up * Yo[0][kk][:, None] + (1 - up) * Yo[1][kk][:, None]
            yf = up * Yf[0][kk][:, None] + (1 - up) * Yf[1][kk][:, None]
            if isout is not False:
                o = isout[:, None]
                p = np.where(o, -self.rho_out * G * Z, p); rho = np.where(o, self.rho_out, rho)
                T = np.where(o, P['T_out'], T); yo = np.where(o, Y_O2_AIR, yo); yf = np.where(o, 0.0, yf)
                up = np.where(o, 0.0, up)
            return p, rho, T, yo, yf, up
        pi_, ri, Ti, yoi, yfi, upi = side(vi, False)
        pj_, rj, Tj, yoj, yfj, upj = side(vj, out)
        dp = pi_ - pj_
        fwd = 0.5 * (1 + np.tanh(dp / 1e-3))
        rs = fwd * ri + (1 - fwd) * rj
        sq = dp / np.sqrt(np.hypot(dp, 0.01))                   # sign·sqrt(|dp|) 정칙화
        m = P['Cd'] * vw[:, None] * self.dZ * np.sqrt(2 * rs) * sq   # +: i→j

        # User-specified volumetric fan flow with native-style adverse pressure cutoff.
        for index,vent in getattr(self,'mechanical_flows',{}).items():
            supply=vent.get('direction','supply')=='supply'
            adverse=dp[index] if supply else -dp[index]
            low,high=vent['cutoffs'];factor=np.clip((high-adverse)/(high-low),0.,1.)
            density=rj[index] if supply else ri[index]
            m[index]=( -1 if supply else 1)*vent['flow_m3_s']*density*factor/m.shape[1]
        mi = np.maximum(m, 0); mj = np.maximum(-m, 0)           # i→j, j→i
        dmu = np.zeros(N); dml = np.zeros(N); hu = np.zeros(N); hlw = np.zeros(N)
        inu = np.zeros(N); inl = np.zeros(N)                    # 유입 질량
        sou = np.zeros(N); sol_ = np.zeros(N); sfu = np.zeros(N); sfl = np.zeros(N)   # 유입 화학종
        door_jet=P.get('door_jet_enabled',False)
        nv=len(vi);jet_fuel_u=np.zeros(2*nv);jet_fuel_l=np.zeros(2*nv)
        outgoing_upper_fuel=np.zeros(N)
        def flow(src_up, Ts, yo, yf, mass, frm, to, from_room, to_room):
            if from_room is not None:
                fr = np.where(from_room, frm, 0); mm = mass * from_room[:, None]
                np.add.at(dmu, fr, -(mm * src_up).sum(1)); np.add.at(dml, fr, -(mm * (1 - src_up)).sum(1))
                np.add.at(hu, fr, -CP * (mm * src_up * Ts).sum(1)); np.add.at(hlw, fr, -CP * (mm * (1 - src_up) * Ts).sum(1))
            k = np.where(to_room, to, 0); mm = mass * to_room[:, None]
            Tm = 0.5 * (Tl[k] + Tu[k])[:, None]; wd = np.maximum(2.0, 0.1 * (Tu[k] - Tl[k]))[:, None]
            du = 0.5 * (1 + np.tanh((Ts - Tm) / wd))               # 두 층 중간보다 뜨거우면(가벼우면) 상부층으로
            a_ = mm * du; b_ = mm * (1 - du)
            np.add.at(dmu, k, a_.sum(1)); np.add.at(dml, k, b_.sum(1))
            np.add.at(inu, k, a_.sum(1)); np.add.at(inl, k, b_.sum(1))
            np.add.at(hu, k, CP * (a_ * Ts).sum(1)); np.add.at(hlw, k, CP * (b_ * Ts).sum(1))
            np.add.at(sou, k, (a_ * yo).sum(1)); np.add.at(sol_, k, (b_ * yo).sum(1))
            np.add.at(sfu, k, (a_ * yf).sum(1)); np.add.at(sfl, k, (b_ * yf).sum(1))
            if door_jet:
                fr=np.where(from_room,frm,0)
                upper_fuel=mass*src_up*np.maximum(Mfu[fr],0.)[:,None]*from_room[:,None]
                np.add.at(outgoing_upper_fuel,fr,upper_fuel.sum(1))
                eligible=self.door_jet_eligible & from_room & to_room
                offset=0 if frm is vi else nv
                jet_fuel_u[offset:offset+nv]=(upper_fuel*du).sum(1)*eligible
                jet_fuel_l[offset:offset+nv]=(upper_fuel*(1-du)).sum(1)*eligible
        room_j = ~out; room_i = np.ones_like(out)
        flow(upi, Ti, yoi, yfi, mi, vi, vj, room_i, room_j)      # i → j
        flow(upj, Tj, yoj, yfj, mj, vj, vi, room_j, room_i)      # j → i (외기 출발이면 출발 장부 없음)

        # ── 화재·플룸 ──
        Qf_total = Q_total = Qp_total = me_total = Lf_total = pyro_mass_total = 0.0
        room_Q = np.zeros(N); room_Qf = np.zeros(N); room_Qp = np.zeros(N)
        room_radiation = np.zeros(N)
        upper_primary_oxygen=np.zeros(N)
        lower_plume_oxygen=np.zeros(N)
        for i, Qf, heat_comb, chi_r, plume_k, fire_height in self.fire_sources(t, E):
            D = max(math.sqrt(4 * (Qf / 500e3) / math.pi), 0.3)
            k_ = plume_k                                  # legacy mirror plume
            Qc = (1 - chi_r) * Qf / 1e3 * k_
            L = 0.235 * (k_ * Qf / 1e3) ** 0.4 - 1.02 * D
            def entr(z):
                if z <= 0: return 0.0
                if z > max(L, 0.01): return (0.071 * Qc ** (1/3) * z ** (5/3) + 0.0018 * Qc) / k_
                return 0.0056 * Qc * z / max(L, 0.1) / k_
            Hf = self.Ha[i] - fire_height
            # 하부층(신선 공기) 유입: 플룸 유입량, 단 개구부로 하부층에 드는 공기는 플룸 수요 한도까지 화원으로(유입 기류)
            me = max(entr(min(max(hl[i] - fire_height, 0.0), Hf)), min(inl[i], entr(Hf)))
            me = min(me, 0.5 * ml[i])
            meu = max(entr(Hf) - me, 0.0)                                   # 연기층 내부 재순환 유입
            lolf = lambda Y: oxygen_factor(Y,P)
            O2in = me * Yo[1][i] + meu * Yo[0][i]
            Q = min(Qf, H_O2 * (me * Yo[1][i] * lolf(Yo[1][i]) + meu * Yo[0][i] * lolf(Yo[0][i])))
            # 열분해: 연소분 + 미연분(상부층 열 되먹임 비례 — 식으면 훈소·정지)
            fb = min(max((Tu[i] - P['T_pyro0']) / P['T_pyro_span'], 0), 1) if P['pyro_feedback'] else 1.0
            Qp = Q + (Qf - Q) * fb
            mp = Qp / heat_comb
            pyro_mass_total += mp
            dml[i] -= me; dmu[i] += me + mp
            if door_jet:lower_plume_oxygen[i]+=me*max(float(Mol[i]),0.)
            hlw[i] -= CP * Tl[i] * me
            hu[i] += CP * Tl[i] * me + (1 - chi_r) * Q + CP * P['T_pyro'] * mp
            inu[i] += me + mp
            sou[i] += me * Yo[1][i] - min(Q / H_O2, O2in)
            upper_primary_oxygen[i]+=max(min(Q/H_O2,O2in)-me*Yo[1][i],0.)
            sfu[i] += me * Yf[1][i] + ((Qp - Q) / heat_comb)
            room_Q[i] += Q; room_Qf[i] += Qf; room_Qp[i] += Qp
            room_radiation[i] += chi_r*Q
            Q_total += Q; Qf_total += Qf; Qp_total += Qp; me_total += me
            if Q > 0:
                Lf_total = max(Lf_total, max(0.235 * (plume_k * Q / 1e3) ** 0.4 - 1.02 * D, 0.0))

        upper_xi=np.zeros(N);upper_o2=np.zeros(N);upper_heat=np.zeros(N)
        if P.get('upper_combustion_enabled',False):
            from .numerics import upper_reaction
            upper_xi,upper_o2,upper_heat=upper_reaction(mu,Mfu,Mou,Tu,upper_primary_oxygen,P,
                outgoing_upper_fuel if door_jet else None)
            sfu-=upper_xi;sou-=upper_o2;hu+=upper_heat
            Q_total+=float(upper_heat.sum())
            # Products remain in the layer. No extra total mass, solid fuel
            # consumption, plume entrainment, or radiation source is added.

        jet_xi=np.zeros(2*nv);jet_heat=np.zeros(2*nv);jet_o2=np.zeros(2*nv)
        jet_room_heat=np.zeros(N);jet_room_o2=np.zeros(N);jet_available=np.zeros(N)
        if door_jet:
            from .door_jet import react
            dest=np.r_[np.minimum(vj,N-1),vi];source=np.r_[vi,np.minimum(vj,N-1)]
            eligible=np.r_[self.door_jet_eligible,self.door_jet_eligible]
            jet=react(jet_fuel_u,jet_fuel_l,Tu[source],dest,eligible,ml,Mol,lower_plume_oxygen,P)
            jet_xi=jet['reaction_kg_s'];jet_heat=jet['heat_W'];jet_o2=jet['oxygen_kg_s']
            jet_room_heat=jet['room_heat_W'];jet_room_o2=jet['room_oxygen_kg_s'];jet_available=jet['available_lower_oxygen_kg_s']
            np.add.at(sfu,dest,-jet['burn_into_upper_kg_s'])
            np.add.at(sfl,dest,-jet['burn_into_lower_kg_s'])
            sol_-=jet_room_o2;hu+=jet_room_heat
            Q_total+=float(jet_room_heat.sum())

        # ── 벽 열손실 ──
        hk = math.sqrt(P['kpc'] / max(t, 1.0))
        def hloss(T, A):
            hr = P['eps'] * 5.67e-8 * (T * T + P['T_in'] ** 2) * (T + P['T_in'])
            h = 1 / (1 / (P['h_conv'] + hr) + 1 / hk)
            return h * A * (T - P['T_in'])
        Au = self.Aa + self.pera * (self.Ha - hl); Al = self.pera * hl
        wall_rhs = np.zeros(0); wall_stats = {}
        if getattr(self, 'finite_walls', None) is not None:
            lossu, lossl, wall_rhs, wall_stats = self.finite_walls.exchange(self,y,Tu,Tl,hl,room_radiation)
            hu -= lossu; hlw -= lossl
            hu += wall_stats.pop('gas_fire_radiation_by_room',np.zeros(N))
        else:
            hu -= hloss(Tu, Au); hlw -= hloss(Tl, Al) * 0.3       # legacy compatibility

        # ── 보존식 ──
        dP = (GAM - 1) / self.Va * (hu + hlw)
        dVu = ((GAM - 1) * hu - Vu * dP) / (GAM * P0)
        if smooth:
            width=10*atol[N:2*N]
            # Outward rate smoothly vanishes at a bound; inward recovery stays.
            low=.5*(1+np.tanh((raw_Vu-self.Vmin)/width))
            high=.5*(1+np.tanh((self.Va-self.Vmin-raw_Vu)/width))
            dVu=np.where(dVu<0,dVu*low,dVu*high)
        else:
            dVu = np.where((Vu <= self.Vmin * 1.0001) & (dVu < 0), 0, dVu)
            dVu = np.where((Vu >= self.Va - self.Vmin * 1.0001) & (dVu > 0), 0, dVu)
        dTu = (hu - CP * Tu * dmu + Vu * dP) / (CP * mu)
        dTl = (hlw - CP * Tl * dml + Vl * dP) / (CP * ml)
        dou = (sou - Yo[0] * inu) / mu; dol = (sol_ - Yo[1] * inl) / ml
        dfu = (sfu - Yf[0] * inu) / mu; dfl = (sfl - Yf[1] * inl) / ml
        if diag:
            return dict(Q=Q_total, Qf=Qf_total, me=me_total, Qp=Qp_total,
                        broken=bk, Lf=Lf_total, room_Q=room_Q, room_Qf=room_Qf,
                        room_Qp=room_Qp, upper_reaction_kg_s=upper_xi,
                        upper_oxygen_consumption_kg_s=upper_o2,upper_HRR_W=upper_heat,
                        upper_primary_oxygen_kg_s=upper_primary_oxygen,
                        door_jet_reaction_kg_s=jet_xi,door_jet_HRR_W=jet_heat,
                        door_jet_oxygen_kg_s=jet_o2,door_jet_room_HRR_W=jet_room_heat,
                        door_jet_room_oxygen_kg_s=jet_room_o2,
                        door_jet_available_lower_oxygen_kg_s=jet_available,
                        lower_plume_oxygen_kg_s=lower_plume_oxygen,
                        outgoing_upper_fuel_kg_s=outgoing_upper_fuel,
                        door_jet_incoming_fuel_kg_s=jet_fuel_u+jet_fuel_l,
                        mass_rate=float(np.sum(dmu+dml)),
                        heat_rate=float(np.sum(hu+hlw)),
                        boundary_mass_in=float(mj[out].sum()),boundary_mass_out=float(mi[out].sum()),
                        boundary_enthalpy_in=float(CP*(mj[out]*Tj[out]).sum()),
                        boundary_enthalpy_out=float(CP*(mi[out]*Ti[out]).sum()),
                        pyro_mass_rate=pyro_mass_total, **wall_stats)
        db = np.zeros(self.nb)
        if self.nb:
            ri = self.vi[self.wb]
            db = 0.2 * 0.5 * (1 + np.tanh((Tu[ri] - self.Tb) / 10.0)) * (1 - bk)
        cumulative=[] if P.get('remove_cumulative_state') else [Qp_total]
        # Airflow within a sealed component uses only pressure differences.
        # Drop its common pressure drift from the integrated pressure state
        # after the physical energy and volume balances have used raw dP.
        for rooms,reference in getattr(self, 'sealed_pressure_rooms', ()):
            dP[rooms] -= dP[reference]
        return np.concatenate([dP, dVu, dTu, dTl, dou, dol, dfu, dfl, cumulative, db, wall_rhs])

    def sparsity(self):
        from scipy.sparse import lil_matrix
        N = self.N; n = 8 * N + 1 + self.nb
        C = np.eye(N, dtype=bool)
        for i, j in zip(self.vi, self.vj):
            if j < N: C[i, j] = C[j, i] = True
        S = lil_matrix((n, n), dtype=bool)
        for a in range(8):
            for b in range(8):
                S[a*N:(a+1)*N, b*N:(b+1)*N] = C
        S[:, 8*N] = True; S[8*N, :] = True
        for q, k in enumerate(self.wb):
            r = 8 * N + 1 + q; i = self.vi[k]
            S[r, r] = True
            for a in range(8): S[r, a*N + i] = True; S[a*N:(a+1)*N, r] = C[:, i]
        return S.tocsr()

    def run(self, t_end=1200, dt_out=10):
        te = np.arange(0, t_end + 1e-9, dt_out)
        N = self.N
        atol = np.concatenate([np.full(N, 1e-3), self.Vmin * 0.1, np.full(2 * N, 0.05),
                               np.full(4 * N, 1e-6), [1e3], np.full(self.nb, 1e-3)])
        sol = solve_ivp(self.rhs, (0, t_end), self.y0(), method='BDF', t_eval=te, rtol=1e-4, atol=atol,
                        jac_sparsity=self.sparsity())
        self.sol = sol
        return sol

    # ── 결과 정리·판정 ──
    def result(self):
        P = self.P; sol = self.sol; N = self.N
        Pf, Vu, Tu, Tl, Mou, Mol, Mfu, Mfl, E = self.unpack(sol.y)
        Vu = np.clip(Vu, self.Vmin[:, None], (self.Va - self.Vmin)[:, None])
        ru = P0 / (RG * Tu); mu = ru * Vu
        Yo_u = Mou; Yf_u = np.maximum(Mfu, 0)
        Xo_u = Yo_u * 29 / 32
        hl = (self.Va[:, None] - Vu) / self.Aa[:, None]
        dg = [self.rhs(t, sol.y[:, k], diag=True) for k, t in enumerate(sol.t)]
        Q = np.array([d['Q'] for d in dg]); Lf = np.array([d['Lf'] for d in dg])
        lfl = P['LFL0_hrr'] / P['dHc'] * np.clip(1 - (Tu - 293) / 1300, 0.2, 1)
        deep = (self.Ha[:, None] - np.minimum(hl, self.Ha[:, None])) >= P['d_min']   # 얇은 연기층은 조성 판정 제외
        flash = Tu >= P['T_fo']
        backdraft = (Yf_u >= P['Yf_backdraft']) & (Xo_u < P['LOC']) & deep
        fgi = (Yf_u >= lfl) & (Xo_u >= P['LOC']) & (Tu < P['T_ai']) & deep
        unten = (np.minimum(hl, self.Ha[:, None]) < P['z_ten']) & (Tu > P['T_ten'])
        unten &= (self.zfa[:, None] == self.zfa.max()) | np.array([n['kind'] == 'room' for n in self.nodes])[:, None]
        rooms = []
        for i, n in enumerate(self.nodes):
            def first(b):
                k = np.argmax(b[i]); return float(sol.t[k]) if b[i].any() else None
            rooms.append(dict(id=n['id'], name=n['name'], kind=n['kind'],
                              z_int=np.round(np.minimum(hl[i], n['H']), 2).tolist(),
                              T_u=np.round(Tu[i] - 273.15, 1).tolist(), T_l=np.round(Tl[i] - 273.15, 1).tolist(),
                              O2_u=np.round(Xo_u[i] * 100, 2).tolist(), Yf_u=np.round(Yf_u[i], 4).tolist(),
                              t_flashover=first(flash), t_backdraft=first(backdraft), t_fgi=first(fgi),
                              t_untenable=first(unten)))
        wb = {}
        for q, k in enumerate(self.wb):
            b = sol.y[8 * N + 1 + q]; hit = np.nonzero(b > 0.5)[0]
            if len(hit): wb[self.vents[k][5]] = float(sol.t[hit[0]])
        return dict(floor=self.floor, window_broken=wb, fire_room=self.nodes[self.ig]['id'] if self.ig is not None else None,
                    t=sol.t.tolist(), HRR_kW=np.round(Q / 1e3, 1).tolist(), flame_L=np.round(Lf, 2).tolist(), fire=self.fire_info,
                    flags=dict(flash=flash, backdraft=backdraft, fgi=fgi, unten=unten), rooms=rooms,
                    input_issues=self.input_issues, opening_unit='percent',
                    ok=bool(sol.success), msg=sol.message)


if __name__ == '__main__':
    import argparse, time
    ap = argparse.ArgumentParser()
    ap.add_argument('building'); ap.add_argument('--floor', default='4F')
    ap.add_argument('--fire', help='발화 실 id'); ap.add_argument('--point', help='화점 x,y (건물 좌표 m)')
    ap.add_argument('--door', default=0, type=float, help='전체 문 기본 개방률 %')
    ap.add_argument('--fire-door', default=None, type=float, help='발화 실 문 개방률 %')
    ap.add_argument('--win', default=0, type=float, help='전체 창 기본 개방·파손률 %')
    ap.add_argument('--door-settings'); ap.add_argument('--window-settings')
    ap.add_argument('--tbreak', default=None, type=float, help='창 열파손 온도 ℃(없으면 끔)')
    ap.add_argument('--t', default=1200, type=float); ap.add_argument('-o', '--out')
    a = ap.parse_args()
    B = json.load(open(a.building, encoding='utf-8'))
    sc = dict(fire_room=a.fire, fire_point=[float(v) for v in a.point.split(',')] if a.point else None, T_break=a.tbreak, door_open_default=a.door, window_open_default=a.win, doors={}, windows={})
    if a.door_settings:
        d = json.load(open(a.door_settings, encoding='utf-8')).get(a.floor, {})
        sc['doors'] = {k: v.get('open_pct', 0) for k, v in d.items()}
    if a.window_settings:
        d = json.load(open(a.window_settings, encoding='utf-8')).get(a.floor, {})
        sc['windows'] = {k: v.get('open_break_pct', 0) for k, v in d.items()}
    F = [f for f in B['floors'] if f['name'] == a.floor][0]
    M0 = Model(B, a.floor, sc)
    if a.fire_door is not None:
        for o in F['openings']:
            if (a.fire or M0.fire_info['room']) in o['sides'] and o['kind'].startswith('door'): sc['doors'][o['id']] = a.fire_door
    t0 = time.time(); M = Model(B, a.floor, sc); M.run(a.t); R = M.result()
    print('화재:', R['fire'])
    print(f"노드 {M.N} 개구부 {len(M.vents)} 계산 {time.time()-t0:.1f}s {R['msg']}")
    h = np.array(R['HRR_kW']); print('HRR(kW) 매 60s:', [int(x) for x in h[::max(1, int(60 / (R['t'][1] - R['t'][0])))]])
    print('창 열파손:', R['window_broken'])
    for r in R['rooms']:
        k = len(R['t']) - 1
        print(f"{r['id']:>4} {r['name'][:8]:<8} z={r['z_int'][k]:5.2f} Tu={r['T_u'][k]:6.1f} O2={r['O2_u'][k]:5.1f} Yf={r['Yf_u'][k]:.3f}"
              f" FO={r['t_flashover']} BD={r['t_backdraft']} FGI={r['t_fgi']} 피난한계={r['t_untenable']}")
    if a.out:
        R.pop('flags'); json.dump(R, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False)
