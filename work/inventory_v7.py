import pathlib,sys,json,hashlib,collections,re
W=pathlib.Path(__file__).resolve().parent;sys.path[:0]=[str(W/'cad-deps'),r'C:\Users\<user>\Documents\Codex\2026-09-07\2\CAD3D']
import ezdxf
from cadio import load,units_to_m
SRC=pathlib.Path(r'C:\Users\<user>\Documents\Codex\2026-09-07\2\도면수집\28-200-2026-00000010')
DXF=pathlib.Path(r'C:\Users\<user>\Documents\Codex\2026-09-07\2\CAD3D\out\28-200-2026-00000010\dxf')
O=W/'cad-v7-inventory';O.mkdir(exist_ok=True)
records=[]
for f in sorted(DXF.glob('*.dxf')):
 d,prims,ins=load(f);texts=[]
 def walk(entities,depth=0):
  for e in entities:
   if e.dxftype() in ('TEXT','MTEXT','ATTRIB','ATTDEF'):
    tx=e.plain_text() if hasattr(e,'plain_text') else e.dxf.get('text','')
    if tx.strip():texts.append(tx.strip())
   elif e.dxftype()=='INSERT' and depth<8:
    walk(e.attribs,depth+1)
    try:walk(e.virtual_entities(),depth+1)
    except Exception:pass
 walk(d.modelspace())
 titles=[t for t in texts if re.search(r'평면|지하|지상|옥탑|지붕|창호|단면|입면|영사|방송|기자재|무대|다목적',t)]
 rec=dict(name=f.name,path=str(f),sha256=hashlib.sha256(f.read_bytes()).hexdigest(),unit_m=units_to_m(d,prims),titles=titles,
          layers=[dict(name=l.dxf.name,entities=sum(1 for p in prims if p.raw==l.dxf.name),off=l.is_off(),frozen=l.is_frozen()) for l in d.layers],
          entity_types=dict(collections.Counter(e.dxftype() for e in d.modelspace())),primitives=len(prims),blocks=len(ins),xrefs=[dict(name=b.name,path=b.block.dxf.get('xref_path',''),resolved=len(b)>0) for b in d.blocks if b.block.is_xref])
 records.append(rec);(O/(f.stem+'-texts.json')).write_text(json.dumps(texts,ensure_ascii=False),encoding='utf8')
 print(f.name,titles[:20],len(prims),flush=True)
(O/'cad_inventory.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf8')
import pdfplumber,subprocess
pdf=next(SRC.glob('*.pdf'));doc=pdfplumber.open(pdf);pages=[]
for i,p in enumerate(doc.pages):
 tx=p.extract_text() or '';draw=p.lines+p.curves+p.rects;rec=dict(page=i+1,size=[p.width,p.height],text=tx,drawings=len(draw),images=len(p.images),raster_only=not tx.strip() and not draw)
 pages.append(rec)
 print('PDF',i+1,tx[:140].replace('\n',' '),'draw',len(draw),'images',len(p.images),flush=True)
(O/'pdf_inventory.json').write_text(json.dumps(dict(name=pdf.name,path=str(pdf),sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),pages=pages),ensure_ascii=False,indent=2),encoding='utf8')
subprocess.run([r'C:\Users\<user>\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe','-scale-to','1600','-png',str(pdf),str(O/'fire')],check=True)
