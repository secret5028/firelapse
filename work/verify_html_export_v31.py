from pathlib import Path
from html.parser import HTMLParser
import base64, hashlib, json, re
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'outputs/CAD-HTML내보내기-v31'
class Scripts(HTMLParser):
    def __init__(self):super().__init__();self.scripts=[];self.current=None
    def handle_starttag(self,tag,attrs):
        if tag=='script':self.current=[dict(attrs),'']
    def handle_data(self,data):
        if self.current is not None:self.current[1]+=data
    def handle_endtag(self,tag):
        if tag=='script' and self.current is not None:self.scripts.append(self.current);self.current=None
def check(path):
    p=Scripts();p.feed(path.read_text('utf8'))
    boot=next(s for a,s in p.scripts if s.startswith('(function bootstrap('))
    pack=json.loads(re.search(r'\}\)\((\{.*\})\);$',boot,re.S).group(1))
    hashes={}
    for name in ['building.json','cfast-demo.json']:
        data=base64.b64decode(pack['files'][name]);assert data==(OUT/name).read_bytes()
        hashes[name]=hashlib.sha256(data).hexdigest()
    result=json.loads(base64.b64decode(pack['files']['cfast-demo.json']))
    assert result['building_sha256']==hashes['building.json']
    imports=json.loads(next(s for a,s in p.scripts if a.get('type')=='importmap'))['imports']
    assert len(imports)==4 and all(v.startswith('data:text/javascript;base64,') for v in imports.values())
    for key,uri in imports.items():
        code=base64.b64decode(uri.split(',',1)[1]).decode('utf8')
        for specifier in re.findall(r"\bfrom\s+['\"]([^'\"]+)['\"]",code):assert specifier in imports,specifier
    assert not any(a.get('src') for a,s in p.scripts)
    assert 'CAD_OFFLINE' in pack['source'] and 'HTML 내보내기' in pack['source']
    assert '<script type="importmap">' in pack['source']
    return dict(path=str(path),bytes=path.stat().st_size,hashes=hashes,module_count=len(imports),time=pack['view']['cfast']['time'],floor=pack['view']['floor'],mode=pack['view']['cfast']['mode'],embedded_source_bytes=len(pack['source'].encode()),duration=result['duration'],rooms=len(result['rooms']))
a=check(OUT/'소방-3D-결과.html');b=check(OUT/'재저장-검증.html')
assert a['time']==600 and a['mode']=='real'
assert b['time']==1800 and b['floor']=='all'
assert a['embedded_source_bytes']==b['embedded_source_bytes']
(OUT/'검증결과.json').write_text(json.dumps(dict(first=a,reexport=b,browser_result='HTTP standalone: restored, 156 rooms, 20 fuel units, 30min floor counts verified, no console errors',file_protocol='Direct file:// opening was blocked by browser tool policy; not runtime-tested'),ensure_ascii=False,indent=2),'utf8')
print('Embedded data hashes, four offline modules, result duration, state and non-nesting re-export passed')
