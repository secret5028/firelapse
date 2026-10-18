from pathlib import Path
p=Path('work/app.js');s=p.read_text(encoding='utf-8')
s=s.replace('labels:true,','labels:false,')
s=s.replace("const floorGroups=[],", "const layerNodes={structure:[],doors:[],windows:[],corridors:[],stairs:[],lifts:[]};\nconst floorGroups=[],")
s=s.replace("stairMat=mat('#c89d68')", "stairMat=mat('#ca6570')")
s=s.replace("const mechanicalColor={hydrant:'#e94653',alarmValve:'#e94653'}", "const mechanicalColor={hydrant:'#ffd343',alarmValve:'#ffd343'}")
s=s.replace("'#ff8b92',.72", "'#ffe475',.72")
s=s.replace("walls[f].push([x1,z1,x2,z2]);return o;", "walls[f].push([x1,z1,x2,z2]);layerNodes.structure.push(o);return o;")
s=s.replace('floorMeshes.push(o);outline', 'floorMeshes.push(o);layerNodes.structure.push(o);outline')
for fn,key in [('door','doors'),('windowSlot','windows'),('stairs','stairs')]:
    s=s.replace('function '+fn+'(', 'function build_'+fn+'(',1)
    at=s.index('function build_'+fn+'(')
    s=s[:at]+f'function {fn}(g,...args){{const lg=new THREE.Group();g.add(lg);layerNodes.{key}.push(lg);return build_{fn}(lg,...args)}}\n'+s[at:]
a=s.index('for(const x of [31.8,35.5])');b=s.index('for(const x of [4,10',a)
part=s[a:b].replace('box(g,','box(lg,')
s=s[:a]+"const lg=new THREE.Group();g.add(lg);layerNodes.lifts.push(lg);"+part+s[b:]
at=s.index("const tex=new THREE.TextureLoader()")
s=s[:at]+"const corridor=new THREE.Group();g.add(corridor);layerNodes.corridors.push(corridor);box(corridor,29,H*(f-1)+.025,9.8,2,.035,10.4,mat('#4e8996',.45),{name:'코어 연결 통로',body:'도면의 개방된 연결 공간을 근사한 표시입니다. 벽이나 별도의 방으로 추가한 것이 아닙니다.'});box(corridor,33.7,H*(f-1)+.025,5.3,7.4,.035,1.4,mat('#4e8996',.45));\n"+s[at:]
s=s.replace("routesGroup.visible=targetGroup.visible=state.mode==='detail';", "routesGroup.visible=targetGroup.visible=state.mode==='detail'&&$('layerRoutes').checked;")
s=s.replace("$('invertY').onchange=e=>state.invertY=e.target.checked;",'')
at=s.index("$('opacity').oninput=")
s=s[:at]+"for(const key of Object.keys(layerNodes)){$('layer-'+key).onchange=e=>layerNodes[key].forEach(o=>o.visible=e.target.checked)}$('layerRoutes').onchange=e=>{routesGroup.visible=targetGroup.visible=e.target.checked&&state.mode==='detail'};\n"+s[at:]
s=s.replace("$('selection').innerHTML='';", "$('selectedDetails').open=true;$('selection').innerHTML='';")
p.write_text(s,encoding='utf-8')
p=Path('work/viewer.html');h=p.read_text(encoding='utf-8')
a=h.index('<div class="section"><h2>02 /');b=h.index('<div class="section"><h2>03 /',a)
controls=''
for key,title,color in [('structure','건물','#9ab6c5'),('doors','문·열림 방향','#f45b62'),('windows','창·개구부','#31bfff'),('corridors','복도·연결 공간','#4e8996'),('stairs','계단','#ca6570'),('lifts','승강기','#a9a6ef')]:
    controls+=f'<label class="check"><input id="layer-{key}" type="checkbox" checked><i class="dot" style="background:{color}"></i>{title}</label>'
controls+='<label class="check"><input id="layerRoutes" type="checkbox" checked><i class="dot" style="background:#ff4c61"></i>경로</label><label class="check"><input id="equipment" type="checkbox" checked><i class="dot" style="background:#ffd343"></i>소방시설 · 기계</label><label class="check"><input id="labels" type="checkbox">명칭</label><label class="check"><input id="underlay" type="checkbox">원본 도면</label>'
h=h[:a]+'<div class="section layersection"><h2>레이어</h2>'+controls+'<label class="field">벽 투명도 <span id="opacityText" style="float:right">35%</span></label><input aria-label="벽 불투명도" id="opacity" type="range" min="10" max="90" value="35"></div>'+h[b:]
h=h.replace('01 / 건물과 층','건물과 층').replace('03 / 목적지와 진입 경로','경로').replace('마우스 상하 반전은 기본 켜짐이며 왼쪽에서 해제할 수 있습니다.','마우스 상하 반전은 기본 적용됩니다.').replace('확인된 소화전을 추가할 경우 적색 계열로 표시합니다.','소화전을 포함한 확인된 소방기계는 황색 계열로 표시합니다.')
h=h.replace('<div class="section secondary"><h2>선택 정보</h2>', '<details id="selectedDetails" class="section secondary"><summary>선택 정보</summary>')
h=h.replace('정보를 볼 수 있습니다.</div></div><div class="section secondary">','정보를 볼 수 있습니다.</div></details><div class="section secondary">')
# Fold technical qualifications out of the main working surface, retaining access.
h=h.replace('<div class="section secondary"><h2>소방기계 정보</h2>','<details class="section secondary"><summary>자료 정보</summary>')
h=h.replace('표시하지 않습니다.</div></div><div class="secondary">','표시하지 않습니다.</div></details><details class="secondary">')
h=h.replace('<h2>모델 근거</h2>','<summary>모델 근거</summary>').replace('판독 범위와 가정 보기</button></div></aside>','판독 범위와 가정 보기</button></details></aside>')
h=h.replace('도면 해석 모델 · 현장 미검증','검토용')
h=h.replace('</style>', '''
.workspace{grid-template-columns:245px minmax(0,1fr) 235px}.layersection .check{margin:9px 0}.layersection .dot{flex:none;margin-right:0}.left footer,#floorNote,#pickNote,.right>.section>.note,.routecard p{display:none}.right .warning{font-size:12px;padding:6px 8px}.headright .badge{font-size:12px}summary{cursor:pointer;font-size:13px;color:#8ca8bf;margin-bottom:8px}.stageheading .sub{font-size:11px}.right .section{margin-bottom:10px;padding-bottom:12px}.routecard{padding:10px}.routecard b{font-size:13px}.routecard .distance{font-size:12px}.smalltitle{font-size:14px}.bottom .helpinline{display:none}@media(max-width:1150px){.workspace{grid-template-columns:225px minmax(0,1fr)}}@media(max-width:720px){.workspace{grid-template-columns:1fr}}
</style>''')
p.write_text(h,encoding='utf-8')
print('Layer controls added; mechanical yellow; labels off; inverted mouse fixed default; metadata folded.')
