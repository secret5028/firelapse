"""Apply conservative input repair; validate loaders only, never run a solver."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'simulation/deps'),str(ROOT/'simulation'),str(ROOT/'tools')]
from prepare_building_graph import prepare
from pyrocast_cfbt.cad import adapt
from cad_autocorrect import repair_floor

def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n','utf-8')

def check(path):
    building=json.loads(path.read_text('utf-8'));rows=[]
    for f in building['floors']:
        try:
            adapt(ROOT,dict(building_path=str(path),fire_floor=f['name'],scope_floor=f['name'],fire_room=f['rooms'][0]['id']))
            rows.append(dict(floor=f['name'],ok=True))
        except Exception as e:rows.append(dict(floor=f['name'],ok=False,error=str(e)))
    return rows

def main():
    dest=ROOT/'data/parkmarine-hotel';out=ROOT/'reviews/cad-autocorrect-20261104'
    out.mkdir(parents=True,exist_ok=True)
    before=out/'building-before.json'
    if not before.exists():before.write_bytes((dest/'building.json').read_bytes())
    old=json.loads(before.read_text('utf-8'))
    building,report=prepare(before)
    # Check that room footprints, sizes and original CAD opening geometry survive.
    for a,b in zip(old['floors'],building['floors']):
        assert a['rooms']==b['rooms'] or all(
            {k:v for k,v in x.items() if k!='connectivity'}=={k:v for k,v in y.items() if k!='connectivity'}
            for x,y in zip(a['rooms'],b['rooms']))
        for x,y in zip(a['openings'],b['openings']):
            for key in ('polys','leaves','open','open_fraction','fraction','schedule'):
                assert x.get(key)==y.get(key),(a['name'],x['id'],key)
    assert all(not repair_floor(deepcopy(f))['changes'] for f in building['floors']), 'non-idempotent repair'
    staged=out/'building-corrected.json';save(staged,building)
    pre,post=check(before),check(staged)
    for row in post:
        if not row['ok']:
            item=dict(floor=row['floor'],id=row['error'].rsplit('_',1)[-1],kind='loader_failed',detail='입력 검토 필요 · '+row['error'])
            building['model_review']['items'].append(item);report['model_reviews'].append(item)
    def counts(b):
        return dict(rooms=sum(len(f['rooms']) for f in b['floors']),
            isolated=sum(len(f['simulation_graph']['isolated_rooms']) for f in b['floors']),
            connections=sum(len(f['simulation_graph']['connections']) for f in b['floors']))
    result=dict(before=counts(old),after=counts(building),loaders_before=pre,loaders_after=post,
        changes=report['auto_corrections'],review_counts=dict(Counter(x['kind'] for x in building['model_review']['items'])),
        source_sha256=hashlib.sha256(before.read_bytes()).hexdigest(),
        original_source=str(Path.home()/'Documents/Codex/2026-09-07/2/CAD3D/out/28-200-2018-00000088/building.json'),
        idempotent=True,simulation_runs=0,original_geometry_preserved=True)
    save(staged,building);save(dest/'building.json',building);save(dest/'graph-report.json',report);save(out/'comparison.json',result)
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
