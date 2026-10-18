"""DXF 읽기: 블록·외부참조 전개 → 원시요소(선분열) + 블록 삽입 기록.
레이어: 블록 내부 '0' 레이어는 삽입 레이어 상속, 외부참조 결합 접두어(xxx$0$)는 떼서 base로 둠."""
import math, re, ezdxf
from ezdxf import path as zpath

XREF = re.compile(r'^.*?\$\d+\$')


def base_layer(name):
    return XREF.sub('', name).upper().strip()


class Prim:
    __slots__ = ('layer', 'raw', 'kind', 'pts', 'closed', 'ins', 'arc', 'lt', 'source')

    def __init__(s, layer, raw, kind, pts, closed, ins, arc=None, lt='CONTINUOUS'):
        s.layer, s.raw, s.kind, s.pts, s.closed, s.ins, s.arc, s.lt = layer, raw, kind, pts, closed, ins, arc, lt
        s.source = {}


def _wcs_arc(e, cx, cy, r, a0, a1):
    # 대칭(mirror) 삽입 블록의 호는 OCS(돌출 방향 -Z)로 들어옴 → WCS 중심·각도로 변환. 결과는 항상 반시계 a0→a1
    try:
        ex = e.dxf.extrusion
    except Exception:
        ex = None
    if ex is None or abs(ex.z - 1) < 1e-9:
        return (cx, cy, r, a0, a1)
    ocs = e.ocs(); z = e.dxf.get('elevation', 0) if e.dxftype() == 'LWPOLYLINE' else 0
    if hasattr(z, 'z'): z = z.z
    C = ocs.to_wcs((cx, cy, z))
    P0 = ocs.to_wcs((cx + r * math.cos(math.radians(a0)), cy + r * math.sin(math.radians(a0)), z))
    P1 = ocs.to_wcs((cx + r * math.cos(math.radians(a1)), cy + r * math.sin(math.radians(a1)), z))
    w0 = math.degrees(math.atan2(P0.y - C.y, P0.x - C.x)); w1 = math.degrees(math.atan2(P1.y - C.y, P1.x - C.x))
    if ex.z < 0: w0, w1 = w1, w0          # 뒤집힌 평면: 회전 방향 반대
    return (C.x, C.y, r, w0 % 360, w1 % 360)


def _flat(e):
    t = e.dxftype()
    if t == 'LINE':
        return [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)], False, None
    if t in ('LWPOLYLINE', 'POLYLINE'):
        try:
            p = [(v.x, v.y) for v in zpath.make_path(e).flattening(5)]
        except Exception:
            return None
        cl = e.closed if t == 'LWPOLYLINE' else e.is_closed
        arc = None
        if t == 'LWPOLYLINE':   # 볼록(bulge) 구간 = 호 → 가장 큰 호를 대표로 기록(문 판정용)
            try:
                from ezdxf.math import bulge_to_arc
                pts = list(e.get_points('xyb'))
                n = len(pts)
                for i in range(n if cl else n - 1):
                    x, y, b = pts[i]; x2, y2, _ = pts[(i + 1) % n]
                    if abs(b) > 1e-6:
                        c, a0, a1, r = bulge_to_arc((x, y), (x2, y2), b)
                        cand = _wcs_arc(e, c.x, c.y, r, math.degrees(a0), math.degrees(a1))
                        if arc is None or r > arc[2]: arc = cand
            except Exception:
                arc = None
        return p, cl, arc
    if t == 'ARC':
        c = e.dxf.center
        a = _wcs_arc(e, c.x, c.y, e.dxf.radius, e.dxf.start_angle, e.dxf.end_angle)
        return [(v.x, v.y) for v in e.flattening(max(e.dxf.radius / 20, 1e-6))], False, a
    if t == 'CIRCLE':
        return [(v.x, v.y) for v in e.flattening(max(e.dxf.radius / 20, 1e-6))], True, None
    if t in ('SPLINE', 'ELLIPSE'):
        try:
            return [(v.x, v.y) for v in zpath.make_path(e).flattening(5)], False, None
        except Exception:
            return None
    return None


def load(fn, maxdepth=8, diagnostics=None):
    doc = ezdxf.readfile(fn)
    msp = doc.modelspace()
    prims, inserts = [], []
    diagnostics = diagnostics if diagnostics is not None else []

    LT = {}
    for l in doc.layers:
        LT[l.dxf.name] = (l.dxf.get('linetype', 'CONTINUOUS') or 'CONTINUOUS').upper()

    def walk(e, inh_layer, ins_id, depth, inh_lt='CONTINUOUS'):
        t = e.dxftype()
        lay = e.dxf.layer if e.dxf.layer != '0' or inh_layer is None else inh_layer
        lt = (e.dxf.get('linetype', 'BYLAYER') or 'BYLAYER').upper()
        if lt == 'BYLAYER': lt = LT.get(lay, 'CONTINUOUS')
        elif lt == 'BYBLOCK': lt = inh_lt
        if t == 'INSERT':
            if e.mcount > 1:
                for instance in e.multi_insert():
                    walk(instance, inh_layer, ins_id, depth, inh_lt)
                return
            if depth >= maxdepth:
                diagnostics.append(dict(kind='block_depth', block=e.dxf.name))
                return
            iid = len(inserts)
            try:
                ins = e.dxf.insert
                inserts.append(dict(id=iid, name=e.dxf.name, layer=base_layer(lay), raw=lay,
                                    x=ins.x, y=ins.y, rot=e.dxf.get('rotation', 0),
                                    sx=e.dxf.get('xscale', 1), sy=e.dxf.get('yscale', 1),
                                    parent=ins_id, depth=depth))
                block = doc.blocks.get(e.dxf.name)
                if block is None or (block.block.is_xref and not len(block)):
                    diagnostics.append(dict(kind='unresolved_block', block=e.dxf.name))
                def skipped(entity, reason):
                    diagnostics.append(dict(kind='block_entity_skipped', block=e.dxf.name,
                                            entity=entity.dxftype(), reason=str(reason)))
                for v in e.virtual_entities(skipped_entity_callback=skipped):
                    walk(v, lay, iid, depth + 1, lt)
            except Exception as exc:
                diagnostics.append(dict(kind='block_error', block=e.dxf.name, reason=str(exc)))
            return
        r = _flat(e)
        if not r or len(r[0]) < 2:
            if t in ('LINE','LWPOLYLINE','POLYLINE','ARC','CIRCLE','SPLINE','ELLIPSE'):
                diagnostics.append(dict(kind='geometry_skipped',entity=t,layer=lay,handle=e.dxf.get('handle')))
            return
        pts, cl, arc = r
        primitive = Prim(base_layer(lay), lay, t, pts, cl, ins_id, arc, lt)
        primitive.source = dict(handle=e.dxf.get('handle'), insertion=ins_id)
        prims.append(primitive)

    for e in msp:
        walk(e, None, None, 0)
    # 선종류 정의에 끊김 무늬가 있으면(숨은선·중심선·점선 등, 이름과 무관) 'DASHED:' 표시
    pat = {}
    for lt_ in doc.linetypes:
        nm = lt_.dxf.name.upper()
        try: ptn = lt_.simplified_line_pattern()
        except Exception: ptn = []
        pat[nm] = bool(ptn) and any(abs(x) > 1e-9 for x in ptn[1:]) if len(ptn) > 1 else False
    for p in prims:
        p.lt = p.lt if p.lt else 'CONTINUOUS'
        if pat.get(p.lt.upper()): p.lt = 'DASHED:' + p.lt
    return doc, prims, inserts


def units_to_m(doc, prims):
    u = doc.header.get('$INSUNITS', 0)
    m = {1: 0.0254, 2: 0.3048, 4: 0.001, 5: 0.01, 6: 1.0}.get(u)
    if m:
        return m
    xs = [p[0] for q in prims for p in q.pts]
    span = max(xs) - min(xs) if xs else 0
    return 0.001 if span > 2000 else 1.0
