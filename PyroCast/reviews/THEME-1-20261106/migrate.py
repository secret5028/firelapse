from pathlib import Path
import re,json,hashlib,subprocess,sys
ROOT=Path('C:/Users/예방/Documents/ChatGPT/PyroCast')
OUT=Path(__file__).parent
BACK=OUT/'original'
BASE={'bg-scene':'#102331','bg-panel':'#142b3b','bg-card':'#163345','bg-control':'#1d4158','bg-control-hover':'#254353','bg-selected':'#1c3e52','border':'#496273','border-strong':'#577487','text':'#eaf3f8','text-strong':'#fff','text-muted':'#b8cbd8','accent':'#42c4e8','accent-fg':'#102331','ok':'#5fd39a','busy':'#f5b84a','error':'#ff8c6b'}
semantic={'#ef4444','#a855f7','#facc15','#ff5b5b','#b16cff','#f2d14a','#f97316'}
tokens={}; uses=[]; changed=[]
def save(path,text):
    original=path.read_bytes() if path.exists() else None
    # Keep original line endings; text is read with universal newline normalization.
    if original is not None and text==original.decode('utf-8').replace('\r\n','\n'):return
    raw=text.replace('\n','\r\n').encode() if original and b'\r\n' in original else text.encode()
    if raw==original:return
    rel=path.relative_to(ROOT)
    if original is not None:
        dest=BACK/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():dest.write_bytes(original)
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw);changed.append(str(rel).replace('\\','/'))
def css(s):
    def replace(m):
        value=m[0]; low=value.lower()
        if low in semantic:return value
        name=next((k for k,v in BASE.items() if low==v),None)
        if name is None:
            name='compat-'+(low[1:] if low.startswith('#') else hashlib.sha256(low.encode()).hexdigest()[:8])
            tokens[name]=value
        uses.append({'value':value,'token':name})
        return 'var(--'+name+')'
    # Values only: never selectors or SVG IDs. Transparent/currentColor are retained.
    return re.sub(r'#[0-9a-fA-F]{3,8}\b|rgba?\([^()]+\)|(?<![\w-])(?:white|black)(?![\w-])',replace,s)
def js(text):
    # Restrict replacements to CSS source strings, preserving executable expressions.
    pattern=r'((?:style\.textContent|style\.cssText|\.cssText)\s*\+?=\s*)(`[^`]*`|\'[^\'\n]*\'|"[^"\n]*")'
    text=re.sub(pattern,lambda m:m[1]+m[2][0]+css(m[2][1:-1])+m[2][-1],text)
    text=re.sub(r'(style="|style=\')([^"\'<>]*)(["\'])',lambda m:m[1]+css(m[2])+m[3],text)
    text=re.sub(r'(\.style\.(?:color|background|backgroundColor|borderColor)\s*\+?=\s*)([\'"])(#[0-9a-fA-F]{3,8})([\'"])',lambda m:m[1]+m[2]+css(m[3])+m[4],text)
    return text
files=[p for p in (ROOT/'app/web').rglob('*.js') if 'layers' not in p.parts and p.name!='model_review.js']+[ROOT/'app/model-library/operation-controls.js',ROOT/'data/wando-coldstore/operating.js']
for p in files:save(p,js(p.read_text('utf-8')))
p=ROOT/'simulation/viewer/overlay.css';save(p,css(p.read_text('utf-8')))
for rel in ['app/model-library/operation.html','data/wando-coldstore/model.html','simulation/results/github-publish-20261026/PyroCast/cad-project/model.html']:
    p=ROOT/rel;t=p.read_text('utf-8');t=re.sub(r'(<style[^>]*>)([\s\S]*?)(</style>)',lambda m:m[1]+css(m[2])+m[3],t)
    t=t.replace('</head>','<link rel="stylesheet" href="/cfbt/theme.css">\n</head>',1);save(p,t)
theme='/* THEME-1 stage 1: exact original CSS values; compatibility aliases are intentional. */\n:root{\n'+''.join('  --'+k+':'+v+';\n' for k,v in BASE.items())+''.join('  --'+k+':'+v+';\n' for k,v in sorted(tokens.items()))+'}\n'
save(ROOT/'simulation/viewer/theme.css',theme)
p=ROOT/'tools/serve_cfbt_building.py';t=p.read_text('utf-8').replace("('/cfbt/overlay.js','/cfbt/overlay.css'","('/cfbt/theme.css','/cfbt/overlay.js','/cfbt/overlay.css'")
save(p,t)
p=ROOT/'tools/lite_export.py';t=p.read_text('utf-8');needle="    envelope = {'schema': 'pyrocast.offline/1'"
insert="    theme_link = '<link rel=\"stylesheet\" href=\"/cfbt/theme.css\">'\n    theme_style = '<style>'+read('/cfbt/theme.css').decode('utf-8')+'</style>'\n    html = html.replace(theme_link, theme_style) if theme_link in html else html.replace('</head>', theme_style+'</head>')\n"
assert needle in t;t=t.replace(needle,insert+needle);save(p,t)
(OUT/'stage1-files.json').write_text(json.dumps(changed,ensure_ascii=False,indent=2),'utf-8')
(OUT/'tokens.json').write_text(json.dumps({'base':BASE,'compat':tokens,'uses':uses},ensure_ascii=False,indent=2),'utf-8')
print(json.dumps({'changed':changed,'compatibility_tokens':len(tokens),'replacements':len(uses)},ensure_ascii=False))
