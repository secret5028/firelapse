"""Topology/output regression checks; these are not physical validation."""
from pathlib import Path
import hashlib,json,math
root=Path(__file__).resolve().parent.parent
out=root/'outputs/CAD-층간전이-v17'
opened=json.loads((out/'cfast-demo.json').read_text('utf8'))
closed=json.loads((out/'closed-result.json').read_text('utf8'))
assert opened['solver_compartments']==100
assert len(opened['vertical_connections'])==36
assert {v['kind'] for v in opened['vertical_connections']}=={'stair','elev','ramp'}
assert len(opened['floor_summary'])==9
members=opened['solver_members']; all_keys=[k for ms in members.values() for k in ms]
assert len(set(all_keys))==len(all_keys)==156
by_key={r['key']:r for r in opened['rooms']}
for k,ms in members.items():
    if len(ms)>1:
        assert len({by_key[m]['floor'] for m in ms})==1
        assert all(by_key[m]['floor']!='3F' and not by_key[m]['core_kind'] for m in ms)
for r in opened['rooms']:
    assert len(r['series'])==121
    assert r['series'][0][0]==0 and r['series'][-1][0]==600
    assert all(math.isfinite(x) for row in r['series'] for x in row)
    assert all(0<=row[3]<=r['height']+.001 for row in r['series'])
for f in opened['floor_summary']:
    if f!='3F':assert closed['floor_summary'][f]['max_od']==0
for f in ['4F','5F','6F','7F','PH']:assert opened['floor_summary'][f]['max_od']>0
assert len(opened['flame_height'])==121 and opened['flame_height'][0]==0
assert opened['flame_height'][-1]>1
app=Path('C:/Users/<user>/Desktop/소방 크로키 업-로컬웹앱')
dest=app/'data/d018b4bb75da4475b1fd75447603c1a0/cad-output'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(dest/'building.json')==opened['building_sha256']
assert sha(dest/'cfast-demo.json')==sha(out/'cfast-demo.json')
assert sha(dest/'model.html')==sha(out/'model.html')==sha(app/'_internal/cad_engine/integrated_viewer.html')
old=(out/'before-model.html').read_text('utf8').split('// CFAST result playback')[0].rstrip()
new=(out/'model.html').read_text('utf8').split('// Coupled CFAST results')[0].rstrip()
assert old==new,'Legacy interface prefix changed'
record=dict(status='passed',building_unchanged=True,legacy_interface_prefix_unchanged=True,solver_compartments=100,display_rooms=156,vertical_paths=36,normal_exit=True,
    open_floor_summary=opened['floor_summary'],closed_floor_summary=closed['floor_summary'],
    scope='Topology, numerical range, installation and closed-path control checks only; not fire-physics validation')
(out/'검증결과.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf8')
print('PASS: legacy + geometry unchanged; 36 paths; closed-path control has no inter-floor smoke; mapped outputs finite.')
