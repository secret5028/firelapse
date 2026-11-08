"""Parallel native vents for apertures wider than an equal-area box wall.

Preserves endpoints, sill/head, schedule and summed width/area. This is an
equivalent zone-flow representation, not a correction to the original CAD
opening or a claim that multiple physical doors exist. Original inputs stay
intact so MC chooses one state per original opening before this conversion.
"""
from copy import deepcopy
import math


def prepare(raw):
    m=deepcopy(raw);rooms={r['id']:r for r in m['rooms']};out=[];notes=[]
    used={v['id'] for v in m.get('openings',[])}
    for v in m.get('openings',[]):
        if v.get('type')=='FLOOR':
            out.append(v);continue
        axis=0 if v.get('face','FRONT') in ('FRONT','REAR') else 1
        available=min(rooms[r]['size_m'][axis] for r in (v['a'],v['b']) if r in rooms)
        count=max(1,math.ceil(v['width_m']/available))
        if count==1:
            out.append(v);continue
        ids=[]
        for i in range(count):
            part=deepcopy(v);ident=v['id'] if i==0 else v['id']+f'_EQ{i}'
            if i and ident in used:raise ValueError('Equivalent vent ID collision: '+ident)
            used.add(ident);ids.append(ident)
            width=v['width_m']/count
            part.update(id=ident,width_m=width,offset_m=(rooms[v['a']]['size_m'][axis]-width)/2,
                        equivalent_parent_opening=v['id'],equivalent_part=i)
            out.append(part)
        notes.append(dict(opening=v['id'],parts=ids,width_m=v['width_m'],
                          area_m2=v['width_m']*(v['top_m']-v.get('bottom_m',0)),
                          basis='parallel same-height zone vents; summed aperture area and schedule preserved'))
    m['openings']=out
    if notes:
        m['equivalent_apertures']=dict(revision='native_parallel_apertures_v1',rows=notes)
        m.setdefault('warnings',[]).append('계산용 벽보다 넓은 개구부: 동일 높이·개폐율의 병렬 개구부로 면적 합계를 보존한 등가 입력. 실제 문 개수·CAD 형상은 변경하지 않음.')
    return m
