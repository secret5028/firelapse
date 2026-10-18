from pathlib import Path
import hashlib, json, shutil
from cfast_combustion import add_combustion

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'outputs/CAD-연소표현-v28'
BASE=ROOT/'outputs/CAD-속도검증-v27/final'
JOB=Path('C:/Users/예방/Desktop/소방 크로키 업-로컬웹앱/data/d018b4bb75da4475b1fd75447603c1a0/cad-output')
OUT.mkdir(exist_ok=True); (OUT/'backup').mkdir(exist_ok=True)
for name in ('model.html','cfast-demo.json','building.json'):
    if not (OUT/'backup'/name).exists(): shutil.copy2(JOB/name, OUT/'backup'/name)
for name in ('cad_cfast_multifloor.py','cad_cfast_realistic.js','cad_cfast_multifloor_overlay.js','restore_cad_ui.py'):
    if not (OUT/'backup'/name).exists(): shutil.copy2(ROOT/'work'/name,OUT/'backup'/name)
data=json.loads((BASE/'cfast-demo.json').read_text(encoding='utf8'))
raw=(JOB/'building.json').read_bytes()
assert hashlib.sha256(raw).hexdigest()==data['building_sha256']
add_combustion(data, BASE, json.loads(raw))
(OUT/'cfast-demo.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf8')
summary={'rooms':[{'room':r['solver_key'],'intervals':r['intervals']} for r in data['combustion']['rooms']],
         'jets':[{k:v for k,v in j.items() if k!='hrr'} for j in data['combustion']['jets']]}
(OUT/'combustion-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(summary,ensure_ascii=False))
