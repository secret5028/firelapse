import ezdxf,json,collections
from ezdxf.disassemble import recursive_decompose
from ezdxf import path
from PIL import Image,ImageDraw
allout={}
for i in range(1,9):
 d=ezdxf.readfile(f'work/cad-input/{i}.dxf'); lines=[];texts=[]
 for e in recursive_decompose(d.modelspace()):
  try:
   if e.dxftype() in ('TEXT','MTEXT'):texts.append({'text':e.dxf.text if e.dxftype()=='TEXT' else e.plain_text(),'p':[round(v,5) for v in e.dxf.insert],'layer':e.dxf.layer});continue
   if e.dxftype() in ('HATCH','SOLID','TRACE','3DFACE'):continue
   pts=[[round(v,5) for v in p] for p in path.make_path(e).flattening(30)]
   if len(pts)>1:lines.append({'layer':e.dxf.layer,'p':pts})
  except Exception:pass
 allout[str(i)]={'lines':lines,'texts':texts}
 if i in [1,2,3,8]:
  pts=[p for l in lines for p in l['p']];lo=[min(p[k] for p in pts) for k in (0,1)];hi=[max(p[k] for p in pts) for k in (0,1)];scale=min(1800/(hi[0]-lo[0]),1200/(hi[1]-lo[1]));im=Image.new('RGB',(1900,1300),'white');dr=ImageDraw.Draw(im)
  for l in lines:dr.line([(50+(p[0]-lo[0])*scale,1250-(p[1]-lo[1])*scale) for p in l['p']],fill='black',width=1)
  im.save(f'work/cad-input/{i}.png')
 print(i,len(lines),collections.Counter(l['layer'] for l in lines).most_common(12))
json.dump(allout,open('work/cad-input/vectors.json','w',encoding='utf-8'),ensure_ascii=False)
