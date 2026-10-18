from pathlib import Path
import sys,json,re
sys.path.insert(0,str(Path('work/cad-deps').resolve()))
import ezdxf
base=Path('C:/Users/예방/Desktop/소방 크로키 업-로컬웹앱/data/d018b4bb75da4475b1fd75447603c1a0')
doc=ezdxf.readfile(base/'4fae9163d0ab4400a82d92a6286d22e2.dxf')
texts=[]
for block in doc.blocks:
 for e in block:
  if e.dxftype() in ('TEXT','MTEXT','ATTRIB','ATTDEF'):
   t=e.plain_text() if hasattr(e,'plain_text') else e.dxf.get('text','')
   texts.append(dict(text=t,layer=e.dxf.layer,block=block.name,point=list(e.dxf.insert)[:2]))
terms=re.compile('테라스|테라쓰|TERRACE|발코니|BALCONY|노대|옥외|난간|RAIL|PARAPET|휴게',re.I)
hits=[t for t in texts if terms.search(t['text'])]
print('text_count',len(texts),'hits',json.dumps(hits,ensure_ascii=False))
print('layer_hits',[l.dxf.name for l in doc.layers if terms.search(l.dxf.name)])
Path('work/3F-all-cad-text.json').write_text(json.dumps(texts,ensure_ascii=False,indent=2),'utf8')
# Nearby original text in modelspace; transformed source metre region of R27.
b=json.loads((base/'cad-output/building.json').read_text('utf8'));f=next(f for f in b['floors'] if f['name']=='3F')
for t in texts:
 x,y=t['point'];x=x*.001*f['scale']+f['shift'][0]-b['origin'][0];y=y*.001*f['scale']+f['shift'][1]-b['origin'][1]
 if 43<x<70 and 28<y<41:print('nearby',json.dumps(t,ensure_ascii=False))
