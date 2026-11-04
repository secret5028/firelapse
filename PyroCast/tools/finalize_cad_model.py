"""Finish CAD→3D model input with shared axioms, AI review, and visible issues.

Consumes the existing CAD loader's building JSON; never runs a fire simulation.
The source-bound AI decisions are embedded in the input by the review step, or
supplied as a JSON file. An absent review is recorded, not claimed as completed.
"""
import argparse,gzip,json,sys
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'simulation/deps'),str(ROOT/'simulation'),str(ROOT/'tools')]
from prepare_building_graph import prepare
from apply_hotel_autocorrect import save,check

def finalize(source,out,ai_review=None,publish=False):
    source=Path(source);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    snapshot=out/'building-before.json.gz'
    if not snapshot.exists():
        with gzip.GzipFile(filename=str(snapshot),mode='wb',mtime=0) as f:f.write(source.read_bytes())
    elif source.read_bytes()!=gzip.decompress(snapshot.read_bytes()):
        last=out/'building-after.json'
        if not last.exists() or source.read_bytes()!=last.read_bytes():
            raise ValueError('Input changed since this review. Use a new output directory; do not reuse an old drawing snapshot.')
    before=json.loads(gzip.decompress(snapshot.read_bytes()))
    work=deepcopy(before)
    if ai_review:
        decisions=json.loads(Path(ai_review).read_text('utf8'))['decisions']
        for f in work['floors']:f['ai_connection_reviews']=[x for x in decisions if x['floor']==f['name']]
    staged=out/'input.json';save(staged,work)
    after,report=prepare(staged)
    result=out/'building-after.json';save(result,after)
    # Reapplying the finalizer may update report source metadata, never add repairs.
    repeat,again=prepare(result)
    assert not again['auto_corrections'],again['auto_corrections']
    assert repeat['vertical_connections']==after['vertical_connections']
    assert all(x['kind'] in ('stair','elev') for x in after['vertical_connections'])
    floor_rows=[]
    for a,b in zip(before['floors'],after['floors']):
        archived={c['source_room_id']:c['source_room'] for c in b.get('structural_columns',[])}
        now={r['id']:r for r in b['rooms']}
        for r in a['rooms']:
            target=now.get(r['id'],archived.get(r['id']));assert target is not None
            for key in ('polys','area','names'):assert r.get(key)==target.get(key),(a['name'],r['id'],key)
        floor_rows.append(dict(floor=b['name'],rooms_before=len(a['rooms']),rooms_after=len(b['rooms']),
            unresolved_before=len(a['simulation_graph']['isolated_rooms']),unresolved_after=len(b['simulation_graph']['isolated_rooms']),
            columns=[c['source_room_id'] for c in b.get('structural_columns',[])],remaining=b['simulation_graph']['isolated_rooms']))
    loaders=check(result)
    for row in loaders:
        if not row['ok']:
            item=dict(floor=row['floor'],id='LOADER',kind='loader_failed',detail='입력 검토 필요 · '+row['error'])
            after['model_review']['items'].append(item);report['model_reviews'].append(item)
    summary=dict(floors=floor_rows,unresolved_before=sum(x['unresolved_before'] for x in floor_rows),
        unresolved_after=sum(x['unresolved_after'] for x in floor_rows),
        column_reclassifications=sum(len(f.get('structural_columns',[])) for f in after['floors']),
        vertical_before=len(before.get('vertical_connections',[])),vertical_after=len(after['vertical_connections']),
        vertical_kinds=sorted({x['kind'] for x in after['vertical_connections']}),
        loaders=loaders,simulation_runs=0,idempotent=True,geometry_preserved=True)
    save(result,after);save(out/'comparison.json',summary);save(out/'graph-report.json',report)
    if publish:save(source,after);save(source.parent/'graph-report.json',report)
    print(json.dumps(summary,ensure_ascii=False))
    return after,summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('--output',required=True);p.add_argument('--ai-review');p.add_argument('--publish',action='store_true')
    a=p.parse_args();finalize(a.source,a.output,a.ai_review,a.publish)
