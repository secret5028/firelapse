"""Add a local, interactive overlay for excluded CAD opening connections."""
import json
import html
import re
from pathlib import Path


def enhance_review(out):
    out=Path(out)
    p=json.loads((out/'plan.json').read_text(encoding='utf-8'))
    graph=json.loads((out/'simulation_graph.json').read_text(encoding='utf-8'))
    excluded={o['id']:o['reason'] for o in graph['excluded_openings'] if o['reason'] in ('same_space','unresolved')}
    ra=p['raster'];items=[]
    for o in p['openings']:
        if o['id'] not in excluded:continue
        polys=[[[round((x*1000-ra['x0'])/ra['R'],2),round((ra['y1']-y*1000)/ra['R'],2)] for x,y in poly] for poly in o['polys']]
        points=[pt for poly in polys for pt in poly]
        if not points:raise ValueError('Missing review geometry '+o['id'])
        xs,ys=zip(*points)
        items.append(dict(id=o['id'],number=len(items)+1,reason=excluded[o['id']],
            kind='문 후보' if o['kind'].startswith('door') else '창 후보',sides=o.get('sides',[]),evidence_note=o.get('symbol_evidence',{}).get('note',''),
            x=(min(xs)+max(xs))/2,y=(min(ys)+max(ys))/2,polys=polys))
    assert len(items)==len(excluded)
    page=(out/'index.html').read_text(encoding='utf-8')
    if 'id="opening-review"' in page:return items
    css='''
#stage{position:relative;width:100%;line-height:0}#stage #drawing{width:100%!important}
#opening-overlay{position:absolute;inset:0;pointer-events:none}#opening-overlay svg{position:absolute;inset:0;width:100%;height:100%;overflow:visible}
.opening-pin{position:absolute;pointer-events:auto;line-height:1.1;padding:6px 8px;background:#9b102b;color:white;border:2px solid white;border-radius:7px;font-size:12px;font-weight:800;white-space:nowrap;box-shadow:0 0 0 2px #9b102b,0 2px 7px #0005;z-index:2;transform:translate(-50%,-50%)}
.opening-pin.selected{background:#ffdf59;color:#39120c;box-shadow:0 0 0 3px #491017;z-index:3}
.opening-shape{fill:#e72e52;fill-opacity:.38;stroke:#8f0024;stroke-width:4;vector-effect:non-scaling-stroke}
.opening-halo{fill:none;stroke:white;stroke-width:8;vector-effect:non-scaling-stroke}
.opening-line{stroke:#9b102b;stroke-width:2;vector-effect:non-scaling-stroke}
.opening-shape.selected{fill:#ffe261;fill-opacity:.7;stroke:#4b0715;stroke-width:5}
#opening-review{border:2px solid #ab1b39;border-radius:10px;padding:13px;margin-bottom:18px;background:#fff8f9}
#opening-review h2{margin:0;color:#94122f}#opening-review p{font-size:13px;line-height:1.6}
.review-controls{display:flex;gap:7px;flex-wrap:wrap;margin:10px 0}.review-controls button{font-size:12px;padding:6px 8px}
#review-filter{max-width:100%;padding:7px;border:1px solid #d8b0b8;border-radius:6px}
#opening-list{list-style:none;padding:0;margin:10px 0;max-height:36vh;overflow:auto}
#opening-list li{margin:6px 0}#opening-list button{width:100%;text-align:left;background:white;border-color:#e6c1c9;padding:9px;line-height:1.5}
#opening-list button[aria-pressed=true]{background:#fff1b6;border:2px solid #9b102b}
.opening-reason{display:block;color:#663c46;font-size:12px}.review-empty{background:#edf5ef;padding:10px;color:#245538}
'''
    rows=[]
    reason_text={'same_space':'양쪽이 같은 공간으로 판독됨','unresolved':'연결 상대를 확인하지 못함'}
    for item in items:
        sides=' ↔ '.join('미확정' if s is None else ('외기' if s=='out' else s) for s in item['sides'])
        reason_label='외기측 확인 · 실내 공간 미확정' if item['reason']=='unresolved' and 'out' in item['sides'] else reason_text[item['reason']]
        rows.append(f'<li data-reason="{item["reason"]}"><button type="button" data-opening="{item["number"]}" aria-pressed="false"><b>⚠ {item["number"]:02d} · {html.escape(item["id"])} ({item["kind"]})</b><span class="opening-reason">{reason_label}<br>{html.escape(sides)}<br>{html.escape(item["evidence_note"])}</span></button></li>')
    panel=f'''<section id="opening-review"><h2>개구부 연결 확인 · {len(items)}개</h2>
<p>짙은 빨강 테두리와 ⚠ 번호가 확인 대상입니다.<br>목록이나 도면 번호를 누르면 해당 위치를 확대합니다.</p>
<p>‘양쪽 같은 공간’은 불필요한 선이거나 구획 분리 누락일 수 있습니다. 확정 오류를 뜻하지 않습니다.</p>
<div class="review-controls"><button id="review-all" type="button">전체 도면</button><label><input id="review-visible" type="checkbox" checked>표시 켜기</label></div>
<select id="review-filter" aria-label="개구부 확인 사유"><option value="all">모든 확인 대상 ({len(items)})</option><option value="unresolved">연결 상대 미확정 ({sum(i['reason']=='unresolved' for i in items)})</option><option value="same_space">양쪽 같은 공간 ({sum(i['reason']=='same_space' for i in items)})</option></select>
<ul id="opening-list">{''.join(rows)}</ul>'''
    if not items:panel+='<p class="review-empty">이 층의 불명확한 개구부 연결은 0개입니다.</p>'
    rejected=p.get('rejected_openings',[])
    if rejected:
        labels=', '.join(html.escape(o['id']) for o in rejected)
        panel+=f'<details><summary>근거 검토 후 제외한 후보 {len(rejected)}개</summary><p>{labels}</p><p>문·창 목록과 3D 개구부에서 제외했습니다. 원본 CAD와 판정 근거는 보존합니다.</p><p><a href="rejected_openings.json">제외 후보와 근거</a></p></details>'
    panel+='</section>'
    page=page.replace('</style>',css+'</style>',1)
    page=page.replace('<aside>','<aside>'+panel,1)
    page=re.sub(r'(<img id="drawing"[^>]*>)',r'<div id="stage">\1<div id="opening-overlay"></div></div>',page,count=1)
    payload=json.dumps(dict(width=ra['W'],height=ra['H'],items=items),ensure_ascii=False).replace('<','\\u003c')
    js='''
const review=__DATA__,im=document.getElementById('drawing'),stage=document.getElementById('stage'),canvas=document.getElementById('canvas'),overlay=document.getElementById('opening-overlay');
const zoom=document.getElementById('zoom'),visible=document.getElementById('review-visible'),filter=document.getElementById('review-filter');
const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox',`0 0 ${review.width} ${review.height}`);svg.setAttribute('preserveAspectRatio','none');overlay.append(svg);
const nodes=new Map();let selected=null;
function element(tag,attrs){const e=document.createElementNS(ns,tag);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,v));svg.append(e);return e;}
review.items.forEach(item=>{const group=document.createElementNS(ns,'g');svg.append(group);item.polys.forEach(poly=>{const pts=poly.map(p=>p.join(',')).join(' ');['opening-halo','opening-shape'].forEach(cls=>{const p=document.createElementNS(ns,'polygon');p.setAttribute('points',pts);p.setAttribute('class',cls);group.append(p);});});
const line=element('line',{class:'opening-line',x1:item.x,y1:item.y,x2:item.x,y2:item.y});
const pin=document.createElement('button');pin.className='opening-pin';pin.type='button';pin.textContent=`⚠ ${String(item.number).padStart(2,'0')} ${item.id}`;pin.setAttribute('aria-label',`${item.id} 위치 확대`);pin.onclick=()=>selectOpening(item.number);overlay.append(pin);nodes.set(item.number,{group,line,pin,item});});
function layout(){const w=stage.clientWidth,h=im.clientHeight;if(!w||!h)return;const placed=[];const show=visible.checked&&!im.getAttribute('src').startsWith('before')&&!im.getAttribute('src').startsWith('architecture');overlay.hidden=!show;
nodes.forEach(node=>{const {item,pin,group,line}=node,ok=filter.value==='all'||filter.value===item.reason;pin.hidden=!ok;group.style.display=ok?'':'none';line.style.display=ok?'':'none';if(!ok)return;
const x=item.x/review.width*w,y=item.y/review.height*h,bw=pin.offsetWidth||85,bh=pin.offsetHeight||30;let chosen;
for(const dy of [-30,30,-65,65,-100,100,0]){for(const dx of [0,90,-90,180,-180]){const cx=Math.max(bw/2+3,Math.min(w-bw/2-3,x+dx)),cy=Math.max(bh/2+3,Math.min(h-bh/2-3,y+dy)),box={l:cx-bw/2-5,r:cx+bw/2+5,t:cy-bh/2-5,b:cy+bh/2+5};if(!placed.some(p=>box.l<p.r&&box.r>p.l&&box.t<p.b&&box.b>p.t)){chosen={cx,cy,box};break;}}if(chosen)break;}
chosen=chosen||{cx:x,cy:y,box:{l:x-bw/2,r:x+bw/2,t:y-bh/2,b:y+bh/2}};placed.push(chosen.box);pin.style.left=chosen.cx+'px';pin.style.top=chosen.cy+'px';line.setAttribute('x2',chosen.cx/w*review.width);line.setAttribute('y2',chosen.cy/h*review.height);
pin.classList.toggle('selected',item.number===selected);group.querySelectorAll('.opening-shape').forEach(p=>p.classList.toggle('selected',item.number===selected));});}
function setZoom(value){zoom.value=value;stage.style.width=value+'%';document.getElementById('z').textContent=value+'%';requestAnimationFrame(layout);}
function setLayer(src){im.src=src;document.querySelectorAll('[data-src]').forEach(b=>b.classList.toggle('on',b.dataset.src===src));requestAnimationFrame(layout);}
function selectOpening(number){const node=nodes.get(number);if(!node)return;selected=number;visible.checked=true;filter.value='all';applyFilter();setLayer('fused.png');setZoom(Math.max(250,Number(zoom.value)));
document.querySelectorAll('[data-opening]').forEach(b=>b.setAttribute('aria-pressed',Number(b.dataset.opening)===number?'true':'false'));
requestAnimationFrame(()=>requestAnimationFrame(()=>{layout();canvas.scrollTo({left:node.item.x/review.width*stage.clientWidth-canvas.clientWidth/2,top:node.item.y/review.height*im.clientHeight-canvas.clientHeight/2,behavior:'auto'});}));}
function applyFilter(){document.querySelectorAll('#opening-list li').forEach(li=>li.hidden=filter.value!=='all'&&filter.value!==li.dataset.reason);layout();}
document.querySelectorAll('[data-opening]').forEach(b=>b.onclick=()=>selectOpening(Number(b.dataset.opening)));
document.querySelectorAll('[data-src]').forEach(b=>b.onclick=()=>setLayer(b.dataset.src));
zoom.oninput=e=>setZoom(Number(e.target.value));visible.onchange=layout;filter.onchange=applyFilter;
document.getElementById('review-all').onclick=()=>{selected=null;filter.value='all';visible.checked=true;applyFilter();setLayer('fused.png');setZoom(100);canvas.scrollTo(0,0);document.querySelectorAll('[data-opening]').forEach(b=>b.setAttribute('aria-pressed','false'));};
im.onload=layout;new ResizeObserver(layout).observe(stage);requestAnimationFrame(layout);
'''.replace('__DATA__',payload)
    page=re.sub(r'<script>.*?</script>',lambda m:'<script>'+js+'</script>',page,flags=re.S,count=1)
    (out/'index.html').write_text(page,encoding='utf-8')
    return items


if __name__=='__main__':
    import sys
    for directory in sys.argv[1:]:print(directory,len(enhance_review(directory)))
