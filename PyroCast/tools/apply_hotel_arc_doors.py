"""Rebuild hotel input connectivity from CAD arcs; no solver execution."""
from copy import deepcopy
import argparse
import gzip
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'simulation/deps'),str(ROOT/'simulation'),str(ROOT/'tools')]
from prepare_building_graph import prepare
from apply_hotel_autocorrect import save,check
from cad_autocorrect import repair_floor

def main(publish=False):
    out=ROOT/'reviews/cad-interior-arcs-20261104';dest=ROOT/'data/parkmarine-hotel'
    before=out/'building-before.json'
    if not before.exists():before.write_bytes((dest/'building.json').read_bytes())
    old=json.loads(before.read_text('utf-8'))
    source=json.loads((out/'source-arcs.json').read_text('utf-8')) if (out/'source-arcs.json').exists() else json.loads(gzip.decompress((out/'source-arcs.json.gz').read_bytes()))
    work=deepcopy(old)
    ai_path=dest/'ai-connection-review.json'
    ai=json.loads(ai_path.read_text('utf-8')) if ai_path.exists() else {'decisions':[]}
    for f,raw in zip(work['floors'],source['floors']):
        assert f['name']==raw['floor']
        f['cad_arcs']=[{k:v for k,v in a.items() if k not in ('points','source','layer')} for a in raw['interior_arcs']]
        f['cad_arc_provenance']={k:v for k,v in raw.items() if k!='interior_arcs'}
        f['ai_connection_reviews']=[x for x in ai['decisions'] if x['floor']==f['name']]
    inp=out/'building-input.json';save(inp,work)
    building,report=prepare(inp)
    rows=[]
    for a,b in zip(old['floors'],building['floors']):
        assert [{k:v for k,v in r.items() if k!='connectivity'} for r in a['rooms']]==[{k:v for k,v in r.items() if k!='connectivity'} for r in b['rooms']]
        oldlinks={x['id']:x['sides'] for x in a['simulation_graph']['connections']}
        newlinks={x['id']:x['sides'] for x in b['simulation_graph']['connections']}
        assert all(newlinks.get(k)==v for k,v in oldlinks.items()),(a['name'],'lost original links')
        for orig in a['openings']:
            now=next(o for o in b['openings'] if o['id']==orig['id'])
            for k in ('polys','leaves','open','open_fraction','fraction','schedule'):
                assert orig.get(k)==now.get(k),(a['name'],orig['id'],k)
        iso0=set(a['simulation_graph']['isolated_rooms']);iso1=set(b['simulation_graph']['isolated_rooms'])
        assert not iso1-iso0
        again=repair_floor(deepcopy(b));assert not again['changes'],(b['name'],again['changes'])
        rows.append(dict(floor=b['name'],before=len(iso0),after=len(iso1),recovered=sorted(iso0-iso1),remaining=sorted(iso1),
            connections_before=len(oldlinks),connections_after=len(newlinks),
            added=[x for x in b['simulation_graph']['connections'] if x['id'] not in oldlinks],
            interior_arcs=len(b['arc_door_inventory']),linked_arcs=sum(x['connection_state']=='linked' for x in b['arc_door_inventory'])))
    staged=out/'building-corrected.json';save(staged,building)
    loaders=check(staged)
    for row in loaders:
        if not row['ok']:
            item=dict(floor=row['floor'],id='LOADER',kind='loader_failed',detail=row['error'])
            building['model_review']['items'].append(item);report['model_reviews'].append(item)
    result=dict(before=sum(x['before'] for x in rows),after=sum(x['after'] for x in rows),floors=rows,loaders=loaders,
        changes=report['auto_corrections'],simulation_runs=0,original_geometry_preserved=True,existing_links_preserved=True,idempotent=True)
    save(staged,building);save(out/'graph-report.json',report);save(out/'comparison.json',result)
    if publish:save(dest/'building.json',building);save(dest/'graph-report.json',report)
    print(json.dumps({k:v for k,v in result.items() if k not in ('changes','floors')},ensure_ascii=False))
    print(json.dumps([{k:v for k,v in row.items() if k not in ('added','remaining')} for row in rows],ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--publish',action='store_true');main(p.parse_args().publish)
