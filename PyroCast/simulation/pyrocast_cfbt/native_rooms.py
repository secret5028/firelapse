"""CFAST uses physical rooms; virtual sampling cells are not extra compartments.

Keep every prescribed fire curve and target position. Coalesce only the cells
created by rule_cells.partition; never merge across a physical parent room.
"""
from copy import deepcopy
import math

REVISION='native_physical_rooms_v1'

def coalesce(model, targets, manifest):
    m=deepcopy(model);targets=deepcopy(targets);manifest=deepcopy(manifest)
    old={r['id']:r for r in m['rooms']}
    mapping={rid:r.get('parent_room',rid) for rid,r in old.items()}
    rooms={}
    for parent in dict.fromkeys(mapping.values()):
        cells=[r for rid,r in old.items() if mapping[rid]==parent]
        origin=[min(r['origin_m'][i] for r in cells) for i in range(3)]
        size=[max(r['origin_m'][i]+r['size_m'][i] for r in cells)-origin[i] for i in range(3)]
        if len(cells)==1:
            origin=list(cells[0]['origin_m']);size=list(cells[0]['size_m'])
        if not math.isclose(math.prod(size),sum(math.prod(r['size_m']) for r in cells),rel_tol=1e-8):
            raise ValueError('Native cells do not tile physical room: '+parent)
        room=deepcopy(cells[0]);room.update(id=parent,parent_room=parent,origin_m=origin,size_m=size)
        room.pop('cell_index',None);rooms[parent]=room
    vents=[]
    for v in m['openings']:
        a,b=v['a'],v['b'];pa,pb=mapping.get(a,a),mapping.get(b,b)
        if pa==pb:
            if not v.get('virtual_cell_boundary'):raise ValueError('Real opening inside a proposed merged room')
            continue
        if v.get('type')!='FLOOR' and a in old:
            axis=0 if v.get('face','FRONT') in ('FRONT','REAR') else 1
            v['offset_m']=v.get('offset_m',0)+old[a]['origin_m'][axis]-rooms[pa]['origin_m'][axis]
        v.update(a=pa,b=pb);vents.append(v)
    for g in m['fuel_groups']:g['room']=mapping[g['room']]
    for v in m.get('mechanical_vents',[]):v['comp']=mapping[v['comp']]
    for target in targets:target['room']=mapping[target['room']]
    m.update(rooms=list(rooms.values()),openings=vents,explicit_candidates=targets,
             native_compartments=dict(revision=REVISION,cell_to_room=mapping))
    for row in m.get('minimum_leakage',[]):row['room']=mapping.get(row['room'],row['room'])
    note='순정 CFAST: 같은 실의 가상 분할 칸을 하나의 물리 구획으로 계산. 가연물별 지정 발열곡선·착화 센서는 유지하며 실 내부 국소 차이는 계산하지 않습니다.'
    m.setdefault('limits',[]).append(note)
    manifest['native_compartments']=deepcopy(m['native_compartments'])
    manifest['limits']=list(manifest.get('limits',[]))+[note]
    return m,targets,manifest
