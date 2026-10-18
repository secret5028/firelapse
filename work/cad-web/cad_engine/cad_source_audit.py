"""Portable all-layer inspection and source coverage, without browser fetch."""
import json,html,hashlib
from pathlib import Path


def verify_drawing_manifest(manifest,source,floor):
    data=json.loads(Path(manifest).read_text(encoding='utf8'))
    sha=hashlib.sha256(Path(source).read_bytes()).hexdigest()
    records=data['drawings']
    match=[r for r in records if r.get('sha256')==sha and r.get('floor')==floor and r.get('role')=='architectural_plan']
    if len(match)!=1:raise ValueError('Primary CAD hash/floor is not uniquely registered in drawing manifest')
    # Other sheets are context only unless the separate registration/fusion
    # stage has actually produced verified geometry or symbol evidence.
    return dict(primary=match[0],related=[r for r in records if floor in r.get('floors',[]) or r.get('floor')==floor],
                geometry_sources=[sha],coverage_note=data.get('coverage_note',''),all_drawings=records)


def write_layer_viewer(plan,path):
    payload=json.dumps(dict(vectors=plan['source_vectors'],evidence=plan.get('layer_evidence',{})),ensure_ascii=False).replace('<','\\u003c')
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>전체 레이어 대조</title>
<style>body{font:15px/1.7 system-ui;margin:20px;color:#20334b}canvas{width:100%;height:78vh;border:1px solid #ccd;background:white}select,button,input{padding:7px}#info{white-space:pre-wrap}a{color:#1264a3}</style>
<h1>전체 레이어 대조</h1><p><a href="index.html">추출 결과</a> · 모든 원본 선을 보존합니다. 회색은 벽으로 채택하지 않은 선, 주황은 복구한 벽, 초록은 문입니다.</p>
<label>레이어 <select id="layer"><option value="">전체</option></select></label> <label>범위 <select id="scope"><option value="plan">추출 영역</option><option value="sheet">전체 도면</option></select></label>
<label><input id="accepted" type="checkbox"> 채택한 벽·문·창만</label> <label>확대 <input id="zoom" type="range" min="1" max="5" step=".2" value="1"></label>
<p id="info"></p><div style="overflow:auto;max-height:80vh"><canvas id="c"></canvas></div>
<script>const D=__DATA__, R=__RASTER__, sel=document.getElementById('layer'), cv=document.getElementById('c'), ctx=cv.getContext('2d');
for(const n of [...new Set(D.vectors.map(v=>v.layer))].sort()){const o=document.createElement('option');o.value=n;o.textContent=n;sel.append(o)}
function draw(){let v=D.vectors.filter(v=>(!sel.value||v.layer===sel.value)&&(!document.getElementById('accepted').checked||!v.excluded_from_boundary));
let x0=R.x0/1000,x1=x0+R.W*R.R/1000,y1=R.y1/1000,y0=y1-R.H*R.R/1000;
if(document.getElementById('scope').value==='sheet'&&v.length){x0=Infinity;y0=Infinity;x1=-Infinity;y1=-Infinity;for(const a of v)for(const [x,y]of a.points){x0=Math.min(x0,x);x1=Math.max(x1,x);y0=Math.min(y0,y);y1=Math.max(y1,y)}}
const zoom=+document.getElementById('zoom').value,w=1300*zoom,h=850*zoom,pad=20,s=Math.min((w-2*pad)/Math.max(.01,x1-x0),(h-2*pad)/Math.max(.01,y1-y0));cv.width=w;cv.height=h;cv.style.width=100*zoom+'%';cv.style.height=78*zoom+'vh';ctx.clearRect(0,0,w,h);
const X=x=>pad+(x-x0)*s,Y=y=>pad+(y1-y)*s;
for(const a of v){if(!a.points.length)continue;ctx.strokeStyle=a.source.derived?'#df6200':({wall:'#30343b',column:'#7d3030',door:'#16934b',window:'#157ec1'}[a.category]||'#aab0b7');ctx.lineWidth=a.source.derived?2:1;ctx.beginPath();if(a.entity==='ARC'&&a.arc){let[cx,cy,r,b,e]=a.arc;let sweep=(e-b+360)%360;ctx.arc(X(cx),Y(cy),r*s,-b*Math.PI/180,-(b+sweep)*Math.PI/180,true)}else{a.points.forEach(([x,y],i)=>i?ctx.lineTo(X(x),Y(y)):ctx.moveTo(X(x),Y(y)));if(a.closed)ctx.closePath()}ctx.stroke()}
document.getElementById('info').textContent='표시 '+v.length+'개 / 전체 '+D.vectors.length+'개 · 검사 레이어 '+D.evidence.scanned_layers.length+'개 · 복구 벽선 조각 '+D.evidence.derived_wall_pieces+'개';}
document.querySelectorAll('select,input').forEach(x=>x.oninput=draw);draw();</script></html>'''
    page=page.replace('__DATA__',payload).replace('__RASTER__',json.dumps(plan['raster']))
    Path(path).write_text(page,encoding='utf8')
