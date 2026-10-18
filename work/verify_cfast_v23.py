from pathlib import Path
import json, math, sys, hashlib
from cfast_design_fire import load_design, interpolate
sys.path.insert(0,str(Path(__file__).resolve().parent/'cad-deps'))
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
root=Path(__file__).resolve().parent.parent
out=root/'outputs/CAD-NIST가연물-v23'
d=json.loads((out/'cfast-demo.json').read_text('utf8'))
old=json.loads((out/'backup/cfast-demo.json').read_text('utf8'))
assert d['duration']==1800 and len(d['hrr'])==361 and len(d['fires'])==3
assert d['solver_compartments']==100 and len(d['rooms'])==156 and len(d['vertical_connections'])==36
assert d['building_sha256']==old['building_sha256']
assert all(math.isfinite(v) for r in d['rooms'] for row in r['series'] for v in row)
assert 'NORMAL EXIT' in (out/'multifloor-execution.log').read_text().upper()
design=load_design(root/'work/cfast_nist_design_fire.json',1800)
assert 3250<design['peak_kW']<3350 and len(design['hrr_kW'])<=200
assert abs(design['evidence']['energy_relative_error'])<.01
assert abs(load_design(root/'work/cfast_design_fire.json',1800)['prescribed_energy_MJ']-1600.125)<1e-8
assert all(abs(v-interpolate(design['hrr_kW'],i*5))<1e-6 for i,v in enumerate(d['prescribed_hrr']))
assert load_design(root/'work/cfast_nist_design_fire.json',600)['hrr_kW'][-1][0]==600
try:load_design(root/'work/cfast_nist_design_fire.json',3600)
except ValueError:pass
else:raise AssertionError('Measured horizon extended without evidence')
fixtures=out/'test-fixtures';fixtures.mkdir(exist_ok=True)
for table in ([[0,0],[0,50],[1800,0]],[[0,0],[1800,-1]],[[0,0],[300,1]]):
    bad=dict(design,hrr_kW=table);p=fixtures/'invalid.json';p.write_text(json.dumps(bad),'utf8')
    try:load_design(p,1800)
    except ValueError:pass
    else:raise AssertionError('Invalid tabulated curve accepted')
rooms={r['key']:r for r in d['rooms']};targets=[]
for f in d['fires'][1:]:
    r=rooms[f['room_key']];poly=unary_union([Polygon(p['o'],p['h']) for p in r['polys']])
    x,y=f['position'];w=f['width_m'];h=f['depth_m']
    assert poly.covers(box(x-w/2,y-h/2,x+w/2,y+h/2)),f['id']
    assert f['setpoint']==407 and f['pilot_assumed']
    assert all(q==0 for flag,q in zip(f['ignited'],f['hrr']) if flag==0)
    assert all(math.isfinite(v) for row in f['target_series'] for v in row)
    if f['ignition_time'] is not None:
        before=[a for a in f['target_series'] if a[0] <= f['ignition_time']]
        assert max(a[1] for a in before)>=400 # solver event within 5s sampling
    targets.append(dict(id=f['id'],room=f['room_key'],ignition_time=f['ignition_time'],
                        max_surface_C=max(s[1] for s in f['target_series']),max_hrr_kW=max(f['hrr'])))
growth=d['ignition_scenario']['growth']['hrr_kW']
energy=sum((b[0]-a[0])*(a[1]+b[1])/2000 for a,b in zip(growth,growth[1:]))
assert abs(energy-254.4)<1e-6
deck=(out/'multifloor.in').read_text()
assert deck.count('&FIRE ')==3 and deck.count('SETPOINT=407')==2 and 'ADIABATIC_TARGET=.TRUE.' not in deck
marker='// Coupled CFAST results on the original CAD scene.'
assert (out/'backup/model.html').read_text('utf8').split(marker)[0]==(out/'model.html').read_text('utf8').split(marker)[0]
report=dict(status='passed',physical_validation=False,normal_exit=True,elapsed_seconds=d['elapsed_seconds'],
    rooms=156,solver_compartments=100,vertical_paths=36,building_sha256=d['building_sha256'],legacy_prefix_unchanged=True,
    measured_curve_peak_kW=design['peak_kW'],prescribed_energy_MJ=design['prescribed_energy_MJ'],
    actual_primary_peak_kW=max(d['hrr']),actual_total_peak_kW=max(d['total_hrr']),
    curve_energy_reduction_error_fraction=design['evidence']['energy_relative_error'],targets=targets,
    target_energy_MJ=energy,footprints_inside_rooms=True,invalid_input_tests='passed',
    limitations=['Free-burning measured HRR transferred to an equivalent compartment',
    'Pilot presence and inventory/placement assumed; not predicted',
    'Cone effective thermal fit used with CFAST two-sided plate, unlike insulated cone back',
    'Post-ignition square HRR uses fixed 45kW/m2 test; no dynamic fuel pyrolysis',
    'Surrogate chemistry and smoke yields remain assumed'])
(out/'검증결과.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
print(json.dumps(report,ensure_ascii=False))
