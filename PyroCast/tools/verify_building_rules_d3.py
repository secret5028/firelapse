"""D-3 read-only regression; no solver run or result-folder writes."""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'simulation/deps'),str(ROOT/'simulation')]
from pyrocast_cfbt.cad import dedicated_core_kind
from pyrocast_cfbt.practical import room_defaults
from pyrocast_lite.core import fire_class
from pyrocast_lite.door_classification import classify_doors
import cad_connectivity_shared as shared

def main():
    out=ROOT/'reviews/D3-20261103';before=json.loads((out/'before.json').read_text('utf-8'))
    rows=[]; buildings=[]
    for p in ['simulation/results/github-publish-20261026/PyroCast/cad-project/building.json','data/wando-coldstore/operating-building.json']:
        b=json.loads((ROOT/p).read_text('utf-8'));buildings.append(b)
        for f in b['floors']:
            for r in f['rooms']:
                rows.append([p,f['name'],r['id'],dedicated_core_kind(r),room_defaults(r,b),fire_class(r.get('names',[]),f.get('use'))])
    assert rows==before['rooms']
    raw=json.loads((ROOT/'simulation/results/room_rule_r8_20261025/source-scenario.json').read_text('utf-8'))
    assert json.loads(json.dumps(classify_doors(raw)))==before['doors']
    # Compare configured graph helpers against the exact extracted upstream functions.
    ns=dict(vars(shared)); provenance=json.loads((out/'cad-source.json').read_text('utf-8'))
    for src in provenance:
        p=Path(src['file']);assert hashlib.sha256(p.read_bytes()).hexdigest()==src['sha256']
        source=p.read_text('utf-8');tree=ast.parse(source)
        functions=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in
                   ('polygon_parts','opening_parts','geometry','connection_status','aperture_frame','opening_dimensions','build_graph','match_vertical_cores')]
        for fn in functions:exec(compile(ast.Module(body=[fn],type_ignores=[]),str(p),'exec'),ns)
    hotel_path=ROOT/'data/parkmarine-hotel/building.json'
    hotel=json.loads(hotel_path.read_text('utf-8'));buildings.append(hotel)
    checked=0
    for building in buildings:
        for f in building['floors']:
            if not f.get('openings') or any('area' not in r for r in f['rooms']):continue
            defaults=dict(room_h=f.get('ceil_h') or f['h'],door_h=f.get('door_h') or 2.1,
                          sill=f.get('sill',.9),head=f.get('head',2.2))
            a=ns['build_graph'](deepcopy(f['rooms']),deepcopy(f['openings']),defaults)
            b=shared.build_graph(deepcopy(f['rooms']),deepcopy(f['openings']),defaults)
            assert a==b, f['name'];checked+=1
    assert ns['match_vertical_cores'](hotel['core_nodes'])==shared.match_vertical_cores(hotel['core_nodes'])
    from execution_evidence import engine_hashes
    hashes=engine_hashes()
    assert 'config/building-rules.json' in hashes and 'simulation/building_rules.py' in hashes
    result=dict(room_outputs_equal=len(rows),door_model_and_report_equal=True,
                graph_floors_equal=checked,vertical_match_equal=True,configuration_hashed=True,
                simulations=0)
    (out/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))

if __name__=='__main__':main()
