"""Geometry/material input checks only. No integration or native execution."""
import hashlib
import subprocess
import types
import json
import math
import sys
from copy import deepcopy
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'simulation'),str(ROOT/'simulation/deps')]
from shapely.geometry import Polygon, Point, LineString
from pyrocast_cfbt.model import normalize
from pyrocast_cfbt.deck import make_deck
from pyrocast_lite.shared_inputs import read_shared

read=lambda p:json.loads(p.read_text('utf-8'))
DATA=ROOT/'data/wando-coldstore'
OUT=ROOT/'simulation/results/ui_C11_20261102'
MIRROR=ROOT/'simulation/results/github-publish-20261026/PyroCast'


def main():
    b=read(DATA/'building.json');f=b['floors'][0];p={r['room_id']:Polygon(r['polygon_m']) for r in f['rooms']}
    assert len(p)==8 and all(v.is_valid and v.area>0 for v in p.values())
    assert all(a.intersection(c).area<1e-9 for i,a in enumerate(p.values()) for c in list(p.values())[i+1:])
    assert math.isclose(p['R1'].area+p['R8'].area,18*18.4)
    assert math.isclose(p['R5'].area,157.5)
    assert len(f['openings'])==8 and all(v['exterior'] and v['b']=='OUTSIDE' for v in f['openings'])
    for v in f['openings']:
        x,y,_=v['center_m'];edge=LineString([(x-v['width_m']/2,y),(x+v['width_m']/2,y)])
        assert p[v['a']].boundary.buffer(1e-8).covers(edge),v['opening_id']
        # Entire aperture, not just center, must face the outside union.
        assert not any(poly.contains(Point(x,y-.1 if v['a']!='R9' else y+.1)) for rid,poly in p.items()),v['opening_id']
    fuel=read(DATA/'fuel-inputs.json');r5=next(r for r in fuel['rooms'] if r['room_id']=='R5')
    assert math.isclose(r5['energy_MJ'],(2*(8.75+18)*6.405+157.5)*.1*35*25)
    assert round(r5['fire_load_MJ_m2'])==278
    # Legacy input writer byte parity, without launching an engine.
    repo=MIRROR.parent
    baseline=subprocess.check_output(['git','-c',f'safe.directory={repo.as_posix()}', '-C',str(repo),
                                      'show','f7e5e7f:PyroCast/simulation/pyrocast_cfbt/deck.py']).decode('utf-8')
    old=types.ModuleType('pyrocast_cfbt._c11_baseline');old.__package__='pyrocast_cfbt'
    exec(compile(baseline,'f7e5e7f/deck.py','exec'),old.__dict__)
    raws=[read(ROOT/'simulation/examples/three_rooms.json'),
          read(ROOT/'simulation/results/lite_v8_mc_R2_10_20261026/S09/sample.json')['scenario']]
    parity=[]
    for raw in raws:
        m=normalize(raw);a=make_deck(m,[],[]);before=old.make_deck(m,[],[])
        assert a==before
        parity.append(dict(name=m.get('name','S09'),sha256=hashlib.sha256(a.encode()).hexdigest(),byte_identical=True))
    m=normalize(raws[0]);thermal=read(DATA/'thermal-input.json')
    m['fuel_groups']=[g for g in m['fuel_groups'] if 'initial_time_s' in g]
    m['surface_materials']=thermal['surface_materials'];m['wall_material']=thermal['wall_material']
    for r in m['rooms']:r['surface_material_ids']=thermal['rooms'][0]['surface_material_ids']
    shared=read_shared(m)
    for values in shared['materials_by_room'].values():
        for key in ('wall','ceiling'):
            assert values[key]['CONDUCTIVITY']==.025 and values[key]['SPECIFIC_HEAT']==1400
            assert values[key]['THICKNESS']==.1 and values[key]['DENSITY']==35
        assert values['floor']['CONDUCTIVITY']==1.75 and values['floor']['DENSITY']==2200
    mat_lines=[s for s in make_deck(m,[],[]).splitlines() if s.startswith('&MATL') and "ID='WALL'" not in s]
    (DATA/'materials.cfast.inc').write_text('\n'.join(mat_lines)+'\n','utf-8')
    # Reject bad IDs/properties before writing them to native input.
    bad=deepcopy(m);bad['surface_materials']['PU_LINING']['specific_heat_kJ_kgK']=-1
    try:make_deck(bad,[],[])
    except ValueError:pass
    else:raise AssertionError('invalid material accepted')
    frozen=['simulation/pyrocast_lite/core.py','simulation/pyrocast_lite/adapter.py',
            'simulation/pyrocast_lite/shared_inputs.py','simulation/pyrocast_cfbt/conditions.py',
            'simulation/pyrocast_cfbt/rule_settings.py','simulation/pyrocast_cfbt/rule_graph_r7.py',
            'simulation/pyrocast_cfbt/room_rule_r8.py','tools/serve_cfbt_building.py',
            'simulation/viewer/legacy_real_view.js','app/web/scene/host.js','app/web/layers/building.js']
    hashes={}
    for rel in frozen:
        assert (ROOT/rel).read_bytes()==(MIRROR/rel).read_bytes(),rel
        hashes[rel]=hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()
    result=dict(simulation_runs=0,native_runs=0,rooms=len(p),external_doors=8,
                total_area_m2=sum(v.area for v in p.values()),overlap_area_m2=0,
                r5_fuel=r5,legacy_deck_checks=parity,material_roundtrip_SI=True,
                unchanged_sha256=hashes)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'input-checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps({'rooms':8,'material_roundtrip':True,'legacy_decks_identical':2,'simulation_runs':0}))


if __name__=='__main__':main()
