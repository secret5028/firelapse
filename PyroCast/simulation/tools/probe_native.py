from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pyrocast_cfbt.model import normalize
from pyrocast_cfbt.deck import candidates, make_deck, gas_sidecar
from pyrocast_cfbt.native import execute

model=normalize(json.loads((ROOT/'examples/three_rooms.json').read_text()))
if len(sys.argv)>1 and sys.argv[1]=='off':
    model['gas']['bulk_enabled']=False
    model['gas']['vent_gate_enabled']=False
targets=candidates(model)
folder=ROOT/'results'/('native_probe_'+(sys.argv[1] if len(sys.argv)>1 else 'on'))
result=execute(ROOT/'build/cfbt/cfast-cfbt.exe',folder,make_deck(model,[],targets),gas_sidecar(model),model['duration_s'],180)
print(json.dumps({'run':result['run'],'bulk_peak_W':max((r['bulk_HRR_W'] for r in result['rooms']),default=0),
                  'upper_peaks_C':{k:float(max(v)) for k,v in result['zone'].items() if k.startswith('ULT_')},
                  'zone_fields':list(result['zone'])[:25]},indent=2))
