import json
from pathlib import Path
v=json.load(open('work/cad-input/vectors.json',encoding='utf-8'));out=[]
for i,x0,y in [(2,30145,1),(3,121998,7.5),(4,213852,15)]:
 f={'name':{2:'1층',3:'2층',4:'지붕'}[i],'y':y,'lines':[],'texts':[]}
 for l in v[str(i)]['lines']:
  layer=l['layer'];u=layer.upper();pts=[[(p[0]-x0)/1000,(-p[1]-412723)/1000] for p in l['p']]
  if not all(-8<p[0]<42 and -8<p[1]<34 for p in pts):continue
  if any(t in u for t in ['DIM','CEN','TIT','DEF','TEXT','HAT','INS','TREES']):continue
  typ='detail'
  if 'DOOR' in u or 'DOFRAME' in u or '창호' in u:typ='doors'
  elif 'WIN' in u:typ='windows'
  elif 'STA' in u:typ='stairs'
  elif 'WALL' in u or u=='IN-CON' or u.endswith('$CON'):typ='walls'
  elif 'FUR' in u or 'BATH' in u:typ='furniture'
  else:continue
  f['lines'].append({'type':typ,'p':[[round(a,5),round(b,5)] for a,b in pts]})
 for t in v[str(i)]['texts']:
  x=(t['p'][0]-x0)/1000;z=(-t['p'][1]-412723)/1000
  if t['layer']=='IN-TEXT' and -5<x<40 and -5<z<32 and len(t['text'])>2:f['texts'].append({'text':t['text'],'x':x,'z':z})
 out.append(f)
Path('work/cad-input/model.json').write_text(json.dumps(out,ensure_ascii=False),encoding='utf-8')
