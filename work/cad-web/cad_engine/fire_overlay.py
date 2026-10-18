"""소방 심볼 → 건축 평면 대조.
- 감지기: 실 안 개수 → 실 검증(감지기 없는 실 = 확인 대상, 화장실·샤프트 등 예외 후보)
- 피난구유도등: 정렬·실 소속·차폐·후보 경합을 확인한 뒤 개구부 분류 보조
- 통로유도등: 복도·통로 실 표시
입력: plan.json, fire inserts(pkl: I), block 분류(pkl), 시트 키, 이동량(dx,dy): fire = arch + (dx,dy)"""
import json, math, pickle, collections, sys, re
import numpy as np
from shapely.geometry import Polygon, Point, MultiPoint
from shapely.strtree import STRtree

KIND = {'det_smoke': 'detector', 'det_heat_rate': 'detector', 'det_heat_fixed': 'detector',
        'exit_sign': 'exit_sign', 'exit_sign2': 'exit_sign', 'corridor_light': 'corridor_light', 'hydrant_box': 'hydrant'}

def legend_boxes(T, x0, x1, y0, y1, dx, dy):
    """시트 안 범례 표(SYMBOL·범례 문자) 아래 영역 = 견본 기호 자리(건축 좌표 m). 범위: 문자 x-1.5~+9m, y-16~+0.5m(1:1 시트)"""
    out = []
    for t, ly, x, y, h in T:
        if x0 <= x < x1 and y0 <= y < y1 and re.fullmatch(r'\s*(SYMBOL|LEGEND|범\s*례)\s*', t or '', re.I):
            ax, ay = (x - dx) / 1000, (y - dy) / 1000
            out.append((ax - 1.5, ay - 16, ax + 9, ay + 0.5))
    return out

def symbols(I, cls, x0, x1, y0, y1, dx, dy, thr=0.4, legend=()):
    out = []
    for n, ly, x, y, r, sx, sy in I:
        if not (x0 <= x < x1 and y0 <= y < y1): continue
        k, sc = cls.get(n, (None, 99))
        if k is None or sc > thr or k not in KIND: continue
        ax, ay = (x - dx) / 1000, (y - dy) / 1000
        if any(b[0] <= ax <= b[2] and b[1] <= ay <= b[3] for b in legend): continue   # 범례 견본
        out.append(dict(kind=KIND[k], sub=k, block=n, x=round(ax, 3), y=round(ay, 3), rot=round(r, 1), score=round(sc, 2)))
    return out

def covered_spaces(plan, upper, shift, syms, min_area=2.0):
    """덮인 반실내 공간(필로티·캐노피 하부): (위층 바닥 ∩ 이 층 외부) 중 감지기가 있는 덩어리.
    근거 두 개(위층 바닥이 덮음 + 소방 설계자가 감지기를 둠)가 겹칠 때만 실로 추가."""
    from shapely.ops import unary_union
    from shapely import affinity
    from cad_evidence import geometry
    low = geometry(plan.get('footprint', []))
    up = geometry(upper.get('footprint', []))
    up = affinity.translate(up, shift[0] / 1000, shift[1] / 1000)
    U = up.difference(low.buffer(0.05))
    out = []
    for g in getattr(U, 'geoms', [U]):
        if g.is_empty or g.area < min_area: continue
        g = g.buffer(-0.15).buffer(0.15)   # 외곽선 사이 얇은 띠 제거
        for gg in getattr(g, 'geoms', [g]):
            if gg.is_empty or gg.area < min_area: continue
            det = [s_ for s_ in syms if s_['kind'] == 'detector' and gg.contains(Point(s_['x'], s_['y']))]
            if not det: continue
            c = gg.representative_point()
            out.append(dict(id=f'C{len(out)}', area=round(gg.area, 2), poly=[[round(x, 3), round(y, 3)] for x, y in gg.exterior.coords[:-1]],
                            center=[round(c.x, 3), round(c.y, 3)], tags=['covered'], names=[], detectors=len(det)))
    return out

def overlay(plan, syms, upper=None, shift=None, *, alignment_verified=False):
    from cad_evidence import analyze_fire
    result = analyze_fire(plan, syms, alignment_verified=alignment_verified)
    # Covered-space detections are evidence candidates, not automatically created rooms.
    if upper is not None and shift is not None:
        result['covered'] = covered_spaces(plan, upper, shift, syms)
        for room in result['covered']:
            result['checks'].append(dict(rule='F덮인공간-후보', id=room['id'],
                note='위층 바닥과 감지기 근거가 겹침. 외곽·벽 확인 전 실 자동 추가는 보류'))
    return result


if __name__ == '__main__':
    plan = json.load(open(sys.argv[1], encoding='utf-8'))
    I = pickle.load(open(sys.argv[2], 'rb'))['I']; cls = pickle.load(open(sys.argv[3], 'rb'))
    x0, x1, y0, y1, dx, dy = map(float, sys.argv[4:10])
    syms = symbols(I, cls, x0, x1, y0, y1, dx, dy)
    res = overlay(plan, syms)
    json.dump(res, open(sys.argv[10], 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(collections.Counter(s['sub'] for s in syms))
    print(collections.Counter(c['rule'] for c in res['checks']))
