from pathlib import Path
import json
from cfast_plume_metadata import add_plume_metadata
root=Path(__file__).resolve().parent.parent
out=root/'outputs/CAD-공식플룸-v29'
data=json.loads((out/'backup/cfast-demo.json').read_text(encoding='utf8'))
add_plume_metadata(data,root/'outputs/CAD-속도검증-v27/final/multifloor.in')
(out/'cfast-demo.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf8')
print([(f['id'],f['plume_inputs']) for f in data['fires']])
