from pathlib import Path
import json
root=Path('C:/Users/예방/Desktop/소방 크로키 업-로컬웹앱/data')
for job in ['80fe8228ff8c4082bc8bf9f83771895b','1b8e6ebc75a74661b81047d7da38be68']:
 s=json.loads((root/job/'state.json').read_text('utf8'));print(job,[(e.get('type')) for p in s['pages'] for e in p.get('fireFacilities',{}).get('equipment',[]) if e.get('type') in ['tank','pump']])
