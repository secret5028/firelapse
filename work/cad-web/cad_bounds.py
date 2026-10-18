import json,collections
v=json.load(open('work/cad-input/vectors.json',encoding='utf-8'))
for i in ['2','3','4']:
 print('\n',i)
 for layer in sorted(set(l['layer'] for l in v[i]['lines'])):
  if any(t in layer.upper() for t in ['WALL','CON','DOOR','DOFRAME','WIN','STA','INS','외벽']):
   pts=[p for l in v[i]['lines'] if l['layer']==layer for p in l['p']];print(layer,len(pts),[round(min(p[k] for p in pts)) for k in (0,1)],[round(max(p[k] for p in pts)) for k in (0,1)])
 print([(t['text'],[round(x) for x in t['p'][:2]]) for t in v[i]['texts'] if t['layer']=='IN-TEXT'][:45])
