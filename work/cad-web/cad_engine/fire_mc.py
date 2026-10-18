# -*- coding: utf-8 -*-
"""경량 해석 몬테카를로 — 현장 도착 시점 위험 확률

표본 변수(근거·분포는 문서화, 기본값은 숙박 — 시나리오 json으로 덮어쓰기 가능)
  발화 실: 지정 또는 객실·실 면적 가중 무작위
  성장 α : 느림 0.00293 / 보통 0.0117 / 빠름 0.0469 kW/s² (0.25/0.5/0.25)
  화재하중: 용도 평균 × Gumbel(COV 0.3)
  발화 실 문: 닫힘 p_fd_closed, 아니면 U(10,100)%
  다른 실 문: 열림 p_door_open → U(10,100)%
  계단 방화문: 열림(고임) p_stair_open → 100%
  창: 초기 개방·파손 p_win_open → U(10,100)%, 열파손 온도 U(300,600)℃
  외기 온도: U(-5,28)℃
  신고까지(발화→신고): U(60,600) s,  신고→도착·전개: U(300,600) s
출력: 실별 도착 시점 위험 확률(플래시오버 경과, 백드래프트 잠재, FGI 잠재, 피난 한계), 연기층 높이 분위
"""
import json, sys, os, time, math, re
import numpy as np
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fire_zone as fz

DEF = dict(n=100, seed=1, t_end=1500, dt=10,
           p_fd_closed=0.6, p_door_open=0.05, p_stair_open=0.1, p_win_open=0.2,
           t_alpha_mult_p=[0.25, 0.5, 0.25],
           T_out=[-5, 28], t_report=[60, 600], t_response=[300, 600], T_break=[300, 600])


def sample(B, floor, cfg, rng, fire_room=None, fire_point=None):
    F = [f for f in B['floors'] if f['name'] == floor][0]
    rooms = [r for r in F['rooms'] if 'stair' not in r.get('tags', []) and r['area'] >= 4]
    used = {s for o in F['openings'] for s in o['sides']}
    rooms = [r for r in rooms if r['id'] in used]
    if fire_room is None:
        # 발화 빈도: 면적 가중, 복도·홀·승강장은 가연물이 적어 0.2배 (cfg로 조정)
        circ = re.compile(cfg.get('circ_re', '복도|홀|ELEV|로비|LOBBY|HALL|CORR'), re.I)
        w = np.array([r['area'] * (cfg.get('circ_w', 0.2) if any(circ.search(n) for n in r['names']) else 1.0) for r in rooms])
        fire_room = rooms[rng.choice(len(rooms), p=w / w.sum())]['id']
    stair_ids = {r['id'] for r in F['rooms'] if 'stair' in r.get('tags', [])}
    doors = {}; wins = {}
    for o in F['openings']:
        if o['kind'] in ('window', 'window_inner'):
            wins[o['id']] = float(rng.uniform(10, 100)) if rng.random() < cfg['p_win_open'] else 0.0
        elif o['kind'].startswith('door'):
            if fire_room in o['sides']:
                doors[o['id']] = 0.0 if rng.random() < cfg['p_fd_closed'] else float(rng.uniform(10, 100))
            elif stair_ids & set(o['sides']):
                doors[o['id']] = 100.0 if rng.random() < cfg['p_stair_open'] else 0.0
            else:
                doors[o['id']] = float(rng.uniform(10, 100)) if rng.random() < cfg['p_door_open'] else 0.0
    # 발화 실 분류(EN 1991-1-2 E.4/E.5): 화재하중 Gumbel(평균·80%), 성장 t_α는 표값 중심 ×(0.5·1·2) 0.25/0.5/0.25
    r = [r for r in F['rooms'] if r['id'] == fire_room][0]
    fc = fz.fire_class(r['names'], F.get('use') or B.get('use'))
    mu, beta = fz.gumbel_params(fc['mean'], fc['q80'])
    qf = max(float(rng.gumbel(mu, beta)), 0.2 * fc['mean'])
    ta_ = fc['t_alpha'] * float(rng.choice([2.0, 1.0, 0.5], p=cfg['t_alpha_mult_p']))
    alpha = 1000.0 / ta_ ** 2
    return dict(fire_room=fire_room, fire_point=fire_point, doors=doors, windows=wins, fire=dict(alpha=alpha, qf_MJ=qf),
                T_break=float(rng.uniform(*cfg['T_break'])),
                prm=dict(T_out=float(rng.uniform(*cfg['T_out'])) + 273.15),
                t_report=float(rng.uniform(*cfg['t_report'])), t_response=float(rng.uniform(*cfg['t_response'])))


_B = None
def _init(path):
    global _B
    _B = json.load(open(path, encoding='utf-8'))

def _one(args):
    floor, sc, cfg = args
    t0 = time.time()
    try:
        M = fz.Model(_B, floor, sc, sc['prm']); M.run(cfg['t_end'], cfg['dt']); R = M.result()
    except Exception as e:
        return dict(ok=False, err=str(e), sc=sc)
    ta = sc['t_report'] + sc['t_response']
    k = int(np.searchsorted(R['t'], ta)); k = min(k, len(R['t']) - 1)
    fl = R['flags']; out = {}
    for i, r in enumerate(R['rooms']):
        out[r['id']] = dict(
            fo=bool(fl['flash'][i, :k + 1].any()),               # 도착 전 플래시오버 경과
            bd=bool(fl['backdraft'][i, k]),                      # 도착 시점 백드래프트 잠재
            fgi=bool(fl['fgi'][i, k]),                           # 도착 시점 FGI 잠재
            un=bool(fl['unten'][i, k]),                          # 도착 시점 피난 한계 초과
            z=r['z_int'][k], T=r['T_u'][k], O2=r['O2_u'][k], Yf=r['Yf_u'][k],
            bd_any=bool(fl['backdraft'][i, :k + 1].any()), fgi_any=bool(fl['fgi'][i, :k + 1].any()))
    hrr = R['HRR_kW']
    return dict(ok=R['ok'], sc=sc, ta=ta, rooms=out, hrr_peak=max(hrr), hrr_at=hrr[k],
                broken=R['window_broken'], sec=time.time() - t0,
                series={r['id']: dict(z=r['z_int'], T=r['T_u']) for r in R['rooms']}, t=R['t'], hrr=hrr,
                flame_L=R['flame_L'], fire=R['fire'])


def run(bpath, floor, cfg, fire_room=None, procs=2, fire_point=None, B=None, progress=None):
    B = B or json.load(open(bpath, encoding='utf-8'))
    if fire_point is not None:
        fire_room = fz.Model(B, floor, dict(fire_point=fire_point)).fire_info['room']
    rng = np.random.default_rng(cfg['seed'])
    jobs = [(floor, sample(B, floor, cfg, rng, fire_room, fire_point), cfg) for _ in range(cfg['n'])]
    with Pool(procs, initializer=_init, initargs=(bpath,)) as pool:
        res = []
        for k, r in enumerate(pool.imap(_one, jobs)):
            res.append(r)
            if progress: progress(k + 1, cfg['n'])
            if (k + 1) % 10 == 0: print(f'  {k+1}/{cfg["n"]}', flush=True)
    good = [r for r in res if r['ok']]
    ids = list(good[0]['rooms'].keys())
    names = {}
    M = fz.Model(B, floor, dict(fire_room=None))
    for n in M.nodes: names[n['id']] = n['name']
    agg = {}
    for i in ids:
        R = [g['rooms'][i] for g in good]
        z = np.array([x['z'] for x in R]); T = np.array([x['T'] for x in R])
        agg[i] = dict(name=names.get(i, i),
                      p_fire=float(np.mean([g['sc']['fire_room'] == i for g in good])),
                      p_flashover=float(np.mean([x['fo'] for x in R])),
                      p_backdraft=float(np.mean([x['bd'] for x in R])),
                      p_fgi=float(np.mean([x['fgi'] for x in R])),
                      p_untenable=float(np.mean([x['un'] for x in R])),
                      p_backdraft_any=float(np.mean([x['bd_any'] for x in R])),
                      p_fgi_any=float(np.mean([x['fgi_any'] for x in R])),
                      z_q=[float(np.percentile(z, q)) for q in (10, 50, 90)],
                      T_q=[float(np.percentile(T, q)) for q in (10, 50, 90)])
    # 발화 실 조건부 위험(발화 실에서 문 열 때)
    fr = dict(p_flashover=float(np.mean([g['rooms'][g['sc']['fire_room']]['fo'] for g in good if g['sc']['fire_room'] in g['rooms']] or [0])),
              p_backdraft=float(np.mean([g['rooms'][g['sc']['fire_room']]['bd'] for g in good if g['sc']['fire_room'] in g['rooms']] or [0])))
    # 대표 시계열: 발화 실 도착 시점 상부 온도 중앙값에 가장 가까운 표본
    Tf = np.array([g['rooms'].get(g['sc']['fire_room'], {}).get('T', 0) for g in good])
    rep = good[int(np.argmin(np.abs(Tf - np.median(Tf))))]
    worst = good[int(np.argmax(Tf))]
    def pack(g):
        return dict(sc={k: v for k, v in g['sc'].items() if k not in ('doors', 'windows')} |
                       dict(doors_open={k: v for k, v in g['sc']['doors'].items() if v > 0},
                            windows_open={k: v for k, v in g['sc']['windows'].items() if v > 0}),
                    ta=g['ta'], t=g['t'], hrr=g['hrr'], series=g['series'], broken=g['broken'],
                    flame_L=g['flame_L'], fire=g['fire'])
    return dict(floor=floor, n=len(good), n_fail=len(res) - len(good), cfg=cfg, fire_room_fixed=fire_room, fire_point=fire_point,
                rooms=agg, fire_room_risk=fr,
                ta_q=[float(np.percentile([g['ta'] for g in good], q)) for q in (10, 50, 90)],
                hrr_peak_q=[float(np.percentile([g['hrr_peak'] for g in good], q)) for q in (10, 50, 90)],
                sec_mean=float(np.mean([g['sec'] for g in good])),
                representative=pack(rep), worst=pack(worst),
                runs=[dict(fire_room=g['sc']['fire_room'], alpha=g['sc']['fire']['alpha'], ta=g['ta'],
                           hrr_peak=g['hrr_peak'], fd=[v for k, v in g['sc']['doors'].items()],
                           fr=g['rooms'].get(g['sc']['fire_room'])) for g in good])


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('building'); ap.add_argument('--floor', default='4F')
    ap.add_argument('--fire', default=None, help='발화 실 고정(없으면 무작위)')
    ap.add_argument('--point', default=None, help='화점 x,y 고정')
    ap.add_argument('--n', type=int, default=100); ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--cfg', help='분포 덮어쓰기 json'); ap.add_argument('--procs', type=int, default=2)
    ap.add_argument('-o', '--out', required=True)
    a = ap.parse_args()
    cfg = dict(DEF); cfg.update(n=a.n, seed=a.seed)
    if a.cfg: cfg.update(json.load(open(a.cfg, encoding='utf-8')))
    t0 = time.time()
    R = run(a.building, a.floor, cfg, a.fire, a.procs, [float(v) for v in a.point.split(',')] if a.point else None)
    json.dump(R, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f"표본 {R['n']} (실패 {R['n_fail']}) 총 {time.time()-t0:.0f}s, 1회 평균 {R['sec_mean']:.1f}s")
    print('도착 시각 분위(s):', [round(x) for x in R['ta_q']], ' 최대 HRR 분위(kW):', [round(x) for x in R['hrr_peak_q']])
    print('발화 실 위험:', R['fire_room_risk'])
    for i, r in R['rooms'].items():
        print(f"{i:>4} {r['name'][:8]:<8} 발화{r['p_fire']:.2f} FO{r['p_flashover']:.2f} BD{r['p_backdraft']:.2f}/{r['p_backdraft_any']:.2f}"
              f" FGI{r['p_fgi']:.2f}/{r['p_fgi_any']:.2f} 피난한계{r['p_untenable']:.2f} 연기층z50={r['z_q'][1]:.2f} T50={r['T_q'][1]:.0f}")
