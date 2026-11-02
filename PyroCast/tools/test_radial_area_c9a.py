"""C9a geometry/legacy regression only; no time integration."""
import json,math
from copy import deepcopy
import run_lite_l1 as base
from run_lite_mc_v8_r2 import PARAMS
from pyrocast_lite.adapter import prepare
from pyrocast_lite.radial_cells import cache_key,radius_for_area,circle
from shapely.geometry import Polygon
from shapely.ops import unary_union


def main():
    root=base.ROOT;out=root/'simulation/results/ui_C9a_20261102'
    read=lambda p:json.loads(p.read_text('utf-8'))
    raw=read(root/'simulation/results/lite_v8_mc_R2_10_20261026/S09/sample.json')['scenario']
    m,man=prepare(raw,PARAMS)
    before=read(root/'simulation/results/ui_C9_20261102/legacy-preparation-before.json')
    assert before==dict(model=m.input_model,manifest=man,contract=m.contract)
    _,fixed=prepare(dict(raw,cell_mode='radial'),PARAMS)
    assert fixed==read(root/'simulation/results/ui_C9_20261102/radial/rule_manifest.json')
    a,manifest=prepare(dict(raw,cell_mode='radial_area'),PARAMS)
    info=manifest['cells']['radial'];target=info['radial_target_area_m2']
    assert math.isclose(target,104.11701,abs_tol=1e-8)
    shapes=[unary_union([Polygon(p['o'],p['h']) for p in r['radial_polys']]) for r in a.input_model['rooms'] if r.get('radial_zone')]
    assert all(abs(s.area-target)<1e-7 for s in shapes[:2])
    original=next(r for r in raw['rooms'] if r['id']=='CAD_3F_R2')
    whole=unary_union([Polygon(p['o'],p.get('h',[])) for p in original['cad_polys']])
    assert whole.symmetric_difference(unary_union(shapes)).area<1e-8
    assert all(x.intersection(y).area<1e-8 for i,x in enumerate(shapes) for y in shapes[i+1:])
    assert math.isclose(a.Va.sum(),m.Va.sum(),rel_tol=1e-12)
    def widths(model):
        ans={}
        for v in model.input_model['openings']:
            if not v.get('virtual_cell_boundary'):
                k=v.get('parent_opening',v['id']);ans[k]=ans.get(k,0)+v['width_m']
        return ans
    assert widths(a).keys()==widths(m).keys()
    assert all(math.isclose(v,widths(m)[k],abs_tol=1e-8) for k,v in widths(a).items())
    assert math.isclose(manifest['cells']['total_energy_MJ_before'],manifest['cells']['total_energy_MJ_after'],rel_tol=1e-12)
    hole=Polygon([(-20,-20),(20,-20),(20,20),(-20,20)],[[(3,3),(5,3),(5,5),(3,5)]])
    r=radius_for_area(hole,(0,0),104)
    assert abs(hole.intersection(circle((0,0),r)).area-104)<1e-7
    ids=[cache_key(dict(raw,cell_mode=x),PARAMS,'same-engine') for x in ('legacy','radial','radial_area')]
    assert len(set(ids))==3
    k=cache_key(raw,PARAMS,'same-engine',info)
    assert k!=cache_key(raw,PARAMS,'same-engine',dict(info,radial_r1_m=info['radial_r1_m']+.1))
    base.save(out/'geometry-checks.json',dict(legacy_identical=True,fixed_radial_manifest_identical=True,
        area_targets_met=True,polygons_cover_without_overlap=True,hole_bisection=True,
        volume_energy_apertures_preserved=True,cache_mode_resolved_radius_separated=True,geometry=info))
    print(json.dumps(dict(target=target,r1=info['radial_r1_m'],r2=info['radial_r2_m'],cells=info['cells']),ensure_ascii=False))

if __name__=='__main__':main()
