from pathlib import Path
import sys,json
ROOT=Path('C:/Users/예방/Documents/ChatGPT/PyroCast');sys.path.insert(0,str(ROOT/'tools'))
from lite_export import build_export
out=Path(__file__).parent;phase=sys.argv[1];rows=json.loads((out/'stage1-paired/capture.json').read_text('utf8'))['scenes']
for name,port in [('hotel',8842),('intech',8844)]:
 row=next(r for r in rows if r['name']==name+'-1440-result')
 state={'floor':row['floor'],'selection':row['selection'],'playback':{'t_s':1420,'playing':False,'speed':1}}
 data,info=build_export(f'http://127.0.0.1:{port}',row['case'],state,model_service=True)
 assert b'--bg-panel:' in data and b'href="/cfbt/theme.css"' not in data
 (out/phase/(name+'-offline.html')).write_bytes(data)
 print(json.dumps({'building':name,**info},ensure_ascii=False))
