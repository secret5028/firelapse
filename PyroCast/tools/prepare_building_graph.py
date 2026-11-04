"""Read CAD building JSON and apply the established connection/classification stage.

Does not run a simulation or alter the source drawing. Unknown links stay unknown.
"""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'simulation/deps'), str(ROOT/'simulation')]
from building_rules import load_rules, usage_class, dedicated_core_kind
from cad_connectivity_shared import build_graph, geometry, match_vertical_cores
from pyrocast_lite.door_classification import classify_doors
from cad_autocorrect import repair_floor

def prepare(source, *, auto_correct=True):
    raw = Path(source).read_bytes()
    building = json.loads(raw)
    report = dict(source=str(Path(source).resolve()), source_sha256=hashlib.sha256(raw).hexdigest(),
                  rules_revision=load_rules()['revision'], floors=[], doors=[], rooms=[],
                  unmapped_labels=[], errors=[], limitations=[], auto_corrections=[], model_reviews=[])
    table = json.loads((ROOT/'simulation/pyrocast_lite/fire_load_table.json').read_text('utf-8'))
    unmapped = {}
    core_nodes = []
    for floor in building['floors']:
        name = floor['name']; adapted = []; nodes = []
        if auto_correct:
            repair = repair_floor(floor)
            report['auto_corrections'].extend(repair['changes'])
            report['model_reviews'].extend(repair['reviews'])
        for room in floor['rooms']:
            rid = f"CAD_{name}_{room['id']}"
            shape = geometry(room['polys']); x0,y0,x1,y1 = shape.bounds
            labels = room.get('names', [])
            cls, evidence = usage_class(labels, floor.get('use'))
            if evidence.get('basis') != 'label':
                report['model_reviews'].append(dict(floor=name,id=room['id'],kind='estimated_usage',
                    detail='용도 추정 · 도면 라벨 미매핑, 기존 층 기본값 유지',usage_class=cls,evidence=evidence))
            kind = dedicated_core_kind(room)
            adapted.append(dict(id=rid, name=' / '.join(labels), cad_names=labels,
                                area_m2=room['area'], size_m=[x1-x0,y1-y0,floor['h']], core_kind=kind))
            report['rooms'].append(dict(id=rid, floor=name, area_m2=room['area'], labels=labels,
                                       usage_class=cls, usage_evidence=evidence, core_kind=kind,
                                       fuel_load_MJ_m2=table['classes'][cls]['mean']))
            for label in labels:
                if usage_class([label], None)[1]['basis']!='label':
                    unmapped.setdefault(label, []).append(rid)
            if kind:
                node=dict(core_id='ROOM_'+room['id'],room_id=room['id'],kind=kind,floor=name,
                          x=(x0+x1)/2,y=(y0+y1)/2,w=x1-x0,h=y1-y0,z0=floor['z'],
                          z1=floor['z']+floor['h'],align=floor.get('align','unconfirmed'),
                          access_room_ids=[],association='dedicated_room_tag_or_label')
                nodes.append(node)
                if room['area']>load_rules()['doors']['core_max_area_m2']:
                    report['errors'].append(dict(floor=name,id=room['id'],kind='large_core_label_review',
                                                 detail='코어 태그와 큰 실 면적이 함께 있음. 자동 수정하지 않음.'))
        defaults=dict(room_h=floor.get('ceil_h') or floor['h'],door_h=floor.get('door_h') or load_rules()['openings']['door_height_m'],
                      sill=floor.get('sill',load_rules()['openings']['sill_m']),head=floor.get('head',load_rules()['openings']['head_m']))
        try:
            graph=build_graph(floor['rooms'],floor['openings'],defaults)
        except (ValueError,TypeError) as exc:
            report['errors'].append(dict(floor=name,kind='graph_failed',detail=str(exc)))
            raise ValueError(f'{name}: {exc}') from exc
        floor['simulation_graph']=graph
        raw_openings={v['id']:v for v in floor['openings']}
        openings=[]
        for v in graph['connections']:
            a,b=[f'CAD_{name}_{x}' if x!='out' else 'OUTSIDE' for x in v['sides']]
            o=raw_openings[v['id']]
            openings.append(dict(id=f"CAD_{name}_{v['id']}",a=a,b=b,kind=v['kind'],
                                 raw_geometry=deepcopy(o),fire_evidence=o.get('fire_evidence')))
        _,classification=classify_doors(dict(rooms=adapted,openings=openings))
        counts=Counter('confirmed' if r['door_class']=='fire' and r['confidence']=='confirmed' else
                       'inferred' if r['door_class']=='fire' else r['door_class'] for r in classification['rows'])
        report['doors'].extend(classification['rows'])
        for node in nodes:
            node['access_room_ids']=sorted({s for v in graph['connections'] if node['room_id'] in v['sides'] for s in v['sides'] if s not in (node['room_id'],'out')})
        core_nodes.extend(nodes)
        for row in graph['excluded_openings']:
            report['errors'].append(dict(floor=name,kind='excluded_opening',**row))
        report['errors'].extend(dict(floor=name,id=rid,kind='isolated_room') for rid in graph['isolated_rooms'])
        report['model_reviews'].extend(dict(floor=name,id=rid,kind='isolated_room',
            detail='연결 미확인 · 도면에 없는 문을 생성하지 않음') for rid in graph['isolated_rooms'])
        report['floors'].append(dict(floor=name,rooms=len(floor['rooms']),connections=len(graph['connections']),
                                    doors={k:counts[k] for k in ['confirmed','inferred','ordinary','external']},
                                    windows=sum('window' in v['kind'] for v in graph['connections']),
                                    external_windows=sum('window' in v['kind'] and v['boundary']=='exterior' for v in graph['connections']),
                                    cores=dict(Counter(n['kind'] for n in nodes)),excluded=len(graph['excluded_openings']),
                                    isolated=len(graph['isolated_rooms'])))
    # Original legacy shaft envelopes are preserved as evidence, not promoted to verified links.
    building.setdefault('source_shafts',deepcopy(building.get('shafts',[])))
    building['core_nodes']=core_nodes
    building['shafts'],building['unconfirmed_vertical_cores']=match_vertical_cores(core_nodes)
    building['vertical_connections']=[dict(kind=s['kind'],from_floor=a['floor'],from_core=a['core_id'],
        to_floor=b['floor'],to_core=b['core_id'],evidence='aligned_cad_core_overlap',overlap=s['overlaps'][i])
        for s in building['shafts'] for i,(a,b) in enumerate(zip(s['nodes'],s['nodes'][1:]))]
    building.update(schema_version=2,opening_unit='percent')
    report['unmapped_labels']=[dict(label=k,rooms=sorted(set(v))) for k,v in sorted(unmapped.items())]
    report['vertical_connections']=len(building['vertical_connections'])
    report['unconfirmed_vertical_cores']=building['unconfirmed_vertical_cores']
    building['model_review']=dict(revision='geometry_evidence_v1',auto_correct=auto_correct,
        corrections=[dict(floor=f['name'],id=o['id'],**c) for f in building['floors']
                     for o in f['openings'] for c in o.get('auto_corrections',[])],
        items=deepcopy(report['model_reviews']),basis='기하 근거 자동보정 · 현장 확인 아님')
    report['limitations']=['원본 추출 결과에 있는 개구부만 연결. 미확정은 외기로 대체하지 않음.',
                          '실명에 없는 용도는 기존 층 용도 기본값 적용; 개별 미매핑 문자는 별도 목록.',
                          '큰 실에 붙은 코어 태그·복수 용도 문자는 검토 필요. 도면 재인식이나 문 생성 없음.',
                          '기존 샤프트 외곽만으로 층간 연결을 확정하지 않음. 실 좌표·정렬·인접 층 중첩으로 재검사.',
                          '14개 도면 층은 B3~B1·1F~10F·PH이며 지상 14층을 뜻하지 않음.',
                          '분류의 확정은 프로젝트 규칙상 명칭이며 방화 성능 실측 확인이 아님.']
    return building, report

def main():
    ap=argparse.ArgumentParser();ap.add_argument('source');ap.add_argument('--output',required=True)
    ap.add_argument('--no-auto-correct',action='store_true',help='기하 근거 자동보정 비활성')
    args=ap.parse_args();out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    building,report=prepare(args.source,auto_correct=not args.no_auto_correct)
    for name,obj in [('building.json',building),('graph-report.json',report)]:
        (out/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'floors':report['floors'],'vertical_connections':report['vertical_connections'],
                      'unmapped_labels':len(report['unmapped_labels']),'issues':len(report['errors'])},ensure_ascii=False))

if __name__=='__main__':main()
