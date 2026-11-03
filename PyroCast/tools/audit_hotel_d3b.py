"""Read-only D-3b geometry evidence. Does not repair a room, opening or label."""
from collections import Counter
import csv
import json
import math
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'simulation'),str(ROOT/'simulation/deps'),str(ROOT/'tools')]
from cad_connectivity_shared import geometry, opening_parts
from pyrocast_cfbt.cad import adapt
from run_lite_l1 import save

OUT=ROOT/'reviews/D3b-20261103'
BUILDING=ROOT/'data/parkmarine-hotel/building.json'


def main():
    building=json.loads(BUILDING.read_text('utf-8')); rows=[]
    for floor in building['floors']:
        shapes={r['id']:geometry(r['polys']) for r in floor['rooms']}
        doors=[(o,geometry(opening_parts(o))) for o in floor['openings'] if o['kind'].startswith('door')]
        for room in floor['rooms']:
            if room['id'] not in floor['simulation_graph']['isolated_rooms']:
                continue
            rid=room['id']; shape=shapes[rid]
            neighbors=sorted([(shape.intersection(s).area,k) for k,s in shapes.items() if k!=rid],reverse=True)
            overlap,other=neighbors[0]
            nearest=sorted([(shape.distance(g),o['id'],o) for o,g in doors],key=lambda v:(v[0],v[1]))[0]
            distance,_,door=nearest
            references=[o['id'] for o in floor['openings'] if rid in (o.get('sides') or [])]
            # Evidence grouping only. This regex does not change production classification.
            utility=bool(re.search(r'\b(PIT|DA|AD|EPS|TPS|AV|PS)\b|승강로|ELEV', ' / '.join(room['names']),re.I))
            if overlap>1e-6:
                category='overlapping_room_polygons'
            elif utility:
                category='utility_space_label_without_aperture'
            else:
                category='no_opening_side_assignment_other'
            rows.append(dict(floor=floor['name'],room=rid,labels=room['names'],tags=room.get('tags',[]),
                reported_area_m2=room['area'],polygon_area_m2=shape.area,category=category,
                raw_opening_references=references,nearest_door=door['id'],distance_m=distance,
                nearest_door_sides=door.get('sides'),nearest_door_status=door.get('connection_status'),
                max_overlap_room=other if overlap>1e-6 else None,max_overlap_m2=overlap,
                max_overlap_fraction=overlap/shape.area if shape.area else None,
                utility_label=utility))
    assert len(rows)==71
    loader=[]
    # Read-only exception tracing captures the actual adapter dimensions at failure.
    def trace(frame,event,arg):
        if event=='exception' and frame.f_code.co_name=='adapt' and Path(frame.f_code.co_filename).name=='cad.py':
            typ,exc,_=arg
            if typ is ValueError and str(exc).startswith('Opening wider than usable equivalent room:'):
                v=frame.f_locals; r=v['r']; b=v['bounds']; a=r['area_m2']
                natural=math.sqrt(a*(b[2]-b[0])/(b[3]-b[1]))
                initial=max(v['maxwidth'],natural)
                vents=[dict(id=o['id'],width_m=o['width_m'],kind=o['kind'],a=o['a'],b=o['b'])
                       for o in v['horizontal'] if v['k'] in (o['a'],o['b'])]
                loader.append(dict(room=v['k'],labels=r.get('cad_names'),area_m2=a,
                    cad_bbox_m=[b[2]-b[0],b[3]-b[1]],height_m=r['height_m'],
                    natural_equivalent_width_m=natural,initial_equivalent_size_m=[initial,a/initial],
                    fallback_size_m=[v['width'],v['depth']],required_width_with_margin_m=v['maxwidth'],
                    widest_opening=max(vents,key=lambda o:o['width_m']),openings=vents,error=str(exc)))
        return trace
    for floor in ('B1','1F','2F','3F'):
        sys.settrace(trace)
        try:
            adapt(ROOT,dict(building_path=str(BUILDING),fire_floor=floor,scope_floor=floor,fire_room='R0'))
        except ValueError as exc:
            if not str(exc).startswith('Opening wider than usable equivalent room:'):
                raise
        finally:
            sys.settrace(None)
    assert len(loader)==4
    save(OUT/'isolation-audit.json',dict(counts=dict(Counter(r['category'] for r in rows)),rows=rows,
        no_raw_side_reference_count=sum(not r['raw_opening_references'] for r in rows),
        caveat='Evidence classes, not proven CAD-recognition root causes. Labels do not directly create/delete graph links. Wall lines were not reinterpreted.',
        grouping='priority: polygon overlap > 1e-6 m²; else utility label; else no side assignment'))
    save(OUT/'loader-dimensions.json',loader)
    with (OUT/'isolated-rooms.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print(json.dumps(dict(counts=dict(Counter(r['category'] for r in rows)),loader=loader),ensure_ascii=False))


if __name__=='__main__':main()
