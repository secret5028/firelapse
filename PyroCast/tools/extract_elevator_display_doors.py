"""Read CAD sliding-door panel pairs. Display evidence only; never edit simulation input.

Requires the existing CAD cadio reader (ezdxf) and shapely. The output is keyed by
the exact building hash. Unknown/ambiguous symbols remain unresolved, not guessed.
"""
import argparse, hashlib, json, math, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def panel_rect(points):
    from shapely.geometry import Polygon
    if len(points) < 4:
        return None
    poly = Polygon(points)
    if not poly.is_valid or poly.area <= 0:
        return None
    box = poly.minimum_rotated_rectangle
    q = list(box.exterior.coords)[:4]
    edges = [(math.dist(q[i], q[(i+1)%4]), q[i], q[(i+1)%4]) for i in range(4)]
    width, a, b = max(edges)
    depth = min(e[0] for e in edges)
    if not (.5 <= width <= 2.5 and .015 <= depth <= .12 and width/depth >= 8 and poly.area/box.area > .96):
        return None
    tangent = [(b[i]-a[i])/width for i in (0, 1)]
    return dict(center=[box.centroid.x, box.centroid.y], width=width, depth=depth, tangent=tangent)


def detect_panels(rows, core):
    panels = []
    for r in rows:
        if r.get('arc') or not r.get('closed'):
            continue
        p = panel_rect(r['points'])
        if p and abs(p['center'][0]-core['x']) <= core['w']/2+.7 and abs(p['center'][1]-core['y']) <= core['h']/2+.7:
            panels.append({**p, 'source': r['source']})
    candidates = []
    for i, a in enumerate(panels):
        for b in panels[i+1:]:
            t = a['tangent']; n = [-t[1], t[0]]
            d = [b['center'][j]-a['center'][j] for j in (0, 1)]
            dot = lambda v, w: sum(x*y for x, y in zip(v, w))
            if abs(dot(t, b['tangent'])) < .995 or abs(a['width']-b['width']) > .08 or abs(dot(d, t)) > .06 or not (.06 <= abs(dot(d, n)) <= .35):
                continue
            c = [(a['center'][j]+b['center'][j])/2 for j in (0, 1)]
            toward = [c[0]-core['x'], c[1]-core['y']]
            if abs(dot(toward, n)) < .25:
                continue
            if dot(toward, n) < 0:
                n = [-v for v in n]
            outer = max((a, b), key=lambda p: dot(p['center'], n))
            c = outer['center']; width = min(a['width'], b['width'])
            span = [[round(c[j]+s*t[j]*width/2, 5) for j in (0, 1)] for s in (-1, 1)]
            if any(math.dist(c, v['center']) < .15 for v in candidates):
                continue
            candidates.append(dict(center=c, span=span, normal=[round(v, 5) for v in n], source=[a['source'], b['source']]))
    return candidates


def extract(building_path, drawings, reader, out):
    sys.path.insert(0, str(reader))
    from cadio import load, units_to_m
    building = json.loads(building_path.read_text('utf8'))
    source_sha = hashlib.sha256(building_path.read_bytes()).hexdigest()
    result = dict(building_sha256=source_sha, scope='display_only', floors=[], unresolved=[])
    out.mkdir(parents=True, exist_ok=True)
    for floor in building['floors']:
        # Original per-floor records can be supplied by the model, otherwise use
        # its source shaft membership. Nothing is extended to an unrecorded floor.
        cores = [dict(c) for c in building.get('source_shafts', building.get('shafts', [])) if c['kind']=='elev' and floor['name'] in c.get('floors', [])]
        if not cores:
            continue
        path = drawings/Path(floor['src']).name
        if not path.exists():
            result['unresolved'].append(dict(floor=floor['name'], reason='source_dxf_missing'));continue
        print('CAD', floor['name'], flush=True)
        doc, prims, inserts = load(str(path)); unit = units_to_m(doc, prims)
        def xy(p):
            return [p[i]*unit*floor.get('scale', 1)+floor.get('shift', [0, 0])[i]-building.get('origin', [0, 0])[i] for i in (0, 1)]
        rows = [dict(points=[xy(q) for q in p.pts], closed=p.closed, arc=bool(p.arc), source=dict(layer=p.layer, insertion=p.ins, primitive=i, block=inserts[p.ins]['name'] if p.ins is not None else None)) for i, p in enumerate(prims)]
        doors = []
        for i, core in enumerate(cores):
            candidates = detect_panels(rows, core)
            if len(candidates) != 1:
                result['unresolved'].append(dict(floor=floor['name'], core=[core['x'], core['y']], reason='panel_pair_ambiguous_or_missing', candidates=len(candidates)));continue
            c = candidates[0]
            doors.append(dict(id=f'CAD_EV_PANEL_{i}', kind='door_elev', display_frame=True, display_only=True, display_span=c['span'], door_h=floor.get('door_h', 2.1), height_basis='floor door-height assumption, not elevation drawing', operation='sliding', connection_status='display_only', normal=c['normal'], source=c['source'], core=[core['x'],core['y']], evidence='two parallel thin sliding-door panels in original CAD', polys=[]))
        result['floors'].append(dict(floor=floor['name'], source_dxf=path.name, source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), doors=doors))
        # Local CAD context for visual review; not synthetic door evidence.
        from PIL import Image, ImageDraw
        for i, core in enumerate(cores):
            x0,y0=core['x']-2,core['y']-2;scale=170
            im=Image.new('RGB',(680,680),'white');draw=ImageDraw.Draw(im)
            for row in rows:
                q=row['points']
                if len(q)<2 or max(p[0] for p in q)<x0 or min(p[0] for p in q)>x0+4 or max(p[1] for p in q)<y0 or min(p[1] for p in q)>y0+4:continue
                draw.line([((p[0]-x0)*scale,(y0+4-p[1])*scale) for p in q],fill='#777777',width=1)
            for door in doors:
                if door['core']!=[core['x'],core['y']]:continue
                draw.line([((p[0]-x0)*scale,(y0+4-p[1])*scale) for p in door['display_span']],fill='#0078c4',width=4)
            im.save(out/f"{floor['name']}-elevator-{i}.png")
    (out/'evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(dict(doors=sum(len(f['doors']) for f in result['floors']), unresolved=result['unresolved']), ensure_ascii=False), flush=True)
    return result


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--building',type=Path,required=True);p.add_argument('--drawings',type=Path,required=True);p.add_argument('--reader',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    extract(a.building,a.drawings,a.reader,a.out)
