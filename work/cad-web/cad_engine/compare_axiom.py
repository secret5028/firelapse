"""원본 / 레이어+공리 / 형상(레이어 무관) 3자 대조 HTML.
python compare_axiom.py 출력.html  이름 dxf 레이어결과접두어 형상결과접두어 [이름 dxf ...]"""
import sys, os, json
import numpy as np, cv2
from shapely.geometry import Polygon
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from cad_compare import render_original, b64
from cad_plan import LayerMap

def render_geo(gj, ra):
    g = json.load(open(gj, encoding='utf-8'))
    R, x0, y1, W, H = ra['R'], ra['x0'], ra['y1'], ra['W'], ra['H']
    T = lambda pts: np.int32([[(x - x0) / R, (y1 - y) / R] for x, y in pts])
    img = np.full((H, W, 3), 255, np.uint8)
    rng = np.random.default_rng(11)
    for r in g['rooms']:
        col = tuple(int(c) for c in rng.integers(170, 245, 3)) if r['has'] else (200, 200, 255)
        cv2.fillPoly(img, [T(r['poly'])], col)
    lab = np.load(gj.replace('_georooms.json', '_georooms_lab.npy'))
    gr = g['raster']
    # 벽 몸체 = 형상 결과에서 실도 외부도 아닌 곳(=0) → 레이어 결과 좌표로 옮겨 그림
    ys, xs = np.nonzero(lab == 0)
    X = xs * gr['R'] + gr['x0']; Y = gr['y1'] - ys * gr['R']
    u = ((X - x0) / R).astype(int); v = ((y1 - Y) / R).astype(int)
    ok = (u >= 0) & (u < W) & (v >= 0) & (v < H)
    inside = np.zeros((H, W), bool); inside[v[ok], u[ok]] = True
    # 바깥(-1)은 흰색 유지, 벽 몸체만 회색(바깥과 구분: 실 경계 3px 안만)
    rooms_mask = (img != 255).any(2)
    near_room = cv2.dilate(rooms_mask.astype(np.uint8), np.ones((15, 15), np.uint8)) > 0
    img[inside & near_room & ~rooms_mask] = (60, 60, 60)
    for d in g['doors']: cv2.line(img, tuple(T([d['seg'][:2]])[0]), tuple(T([d['seg'][2:]])[0]), (0, 170, 0), 3)
    for d in g['doors_unseparated']:
        c = T([[(d['seg'][0] + d['seg'][2]) / 2, (d['seg'][1] + d['seg'][3]) / 2]])[0]
        cv2.drawMarker(img, tuple(c), (255, 0, 255), cv2.MARKER_TILTED_CROSS, 22, 3)
    for w in g['windows']:
        cv2.fillPoly(img, [T(w['quad'])], (255, 120, 0) if w['ext'] else (200, 200, 0))
    for l in g['restored_lines']: cv2.polylines(img, [T(l)], False, (0, 140, 255), 3)
    for r in g['rooms']:
        c = np.array(Polygon(r['poly']).representative_point().coords[0])
        uu, vv = T([c])[0]; cv2.putText(img, r['id'], (int(uu) - 12, int(vv) + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
    return img, g

def main():
    out = sys.argv[1]; a = sys.argv[2:]
    lm = LayerMap(os.path.join(HERE, 'layer_map.json'))
    floors = []
    for i in range(0, len(a), 4):
        name, dxf, hyb, geo = a[i:i + 4]
        orig, r = render_original(dxf, hyb + '.json', lm)
        proc = cv2.imread(hyb + '_plan.png')
        gimg, g = render_geo(geo + '_georooms.json', r['raster'])
        s = min(1.0, 3200 / orig.shape[1])
        rs = lambda im: cv2.resize(im, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else im
        orig, proc, gimg = rs(orig), rs(proc), rs(gimg)
        ra = r['raster']; T = lambda xy: [round((xy[0] - ra['x0']) / ra['R'] * s, 1), round((ra['y1'] - xy[1]) / ra['R'] * s, 1)]
        marks = []
        for c in r['checks']:
            op = {o['id']: o for o in r['openings']}; rm = {x['id']: x for x in r['rooms']}
            p = None
            if c.get('id') in op and op[c['id']]['polys']: p = T(np.array(op[c['id']]['polys'][0]).mean(0) * 1000)
            elif c.get('id') in rm: p = T(np.array(rm[c['id']]['center']) * 1000)
            elif c.get('at'): p = T(c['at'])
            marks.append(dict(t='[레이어+공리] ' + c['rule'], d=f"{c.get('id', '')} {c.get('note', '')}", p=p))
        for d in g['doors_unseparated']:
            marks.append(dict(t='[형상] 문 양쪽 같은 면', d='', p=T([(d['seg'][0] + d['seg'][2]) / 2, (d['seg'][1] + d['seg'][3]) / 2])))
        for rr in g['rooms']:
            if not rr['has']:
                c = Polygon(rr['poly']).representative_point().coords[0]
                marks.append(dict(t='[형상] 문·창 없는 실', d=f"{rr['id']} {rr['area']}㎡", p=T(c)))
        vs = g.get('vs_layer') or {}
        info = dict(rooms=len(r['rooms']), stats=r['stats'], heal=dict(형상_실=len(g['rooms']), 형상_문=g['stats']['doors_ok'], 형상_창=g['stats']['windows_ok'],
                    일치=vs.get('matched_iou50')), use=None)
        floors.append(dict(name=name, src=os.path.basename(dxf), w=orig.shape[1], h=orig.shape[0], o=b64(orig), p=b64(proc), g=b64(gimg), marks=marks, info=info))
    html = open(os.path.join(HERE, 'compare_template.html'), encoding='utf-8').read()
    html = html.replace('__TITLE__', '레이어+공리 vs 형상')
    open(out, 'w', encoding='utf-8').write(html.replace('/*__DATA__*/null', json.dumps(floors, ensure_ascii=False)))
    print('→', out)

if __name__ == '__main__':
    main()
