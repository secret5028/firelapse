"""Compare unchanged ignition algorithms with the read-only pre-edit r8 snapshot."""
import importlib.util
from pathlib import Path
import sys,json
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pyrocast_cfbt.model import normalize
from pyrocast_cfbt.native import load_result,digest
from pyrocast_cfbt.deck import candidates,make_deck
from pyrocast_cfbt.spread import assess


def main():
    snapshot=ROOT.parent/'reviews/전체프로그램-창파괴기본값·5초출력-Claude검토-20261022-r8/code/project/simulation/pyrocast_cfbt'
    spec=importlib.util.spec_from_file_location('r8_snapshot',snapshot/'__init__.py',submodule_search_locations=[str(snapshot)])
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    from r8_snapshot.spread import assess as old_assess
    from r8_snapshot.deck import make_deck as old_deck
    folder=ROOT/'results/window_r8_20261022/floor_no_windows_30min'
    model=normalize(json.loads((folder/'scenario.json').read_text('utf-8')))
    targets=candidates(model);native=load_result(folder/'run_00',1800,{'folder':str(folder/'run_00')})
    old,old_views,_=old_assess(model,native,targets,[])
    new,new_views,_=assess(model,native,targets,[])
    assert old==new,'Ignition proposals changed'
    maximum=0.
    for a,b in zip(old_views,new_views):
        assert a['id']==b['id']
        for key in ('q_inc_kW_m2','surface_C'):
            delta=float(np.max(np.abs(np.asarray(a[key],float)-np.asarray(b[key],float))))
            maximum=max(maximum,delta)
    assert maximum<1e-10,maximum
    assert make_deck(model,[],targets)==old_deck(model,[],targets),'Window OFF native input changed'
    assert digest(snapshot/'thermal.py')==digest(ROOT/'pyrocast_cfbt/thermal.py')
    report={'passed':True,'same_native_deck_when_disabled':True,'thermal_source_unchanged':True,
        'same_ignition_proposals':True,'targets_compared':len(targets),'max_surface_or_incident_difference':maximum,
        'basis':'same successful 31-room native result and same candidates; read-only r8 algorithm versus current'}
    path=ROOT/'results/window_r8_20261022/regression.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
