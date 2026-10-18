from pathlib import Path
import json
from hydraulic_embed import embed_hydraulics
p=Path('outputs/소방공간뷰-강화산업단지-통합.html');s=p.read_text('utf-8')
marker='const app=URL.createObjectURL(new Blob(['
start=s.index(marker)+len(marker);_,length=json.JSONDecoder().raw_decode(s[start:]);code=Path('work/industrial.js').read_text('utf-8')
s=s[:start]+json.dumps(code,ensure_ascii=False).replace('</','<\\/')+s[start+length:]
s=embed_hydraulics(s,'work','industrial-20-v1','강화산업단지 공장 · 기존 배관은 개략선, 계산 계통 별도 등록')
p.write_text(s,'utf-8');print('Updated reviewed industrial HTML using its embedded source assets')
