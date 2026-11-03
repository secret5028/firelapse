"""Augment saved playback only. No solver execution or physical-array changes."""
from pathlib import Path
import json,hashlib
from pyrocast_cfbt.native import read_native_csv
from wando_jet_visual import add_jet_visuals

ROOT=Path(__file__).resolve().parents[1]
def main():
    path=ROOT/'data/wando-coldstore/P1-playback.json'
    old=json.loads(path.read_text('utf-8')); before=json.dumps(old['solvers'],sort_keys=True)
    src=ROOT/'simulation/results/wando_C11_P1_20261102'
    model=json.loads((src/'model.json').read_text('utf-8'))
    vents,_,_=read_native_csv(src/'case_vents.csv')
    add_jet_visuals(old,model,vents)
    assert json.dumps(old['solvers'],sort_keys=True)==before
    path.write_text(json.dumps(old,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    ep=path.parent/'playback-evidence.json';e=json.loads(ep.read_text('utf-8'))
    e['playback_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    e['door_jet_display']='receiver total allocated by saved directional outflow; physical arrays unchanged'
    ep.write_text(json.dumps(e,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'directions':len(old['door_jet']['directions']),'physical_arrays_unchanged':True,'recalculations':0}))
if __name__=='__main__':main()
