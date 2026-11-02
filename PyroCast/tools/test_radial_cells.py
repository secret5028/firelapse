"""C9 geometry/conservation/cache checks; no integration."""
import json, math
from copy import deepcopy
from pathlib import Path
import run_lite_l1 as base
from run_lite_mc_v8_r2 import PARAMS
from pyrocast_lite.adapter import prepare
from pyrocast_lite.radial_cells import split_shape, cache_key
from shapely.geometry import Polygon
from shapely.ops import unary_union


def main():
    out=base.ROOT/'simulation/results/ui_C9_20261102'
    raw=json.loads((base.ROOT/'simulation/results/lite_v8_mc_R2_10_20261026/S09/sample.json').read_text('utf-8'))['scenario']
    legacy,lman=prepare(raw,PARAMS)
    before=json.loads((out/'legacy-preparation-before.json').read_text('utf-8'))
    assert before==dict(model=legacy.input_model,manifest=lman,contract=legacy.contract)
    radial=deepcopy(raw);radial['cell_mode']='radial'
    m,man=prepare(radial,PARAMS)
    cells=[c for c in m.input_model['rooms'] if c.get('radial_zone')]
    other=lambda x:[r for r in x.input_model['rooms'] if r.get('parent_room')!='CAD_3F_R2']
    assert other(legacy)==other(m)
    shapes=[unary_union([Polygon(p['o'],p['h']) for p in c['radial_polys']]) for c in cells]
    original=next(r for r in raw['rooms'] if r['id']=='CAD_3F_R2')
    source=unary_union([Polygon(p['o'],p.get('h',[])) for p in original['cad_polys']])
    assert unary_union(shapes).symmetric_difference(source).area<1e-8
    assert all(a.intersection(b).area<1e-8 for i,a in enumerate(shapes) for b in shapes[i+1:])
    assert math.isclose(m.Va.sum(),legacy.Va.sum(),rel_tol=1e-12)
    # Whole physical apertures retain total area per original opening.
    def widths(model):
        values={}
        for v in model.input_model['openings']:
            if not v.get('virtual_cell_boundary'):
                key=v.get('parent_opening',v['id']);values[key]=values.get(key,0)+v['width_m']
        return values
    assert widths(m).keys()==widths(legacy).keys()
    assert all(math.isclose(v,widths(legacy)[k],abs_tol=1e-8) for k,v in widths(m).items())
    assert math.isclose(man['cells']['total_energy_MJ_before'],man['cells']['total_energy_MJ_after'],rel_tol=1e-12)
    # Hole preservation, disjoint annuli, small-zone merge.
    hole=Polygon([(-20,-20),(20,-20),(20,20),(-20,20)],[[(8,8),(10,8),(10,10),(8,10)]])
    parts=split_shape(hole,(0,0),6,12)
    assert unary_union([s for _,s in parts]).symmetric_difference(hole).area<1e-8
    small=Polygon([(-3,-3),(3,-3),(3,3),(-3,3)])
    assert [z for z,_ in split_shape(small,(0,0),6,12)]==['fire']
    k=cache_key(raw,PARAMS,'engine')
    assert k==cache_key(dict(raw,cell_mode='legacy',radial_r1_m=6.,radial_r2_m=12.),PARAMS,'engine')
    keys={cache_key(dict(raw,**v),PARAMS,'engine') for v in [dict(cell_mode='legacy'),dict(cell_mode='radial'),dict(cell_mode='radial',radial_r1_m=7.),dict(cell_mode='radial',radial_r2_m=13.)]}
    assert len(keys)==4
    report=dict(legacy_model_manifest_contract_identical=True,other_rooms_identical=True,
                volume_m3=float(m.Va.sum()),physical_apertures=len(widths(m)),fuel_energy_conserved=True,
                polygon_coverage_and_nonoverlap=True,hole_and_merge_checks=True,cache_mode_radius_keys_distinct=True,
                cells=man['cells']['radial']['cells'])
    base.save(out/'geometry-checks.json',report)
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
