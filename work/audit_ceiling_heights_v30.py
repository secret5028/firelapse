from pathlib import Path
import json,sys,re,hashlib
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'work/cad-deps'))
import ezdxf
from shapely.geometry import Polygon,Point
from shapely.ops import unary_union
base=Path('C:/Users/<user>/Desktop/소방 크로키 업-로컬웹앱/data/d018b4bb75da4475b1fd75447603c1a0')
b=json.loads((base/'cad-output/building.json').read_text('utf8'))
records={};evidence=[]
def texts(entities):
 for e in entities:
  if e.dxftype() in ['TEXT','MTEXT','ATTRIB','ATTDEF']:
   yield {'text':e.plain_text() if hasattr(e,'plain_text') else e.dxf.text,'point':list(e.dxf.insert)[:2],'layer':e.dxf.layer}
  elif e.dxftype()=='INSERT':
   yield from texts(e.attribs)
   try:yield from texts(e.virtual_entities())
   except Exception:pass
for f in b['floors']:
 coverage=ROOT/f"outputs/CAD-평면연결-v9/office-{f['name']}/source_coverage.json"
 source=Path(json.loads(coverage.read_text('utf8'))['primary']['path']) if coverage.exists() else base/f['src']
 ts=list(texts(ezdxf.readfile(source).modelspace()));tags=[]
 for t in ts:
  if not re.fullmatch(r'[2-5],[0-9]{3}',t['text'].strip()):continue
  x,y=t['point']
  ids=[n for n in ts if re.fullmatch(r'\d{3}',n['text'].strip()) and 400<x-n['point'][0]<1600 and abs(y-n['point'][1])<20]
  if not ids:continue
  label_candidates=[n for n in ts if re.search(r'[가-힣A-Za-z]',n['text']) and 250<n['point'][1]-y<650 and abs(n['point'][0]-ids[0]['point'][0])<2500]
  xy=[t['point'][i]*.001*f['scale']+f['shift'][i]-b['origin'][i] for i in [0,1]]
  tags.append(dict(height_m=int(t['text'].replace(',',''))/1000,room_number=ids[0]['text'],labels=[n['text'] for n in label_candidates],position=xy,native_point=t['point'],source=str(source)))
 for r in f['rooms']:
  if 'outdoor' in r.get('tags',[]):continue
  shape=unary_union([Polygon(p['o'],p['h']) for p in r['polys']]);hits=[t for t in tags if shape.buffer(.05).covers(Point(t['position']))]
  name=' / '.join(r.get('names',[]));k=f"{f['name']}_{r['id']}"
  if hits:
   # When several labels occupy one extracted space, retain the largest clear height,
   # and expose conflicting tags rather than silently treating the room as surveyed.
   h=max(t['height_m'] for t in hits);basis='CAD room-number/height tag';confidence='tag_interpretation'
  elif f['use'] in ['parking','penthouse'] or re.search(r'계단|ELEV\.$|기계실|전기실|발전기',name):h=f['h'];basis='open structural/service volume assumption';confidence='assumed'
  elif re.search(r'화장실|탈의|샤워',name):h=2.4;basis='sanitary room default';confidence='assumed'
  else:h=3.;basis='same-building occupied-room default (observed 3.0 m tags)';confidence='assumed'
  records[k]=dict(height_m=min(f['h'],h),structural_height_m=f['h'],basis=basis,confidence=confidence,tags=hits,room_names=r.get('names',[]))
 evidence.extend(tags)
out=ROOT/'outputs/CAD-가연물묶음-v30'
result=dict(policy='Native CAD tags first; otherwise same-building use-based defaults. Core/vertical vent endpoints retain structural height. Plenum omitted. Boundary thermal material unchanged for controlled comparison.',building_sha256=hashlib.sha256((base/'cad-output/building.json').read_bytes()).hexdigest(),rooms=records,all_tags=evidence)
(ROOT/'work/cfast_ceiling_heights_v30.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
(out/'반자고-도면대조.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
print('tags',len(evidence),'mapped rooms',sum(bool(r['tags']) for r in records.values()))
for k in ['3F_R9','3F_R8','3F_R2']:print(k,json.dumps(records[k],ensure_ascii=False))
