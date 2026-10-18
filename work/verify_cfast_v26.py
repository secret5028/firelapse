from pathlib import Path
import json, math, sys, re, csv
from cfast_design_fire import load_design, interpolate
sys.path.insert(0,str(Path(__file__).resolve().parent/'cad-deps'))
from shapely.geometry import Polygon, Point, box
from shapely.ops import unary_union

root=Path(__file__).resolve().parent.parent
out=root/'outputs/CAD-조건부전이-v26'
d=json.loads((out/'cfast-demo.json').read_text('utf8'))
old=json.loads((out/'backup/cfast-demo.json').read_text('utf8'))
manifest=json.loads((out/'connection-manifest.json').read_text('utf8'))
assert d['duration']==1800 and len(d['hrr'])==361 and len(d['fires'])==5
assert d['solver_compartments']==100 and len(d['rooms'])==156 and len(d['vertical_connections'])==36
assert d['building_sha256']==old['building_sha256']
assert all(math.isfinite(v) for r in d['rooms'] for row in r['series'] for v in row)
assert 'NORMAL EXIT' in (out/'multifloor-execution.log').read_text().upper()
assert d['prescribed_hrr']==old['prescribed_hrr']
assert all(abs(total-(sum(f['hrr'][i] for f in d['fires'])+d['vent_jet_hrr'][i]))<1e-6 for i,total in enumerate(d['total_hrr']))
rooms={r['key']:r for r in d['rooms']};targets=[];footprints=[]
native_log=(out/'multifloor.log').read_text()
native_events={m.group(1):float(m.group(2)) for m in re.finditer(r'Object #\d+ \(([^)]+)\) ignited at\s+(\d+) seconds',native_log)}
with (out/'multifloor_compartments.csv').open() as stream:
    rd=csv.reader(stream);head=next(rd);next(rd);next(rd);next(rd)
    native_rows=[dict(zip(head,map(float,row))) for row in rd if row]
r=rooms['3F_R9'];side=math.sqrt(d['design_fire']['area_m2']);x,y=r['c']
footprints.append(box(x-side/2,y-side/2,x+side/2,y+side/2))
for f in d['fires'][1:]:
    r=rooms[f['room_key']];poly=unary_union([Polygon(p['o'],p['h']) for p in r['polys']])
    x,y=f['position'];w=f['width_m'];h=f['depth_m'];foot=box(x-w/2,y-h/2,x+w/2,y+h/2)
    assert poly.covers(foot),f['id']
    assert poly.contains(Point(f['target_position']))
    if f['room_key']=='3F_R9':footprints.append(foot)
    assert f['criterion']=='TEMPERATURE' and f['setpoint']==369 and f['pilot_assumed']
    assert all(q==0 for flag,q in zip(f['ignited'],f['hrr']) if flag==0)
    assert all(math.isfinite(v) for row in f['target_series'] for v in row)
    if f['ignition_time'] is not None:
        assert f['id'] in native_events, 'IGN flag without native ignition log: '+f['id']
        assert abs(f['ignition_time']-native_events[f['id']])<=5.5
        fire_index=d['fires'].index(f)+1
        assert any(row[f'HRR_E{fire_index}']>0 for row in native_rows), 'Ignited fire has no prescribed HRR'
        rows=[a for a in f['target_series'] if a[0]<=f['ignition_time']+5]
        assert max(a[1] for a in rows)>=368, f['id']
    targets.append(dict(id=f['id'],name=f['name'],room=f['room_key'],ignition_time=f['ignition_time'],
        max_surface_C=max(s[1] for s in f['target_series']),max_hrr_kW=max(f['hrr'])))
assert all(a.intersection(b).area==0 for i,a in enumerate(footprints) for b in footprints[i+1:])
assert not any({v['a'],v['b']}=={'3F_R9','3F_R8'} for v in manifest['wall'])
growth=d['ignition_scenario']['growth']['hrr_kW']
assert len(growth)<=200 and all(t>=0 and q>=0 for t,q in growth)
energy=sum((b[0]-a[0])*(a[1]+b[1])/2000 for a,b in zip(growth,growth[1:]))
deck=(out/'multifloor.in').read_text()
assert deck.count('&FIRE ')==5 and deck.count('SETPOINT=369')==4
assert deck.count("IGNITION_CRITERION='TEMPERATURE'")==4
marker='// Coupled CFAST results on the original CAD scene.'
assert (out/'backup/model.html').read_text('utf8').split(marker)[0]==(out/'model.html').read_text('utf8').split(marker)[0]
report=dict(status='passed',physical_validation=False,normal_exit=True,elapsed_seconds=d['elapsed_seconds'],
    rooms=156,solver_compartments=100,vertical_paths=36,building_sha256=d['building_sha256'],legacy_prefix_unchanged=True,
    actual_primary_peak_kW=max(d['hrr']),actual_total_peak_kW=max(d['total_hrr']),targets=targets,
    registered_fire_peak_kW=max(d['registered_fire_hrr']),vent_jet_peak_kW=max(d['vent_jet_hrr']),
    target_prescribed_energy_MJ=energy,footprints_inside_rooms=True,fire_room_packages_nonoverlapping=True,
    native_ignition_log_matches_flags=True,native_ignition_log_seconds=native_events,
    primary_curve_unchanged=True,source_room_dimensions_m=manifest['dims']['3F_R9'],
    room_max_upper_C={k:max(s[1] for s in rooms[k]['series']) for k in ['3F_R9','3F_R2','3F_R8']},
    limitations=d['ignition_scenario']['defaults']['evidence']['assumptions'])
(out/'검증결과.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
print(json.dumps(report,ensure_ascii=False))
