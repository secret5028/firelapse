from pathlib import Path
import json
p=Path('work/new-pdf/seed-pages.json');seed=json.loads(p.read_text('utf8'))
for key in ['4','5']:
 floor=seed[key];r=floor['origin'][0]/278
 for e in floor['elevators']:
  e['door']={'a':[round(782*r,4),round(870*r,4)],'b':[round(816*r,4),round(870*r,4)],'sourceNote':'계단 남측 승강장 출입면 · 평면 판독 근사, 중앙개폐·높이는 기본값'}
p.write_text(json.dumps(seed,ensure_ascii=False),'utf8')
p=Path('work/folder_review.html');s=p.read_text('utf8')
s=s.replace("const openings=p.shapes.filter(s=>s.type==='door'||s.type==='window');", "const openings=p.shapes.filter(s=>s.type==='door'||s.type==='window').concat((p.elevators||[]).filter(e=>e.door).map(e=>({...e.door,type:'door'})));")
# Retain user positions while adding the newly reviewed doorway metadata.
s=s.replace('elevators:p.elevators??D.pages[i]?.initial?.elevators', 'elevators:(p.elevators??D.pages[i]?.initial?.elevators??[]).map((e,j)=>({...D.pages[i]?.initial?.elevators?.[j],...e,door:e.door??D.pages[i]?.initial?.elevators?.[j]?.door}))')
p.write_text(s,'utf8')
