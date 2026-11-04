"""Shared CAD completion policy: repeated structure, reviewed repair, visible gaps.

No solver, nearest-room door, or synthetic unobserved floor connection. Removed
column/room duplicates retain their full original records as structural objects.
"""
from collections import defaultdict
from copy import deepcopy
import json,re
from pathlib import Path
from shapely.geometry import Point,box
from cad_connectivity_shared import geometry
from building_rules import dedicated_core_kind,load_rules

CONFIG=Path(__file__).resolve().parents[1]/'config/cad-model-axioms.json'
def load_policy():return json.loads(CONFIG.read_text('utf-8'))
def iou(a,b):return a.intersection(b).area/max(a.union(b).area,1e-9)
def aligned(f):
    text=f.get('align','unconfirmed')
    return not any(t in text for t in load_rules()['vertical']['weak_alignment_tokens'])

def apply_model_axioms(building,policy=None):
    p=policy or load_policy();changes=[];reviews=[];floors=building['floors']
    building.setdefault('source_shafts',deepcopy(building.get('shafts',[])))
    candidates=[]
    # A seed needs a structural CAD label AND an already detected column point.
    for f in floors:
        if not aligned(f):continue
        for r in f['rooms']:
            shape=geometry(r['polys'])
            if not any(re.search(p['column_label_pattern'],s,re.I) for s in r.get('names',[])):continue
            for c in f.get('columns',[]):
                if shape.covers(Point(c['x'],c['y'])):candidates.append((f,r,shape,c))
        # Retain seeds on reapplication after their room record was archived.
        for c in f.get('structural_columns',[]):
            r=c['source_room']
            if any(re.search(p['column_label_pattern'],s,re.I) for s in r.get('names',[])):
                candidates.append((f,r,geometry(r['polys']),c['column_center']))
    for seed_floor,seed,foot,center in candidates:
        hits=[];point=Point(center['x'],center['y'])
        for f in floors:
            if not aligned(f) or not any(point.distance(Point(c['x'],c['y']))<=p['column_position_tolerance_m'] for c in f.get('columns',[])):continue
            for r in f['rooms']:
                shape=geometry(r['polys'])
                if not shape.covers(point) or iou(shape,foot)<p['column_footprint_min_iou']:continue
                if any(s and not re.search(p['column_label_pattern'],s,re.I) for s in r.get('names',[])):continue
                referenced=any(r['id'] in o.get('sides',[]) and o.get('sides',[None,None])[0]!=o.get('sides',[None,None])[-1] for o in f['openings'])
                if referenced:
                    reviews.append(dict(floor=f['name'],id=r['id'],kind='column_conflict',detail='반복 기둥 위치이나 유효 개구부 참조가 있어 실 분류 유지'));continue
                hits.append((f,r,shape))
        archived=[f['name'] for f in floors for c in f.get('structural_columns',[]) if point.distance(Point(c['column_center']['x'],c['column_center']['y']))<=p['column_position_tolerance_m']]
        if len(set([f['name'] for f,_,_ in hits]+archived))<p['column_min_distinct_floors']:continue
        matched=sorted(set([f['name'] for f,_,_ in hits]+archived))
        for f,r,shape in hits:
            detail=dict(kind='column_not_room',floor=f['name'],id=r['id'],before='room',after='column',
                detail='층간 반복 위치·기둥 표기·형상 일치 → 실에서 기둥으로 재분류',
                evidence=dict(seed_floor=seed_floor['name'],seed_room=seed['id'],labels=seed.get('names'),
                    center=[center['x'],center['y']],matched_floors=matched,iou=round(iou(shape,foot),6)))
            f.setdefault('structural_columns',[]).append(dict(id='COLUMN_'+r['id'],source_room_id=r['id'],source_room=deepcopy(r),
                column_center=deepcopy(center),polys=deepcopy(r['polys']),height_m=f['h'],correction=detail))
            f['rooms'].remove(r);changes.append(detail)
    # Repeated core envelopes identify only matching room footprints, not entire
    # halls containing a shaft. No match means a review marker, not a vertical link.
    possible=defaultdict(list)
    for si,s in enumerate(building['source_shafts']):
        if s.get('kind') not in p['vertical_kinds']:
            for name in s.get('floors',[]):reviews.append(dict(floor=name,id='SOURCE_CORE_'+str(si),kind='vertical_excluded',detail='모델 공리: 계단·승강기 외 수직 연결 제외'))
            continue
        if not all(k in s for k in ('x','y','w','h')):continue
        footprint=box(s['x']-s['w']/2,s['y']-s['h']/2,s['x']+s['w']/2,s['y']+s['h']/2)
        for f in floors:
            if f['name'] not in s.get('floors',[]) or not aligned(f):continue
            matches=sorted([(iou(geometry(r['polys']),footprint),r) for r in f['rooms']],key=lambda x:x[0],reverse=True)
            if matches and matches[0][0]>=p['core_footprint_min_iou'] and (len(matches)==1 or matches[0][0]-matches[1][0]>p['core_ambiguity_margin']):
                score,r=matches[0];possible[si].append((f,r,s['kind'],score))
            else:
                reviews.append(dict(floor=f['name'],id='SOURCE_CORE_'+str(si),kind='core_region_unresolved',
                    point_m=[s['x'],s['y']],detail='반복 코어 위치 확인 · 대응 실 영역 미확정, 수직 연결 생성 안 함'))
    supported=defaultdict(list)
    for si,hits in possible.items():
        if len(set(f['name'] for f,_,_,_ in hits))<2:continue
        for f,r,kind,score in hits:supported[(f['name'],r['id'])].append(dict(kind=kind,source_core=si,iou=score,matched_floors=[x[0]['name'] for x in hits]))
    for f in floors:
        for r in f['rooms']:
            old=dedicated_core_kind({k:v for k,v in r.items() if k!='axiom_core_kind'})
            evidence=supported.get((f['name'],r['id']),[]);kinds={e['kind'] for e in evidence}
            kind=next(iter(kinds)) if len(kinds)==1 else None
            if kind:
                r['axiom_core_kind']=kind;r['core_axiom_evidence']=evidence
                if old!=kind:
                    item=dict(floor=f['name'],id=r['id'],kind='repeated_core_identity',before=old,after=kind,
                        detail='층간 공통 위치·코어 형상 대응 → '+('계단' if kind=='stair' else '승강기'),evidence=evidence)
                    r.setdefault('model_corrections',[])
                    if not any(c['kind']==item['kind'] for c in r['model_corrections']):r['model_corrections'].append(item);changes.append(item)
            elif old:
                # Dedicated explicit IDs may still be paired directly by the
                # established adjacent-floor matcher. Mixed hall tags cannot.
                if len(r.get('names',[]))>load_rules()['core']['max_dedicated_labels'] or len(kinds)>1:
                    r['axiom_core_kind']=None
                    reviews.append(dict(floor=f['name'],id=r['id'],kind='core_region_unresolved',detail='복합 실 코어 표기만 있음 · 전체 실을 수직 통로로 간주하지 않음'))
            else:r['axiom_core_kind']=None
        if f.get('model_ramps'):
            f.setdefault('source_model_ramps',deepcopy(f['model_ramps']))
        for i,_ in enumerate(f.get('source_model_ramps',[])):
            reviews.append(dict(floor=f['name'],id='RAMP_'+str(i),kind='vertical_excluded',detail='램프 형상 보존 · 본 모델의 수직 유동/이동 경로에서는 제외'))
    building['model_axioms']=deepcopy(p)
    return dict(changes=changes,reviews=reviews)
