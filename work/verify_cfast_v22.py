from pathlib import Path
import json, math
from contextlib import nullcontext
from cfast_design_fire import load_design, interpolate

root=Path(__file__).resolve().parent.parent
out=root/'outputs/CAD-CFAST기준-v22'
d=json.loads((out/'cfast-demo.json').read_text('utf8'))
old=json.loads((root/'outputs/CAD-30분-실감보기-v18/cfast-demo.json').read_text('utf8'))
assert d['calculation_mode']=='prescribed_design_fire'
assert len(d['fires'])==1 and 'ignition_scenario' not in d
assert d['duration']==1800 and len(d['hrr'])==361
assert d['solver_compartments']==100 and len(d['vertical_connections'])==36
assert len(d['rooms'])==156 and d['building_sha256']==old['building_sha256']
assert all(math.isfinite(v) for r in d['rooms'] for sample in r['series'] for v in sample)
prior={r['key']:r for r in old['rooms']}
delta=max(abs(v-w) for r in d['rooms'] for a,b in zip(r['series'],prior[r['key']]['series']) for v,w in zip(a,b))
assert delta==0,delta
assert d['hrr']==old['hrr']
assert 'NORMAL EXIT' in (out/'multifloor-execution.log').read_text().upper()
deck=(out/'multifloor.in').read_text()
assert deck.count('&FIRE ')==1 and 'IGNITION_CRITERION' not in deck and 'DEMWOOD' not in deck
design=load_design(root/'work/cfast_design_fire.json',1800)
assert abs(design['prescribed_energy_MJ']-1600.125)<1e-8
assert interpolate(design['hrr_kW'],150)==250
assert all(abs(v-interpolate(design['hrr_kW'],i*5))<1e-7 for i,v in enumerate(d['prescribed_hrr']))
# Verify finite-duration input and invalid horizons, independent of the current demo.
base=json.loads((root/'work/cfast_design_fire.json').read_text('utf8'))
with nullcontext(out/'test-fixtures') as tmp:
    tmp.mkdir(exist_ok=True)
    path=Path(tmp)/'scenario.json'
    finite=dict(base,steady_seconds=300,decay_seconds=300,end_behavior='zero')
    path.write_text(json.dumps(finite),'utf8')
    curve=load_design(path,1800)
    assert interpolate(curve['hrr_kW'],600)==1000
    assert interpolate(curve['hrr_kW'],750)==250
    assert interpolate(curve['hrr_kW'],900)==0
    assert interpolate(curve['hrr_kW'],1800)==0
    for invalid in (dict(base,area_m2=0),dict(base,sample_seconds=.5),dict(base,radiative_fraction=2)):
        path.write_text(json.dumps(invalid),'utf8')
        try:load_design(path,1800)
        except ValueError:pass
        else:raise AssertionError('Invalid configuration accepted')
try:load_design(root/'work/cfast_design_fire.json',3600)
except ValueError:pass
else:raise AssertionError('Unbounded duration accepted')
old_html=(out/'backup/model.html').read_text('utf8')
new_html=(out/'model.html').read_text('utf8')
marker='// Coupled CFAST results on the original CAD scene.'
assert old_html.split(marker)[0]==new_html.split(marker)[0], 'Legacy UI changed'
report=dict(status='passed',physical_validation=False,normal_exit=True,elapsed_seconds=d['elapsed_seconds'],
    rooms=156,solver_compartments=100,vertical_paths=36,fire_count=1,secondary_ignition='not modeled',
    comparison='v18 same prescribed primary fire',max_room_series_difference=delta,
    prescribed_energy_MJ=design['prescribed_energy_MJ'],equivalent_fuel_kg=design['equivalent_fuel_kg'],
    finite_decay_and_invalid_input_checks='passed',legacy_prefix_unchanged=True,
    building_sha256=d['building_sha256'])
(out/'검증결과.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
print(json.dumps(report,ensure_ascii=False))
