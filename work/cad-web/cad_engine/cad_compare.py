"""원본 CAD ↔ 처리 결과 대조 HTML.
python cad_compare.py <결과폴더(out\\관리번호)> [--map layer_map.json]
결과폴더의 nF.json(src·raster 정보)과 dxf\\ 원본으로 같은 좌표의 원본 그림을 만들고 nF_plan.png 와 나란히/겹치기/스와이프로 비교."""
import collections, sys, os, re, json, glob, base64, argparse
import numpy as np, cv2
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cadio import load, units_to_m
from cad_plan import LayerMap, DASHED

COL = {  # BGR
    'wall': (0, 0, 0), 'column': (0, 0, 170), 'window': (230, 120, 0), 'door': (0, 160, 0),
    'stair': (200, 0, 200), 'elev': (190, 160, 0), 'other': (175, 175, 175), 'ignore': (215, 215, 215)}
ORDER = ['ignore', 'other', 'stair', 'elev', 'window', 'door', 'column', 'wall']


def render_original(dxf, js, lm):
    r = json.load(open(js, encoding='utf-8'))
    ra = r['raster']; R, x0, y1, W, H = ra['R'], ra['x0'], ra['y1'], ra['W'], ra['H']
    doc, prims, _ = load(dxf)
    k = units_to_m(doc, prims) * 1000
    img = np.full((H, W, 3), 255, np.uint8)
    hid = np.zeros((H, W), np.uint8)
    cats = [lm.cat(p.layer) for p in prims]
    for c0 in ORDER:
        for p, c in zip(prims, cats):
            if c != c0: continue
            q = np.int32([[(x * k - x0) / R, (y1 - y * k) / R] for x, y in p.pts])
            if DASHED.search(p.lt) and c in ('wall', 'window', 'column'):
                cv2.polylines(hid, [q], p.closed, 255, 2, cv2.LINE_AA); continue
            w = 1 if c in ('ignore', 'other') else 2
            cv2.polylines(img, [q], p.closed, COL[c], w, cv2.LINE_AA)
    # 숨은선(제외된 벽·창 선) = 주황 점선 느낌
    yy, xx = np.nonzero(hid)
    sel = ((xx // 6 + yy // 6) % 2) == 0
    img[yy[sel], xx[sel]] = (0, 140, 255)
    return img, r


def b64(img, q=None):
    ok, buf = cv2.imencode('.png', img, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    return 'data:image/png;base64,' + base64.b64encode(buf).decode()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('outdir'); ap.add_argument('--map', default=os.path.join(HERE, 'layer_map.json'))
    ap.add_argument('--maxw', type=int, default=3200)
    a = ap.parse_args()
    lm = LayerMap(a.map)
    B = json.load(open(os.path.join(a.outdir, 'building.json'), encoding='utf-8')) if os.path.exists(os.path.join(a.outdir, 'building.json')) else None
    names = [f['name'] for f in B['floors']] if B else sorted(os.path.splitext(os.path.basename(f))[0] for f in glob.glob(os.path.join(a.outdir, '*F.json')))
    floors = []
    for n in names:
        js = os.path.join(a.outdir, n + '.json')
        r0 = json.load(open(js, encoding='utf-8'))
        dxf = os.path.join(a.outdir, 'dxf', r0['src'])
        if not os.path.exists(dxf):
            cand = glob.glob(os.path.join(a.outdir, 'dxf', '*' + os.path.splitext(r0['src'])[0][-8:] + '*'))
            if not cand: print('원본 없음', n); continue
            dxf = cand[0]
        orig, r = render_original(dxf, js, lm)
        proc = cv2.imread(os.path.join(a.outdir, n + '_plan.png'))
        s = min(1.0, a.maxw / orig.shape[1])
        if s < 1:
            orig = cv2.resize(orig, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
            proc = cv2.resize(proc, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        ra = r['raster']
        T = lambda xy: [round((xy[0] - ra['x0']) / ra['R'] * s, 1), round((ra['y1'] - xy[1]) / ra['R'] * s, 1)]
        marks = []
        for f in r['heal']['flags']:
            marks.append(dict(t='틈:' + {'dangling': '열린 끝', 'gap_unlabeled': '문기호 없는 틈', 'gap_zone_size': '문 폭 불일치',
                                         'gap_envelope_closed': '외곽 틈 닫음'}.get(f['kind'], f['kind']),
                              d=f"{f.get('layer', '')} {f.get('width', '') or ''}".strip(), p=T(f['at'])))
        op = {o['id']: o for o in r['openings']}
        rm = {x['id']: x for x in r['rooms']}
        for c in r['checks']:
            p = None
            if c.get('id') in op and op[c['id']]['polys']:
                pp = np.array(op[c['id']]['polys'][0]).mean(0) * 1000; p = T(pp)
            elif c.get('id') in rm:
                p = T(np.array(rm[c['id']]['center']) * 1000)
            marks.append(dict(t=c['rule'], d=f"{c.get('id', '')} {c.get('note', '')}", p=p))
        # 소방 심볼 대조(있으면): 결과 그림 위에 감지기·유도등·소화전 표시 → 세 번째 화면
        g = None; fj = os.path.join(a.outdir, n + '_fire.json')
        if os.path.exists(fj):
            fr = json.load(open(fj, encoding='utf-8'))
            gi = proc.copy(); rr = max(6, int(10 * s * 2))
            for cv_ in fr.get('covered', []):   # 덮인 반실내 공간: 사선 빗금 + 테두리
                q = np.int32([T((x * 1000, y * 1000)) for x, y in cv_['poly']])
                ov = gi.copy(); cv2.fillPoly(ov, [q], (170, 200, 230)); gi = cv2.addWeighted(ov, 0.5, gi, 0.5, 0)
                cv2.polylines(gi, [q], True, (60, 100, 160), 2)
                cc = [int(t) for t in T((cv_['center'][0] * 1000, cv_['center'][1] * 1000))]
                cv2.putText(gi, cv_['id'], tuple(cc), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (40, 60, 120), 1)
            for sy in fr['symbols']:
                u, v = [int(t) for t in T((sy['x'] * 1000, sy['y'] * 1000))]
                if sy['kind'] == 'detector': cv2.circle(gi, (u, v), rr, (0, 0, 230), 3)
                elif sy['kind'] == 'exit_sign' and sy.get('role') == 'corridor_guide':
                    cv2.rectangle(gi, (u - rr, v - rr), (u + rr, v + rr), (0, 150, 0), 3); cv2.drawMarker(gi, (u, v), (230, 90, 0), cv2.MARKER_TRIANGLE_UP, rr, 2)
                elif sy['kind'] == 'exit_sign': cv2.rectangle(gi, (u - rr, v - rr), (u + rr, v + rr), (0, 150, 0), -1)
                elif sy['kind'] == 'corridor_light': cv2.drawMarker(gi, (u, v), (230, 90, 0), cv2.MARKER_TRIANGLE_UP, 2 * rr, 3)
                elif sy['kind'] == 'hydrant': cv2.rectangle(gi, (u - rr, v - rr), (u + rr, v + rr), (0, 140, 255), 3)
            g = b64(gi)
            for c2 in fr['checks']:
                p = None
                if c2.get('at'): p = T((c2['at'][0] * 1000, c2['at'][1] * 1000))
                elif c2.get('id') in op and op[c2['id']]['polys']: p = T(np.array(op[c2['id']]['polys'][0]).mean(0) * 1000)
                elif c2.get('id') in rm: p = T(np.array(rm[c2['id']]['center']) * 1000)
                marks.append(dict(t=c2['rule'], d=f"{c2.get('id', '') or ''} {c2.get('area', '') or ''} {c2.get('note', '')}", p=p))
            cnt = collections.Counter(sy['kind'] for sy in fr['symbols'])
        bf = next((f for f in B['floors'] if f['name'] == n), None) if B else None
        info = dict(rooms=len(r['rooms']), stats=r['stats'], heal=r['heal']['summary']['ops'],
                    use=bf and bf.get('use'), h=bf and bf.get('h'), ceil=bf and bf.get('ceil_h'), align=bf and bf.get('align'))
        fd = dict(name=n, src=r0['src'], w=orig.shape[1], h=orig.shape[0], o=b64(orig), p=b64(proc), marks=marks, info=info)
        if g: fd.update(g=g, gname='결과 + 소방 심볼', fire={k: int(v) for k, v in cnt.items()})
        floors.append(fd)
        print(n, orig.shape, len(marks))
    html = open(os.path.join(HERE, 'compare_template.html'), encoding='utf-8').read()
    title = os.path.basename(os.path.normpath(a.outdir))
    out = os.path.join(a.outdir, 'compare.html')
    open(out, 'w', encoding='utf-8').write(html.replace('__TITLE__', title).replace('/*__DATA__*/null', json.dumps(floors, ensure_ascii=False)))
    print('→', out)


if __name__ == '__main__':
    main()
