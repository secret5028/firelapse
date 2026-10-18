from pathlib import Path
import json
P=Path('work')
seedpath=P/'new-pdf/seed-pages.json';seed=json.loads(seedpath.read_text('utf8'))
for key in ['4','5']:
 p=seed[key];r=p['origin'][0]/278
 p['elevators']=[{'name':'승강기','p':[round(798*r,5),round(846*r,5)],'sourcePage':int(key)+1,'sourceNote':'1층 ELE 13인승 장애인겸용 / 2층 동일 위치 승강기 형상. 표시는 위치 기호이며 승강로 치수가 아님.'}]
seedpath.write_text(json.dumps(seed,ensure_ascii=False),'utf8')
# Use initial source-linked annotations even when an older saved state lacks this field.
p=P/'folder_review.html';s=p.read_text('utf8');s=s.replace('addFloorDetails(T,group,p,convert,y);','addFloorDetails(T,group,p,convert,y);addPageElevators(T,group,p,convert,y);')
s=s.replace('state.pages.map(p=>({...p,shapes:', 'state.pages.map((p,i)=>({...p,elevators:p.elevators??D.pages[i]?.initial?.elevators,shapes:')
p.write_text(s,'utf8')
p=P/'prepare_local.py';s=p.read_text('utf8').replace("Path('work/wall-surface.js').read_text('utf-8')", "Path('work/elevator-display.js').read_text('utf-8')+'\\n'+Path('work/wall-surface.js').read_text('utf-8')");p.write_text(s,'utf8')
p=P/'review-layout.js';s=p.read_text('utf8').replace("['stairs','계단']", "['stairs','계단'],['elevator','승강기 · 금색 ↕']");p.write_text(s,'utf8')
# Museum coordinates use the same CAD registration as its existing model.
m=P/'museum';base=json.loads((m/'cad-6.json').read_text('utf8'));anchor=next(t['p'] for t in base['texts'] if t['text']=='106,100');origin=[base['bounds'][0],base['bounds'][3]]
model=json.loads((m/'model.json').read_text('utf8'))
for f,idx in zip(model,[5,6,4,3]):
 d=json.loads((m/f'cad-{idx}.json').read_text('utf8'));a=next(t['p'] for t in d['texts'] if t['text']=='106,100');dx=anchor[0]-a[0];dy=anchor[1]-a[1]
 f['elevators']=[{'x':round((t['p'][0]+dx-origin[0])/1000,5),'z':round((origin[1]-t['p'][1]-dy)/1000,5),'name':'승강기','source':d['name']} for t in d['texts'] if '승강기' in t['text']]
(m/'model.json').write_text(json.dumps(model,ensure_ascii=False),'utf8')
p=m/'viewer.js';s=p.read_text('utf8');s=s.replace('DATA.forEach((f,i)=>{', (P/'elevator-display.js').read_text('utf8')+'\nDATA.forEach((f,i)=>{',1);s=s.replace("'windows','stairs','furniture'", "'windows','stairs','elevator','furniture'");s=s.replace('layerGroups.push(ls);', "layerGroups.push(ls);for(const e of f.elevators||[])addElevatorMarker(T,ls.elevator,e.x,f.y,e.z,e.name);");p.write_text(s,'utf8')
p=m/'package.py';s=p.read_text('utf8').replace("('stairs','계단')", "('stairs','계단'),('elevator','승강기 · 금색 ↕')");p.write_text(s,'utf8')
print('Elevator annotations:',[(f['name'],f['elevators']) for f in model])
