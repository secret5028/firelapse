"""소방 도면 심볼 추출: 범례 블록을 템플릿으로, 모델공간 삽입 블록을 형상(축척·회전·대칭 불변)으로 분류.
출력: 블록 서명(pickle) — name → dict(img: 48x48 정규화 래스터, texts: 블록 안 문자 집합, size: 외접 크기)"""
import sys, math, pickle, collections
import numpy as np, cv2, ezdxf
from ezdxf import bbox as _bb

N = 48
def block_sig(doc, name, depth=0):
    b = doc.blocks.get(name)
    if b is None: return None
    segs, txt = [], set()
    def walk(ents, M=None, d=0):
        for e in ents:
            t = e.dxftype()
            if t in ('ATTDEF', 'ATTRIB', 'HATCH', 'SOLID', 'DIMENSION'): continue
            if t in ('TEXT', 'MTEXT'):
                try: s = (e.dxf.text if t == 'TEXT' else e.plain_text()).strip()
                except Exception: s = ''
                if s: txt.add(s.replace(' ', '')[:6])
                continue
            if t == 'INSERT' and d < 3:
                try: walk(e.virtual_entities(), d=d + 1)
                except Exception: pass
                continue
            try:
                if t == 'LINE': pts = [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
                elif t in ('ARC', 'CIRCLE', 'ELLIPSE', 'SPLINE', 'LWPOLYLINE', 'POLYLINE'):
                    from ezdxf import path as zp
                    pts = [(v.x, v.y) for v in zp.make_path(e).flattening(0.01 * max(1e-6, 1))] if t != 'ARC' and t != 'CIRCLE' else \
                          [(v.x, v.y) for v in e.flattening(max(e.dxf.radius / 30, 1e-6))]
                else: continue
            except Exception: continue
            if len(pts) >= 2: segs.append(pts)
    walk(b)
    if not segs: return dict(img=None, texts=txt, size=(0, 0))
    P = np.array([p for s in segs for p in s])
    lo, hi = P.min(0), P.max(0); c = (lo + hi) / 2; sz = hi - lo; S = max(sz.max(), 1e-9)
    img = np.zeros((N, N), np.uint8)
    for s in segs:
        q = np.int32([((x - c[0]) / S * (N - 8) + N / 2, N / 2 - (y - c[1]) / S * (N - 8)) for x, y in s])
        cv2.polylines(img, [q], False, 255, 1)
    return dict(img=img, texts=txt, size=tuple(sz))

def variants(img):
    out = []
    for f in (False, True):
        a = cv2.flip(img, 1) if f else img
        for k in range(4): out.append(np.rot90(a, k).copy())
    return out

def chamfer(a, b):
    # 대칭 챔퍼 거리(픽셀): a 선이 b 선에서 얼마나 떨어졌나
    da = cv2.distanceTransform((255 - a), cv2.DIST_L2, 3); db = cv2.distanceTransform((255 - b), cv2.DIST_L2, 3)
    pa, pb = a > 0, b > 0
    if not pa.any() or not pb.any(): return 99
    return 0.5 * (db[pa].mean() + da[pb].mean())

def match(sig, templ):
    """templ: dict(kind → sig). 반환 (kind, 점수). 문자 집합이 다르면 벌점."""
    if sig is None or sig['img'] is None: return None, 99
    best = (None, 99)
    for k, t in templ.items():
        if t['img'] is None: continue
        d = min(chamfer(v, t['img']) for v in variants(sig['img']))
        if t['texts'] != sig['texts']: d += 2.0
        # 가로세로비
        ra = sorted(sig['size']); rb = sorted(t['size'])
        if ra[1] > 0 and rb[1] > 0: d += 2 * abs(ra[0] / ra[1] - rb[0] / rb[1])
        if d < best[1]: best = (k, d)
    return best

if __name__ == '__main__':
    fn, out = sys.argv[1], sys.argv[2]
    doc = ezdxf.readfile(fn)
    used = collections.Counter(e.dxf.name for e in doc.modelspace().query('INSERT'))
    sigs = {n: block_sig(doc, n) for n in used}
    pickle.dump(sigs, open(out, 'wb'))
    print(len(sigs))
