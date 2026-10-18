"""건물 전 층 소방 대조: 층 평면(json) + 소방 DWG 추출물(I·T pkl, 블록 분류 pkl) → <층>_fire.json
시트 배치: 층 순서대로 x 방향 sheet_dx 간격, 줄(row)별 y 범위(화재경보/유도등). 정렬은 기둥 번호 블록 우선."""
import sys, os, re, json, pickle, collections, argparse
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from cadio import load
from fire_align import align_blocks
from fire_overlay import symbols, overlay, legend_boxes
base = lambda n: n.split('$')[-1]
BUB = re.compile(r'COLBUB|기둥|축렬')

def bubbles_plan(dxf):
    _, _, I = load(dxf); A = collections.defaultdict(list)
    for i in I:
        if BUB.search(i['name']): A[base(i['name'])].append((i['x'], i['y']))
    return A

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('outdir'); ap.add_argument('--fire', required=True, help='I·T pkl'); ap.add_argument('--cls', required=True)
    ap.add_argument('--x0', type=float, required=True); ap.add_argument('--dx', type=float, required=True)
    ap.add_argument('--rows', required=True, help='y0:y1:종류,... (종류 fa=화재경보, ex=유도등)')
    a = ap.parse_args()
    J = pickle.load(open(a.fire, 'rb')); I, T = J['I'], J['T']; cls = pickle.load(open(a.cls, 'rb'))
    B = json.load(open(os.path.join(a.outdir, 'building.json'), encoding='utf-8'))
    names = [f['name'] for f in B['floors']]
    rows = [(float(r.split(':')[0]), float(r.split(':')[1]), r.split(':')[2]) for r in a.rows.split(',')]
    bub = {}
    for n in names:
        src = json.load(open(os.path.join(a.outdir, n + '.json'), encoding='utf-8'))['src']
        bub[n] = bubbles_plan(os.path.join(a.outdir, 'dxf', src))
    for k, n in enumerate(names):
        plan = json.load(open(os.path.join(a.outdir, n + '.json'), encoding='utf-8'))
        x0 = a.x0 + a.dx * k; syms = []; al = {}
        for y0, y1, kind in rows:
            F = collections.defaultdict(list)
            for i in I:
                if x0 <= i[2] < x0 + a.dx and y0 <= i[3] < y1 and BUB.search(i[0]): F[base(i[0])].append((i[2], i[3]))
            r = align_blocks(bub[n], F)
            al[kind] = r
            if not r: continue
            lg = legend_boxes(T, x0, x0 + a.dx, y0, y1, r[0], r[1])
            s = symbols(I, cls, x0, x0 + a.dx, y0, y1, r[0], r[1], legend=lg)
            keep = ('detector', 'hydrant') if kind == 'fa' else ('exit_sign', 'corridor_light')
            for t in s: t['sheet'] = kind
            syms += [t for t in s if t['kind'] in keep]
        up = None
        if k + 1 < len(names):
            d_ = align_blocks(bub[names[k + 1]], bub[n])
            if d_: up = (json.load(open(os.path.join(a.outdir, names[k + 1] + '.json'), encoding='utf-8')), (d_[0], d_[1]))
        res = overlay(plan, syms, up[0] if up else None, up[1] if up else None,
                      alignment_verified=bool(al) and all(v is not None and v[2] >= 4 and v[3] <= 50 for v in al.values()))
        res['align'] = {kk: (None if v is None else [round(v[0], 1), round(v[1], 1), v[2], round(v[3], 2)]) for kk, v in al.items()}
        json.dump(res, open(os.path.join(a.outdir, n + '_fire.json'), 'w', encoding='utf-8'), ensure_ascii=False)
        cnt = collections.Counter(s['kind'] for s in res['symbols'])
        nodet = [c for c in res['checks'] if c['rule'] == 'F실-감지기없음' and '예외 후보' not in c['note']]
        print(n, '정렬', {kk: (v[2] if v else None) for kk, v in al.items()}, dict(cnt), '덮인', len(res['covered']), '근거없는 무감지실', len(nodet))

if __name__ == '__main__':
    main()
