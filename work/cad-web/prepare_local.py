from pathlib import Path
import shutil
p=Path('work/local-resources');p.mkdir(exist_ok=True)
for name in ['three.core.js','three.module.js','local_index.html','hydraulic-core.js','hydraulic-ui.js','hydraulic-view.js','drawing-llm-ui.js']:shutil.copyfile(Path('work')/name,p/name)
index=(p/'local_index.html').read_text('utf-8').replace('</header>','<button id="stop">실행 종료</button></header>',1)
index=index.replace('refresh();setInterval',"$('stop').onclick=async()=>{await api('/api/stop',{method:'POST',body:'{}'});document.body.textContent='소방 크로키 업를 종료했습니다. 이 창을 닫아도 됩니다.'};refresh();setInterval")
(p/'local_index.html').write_text(index,'utf-8')
s=Path('work/folder_review.html').read_text('utf-8')
s=s.replace("included:false,shapes:[]}","included:false,shapes:[],...p.initial}")
s=s.replace('PDF·이미지의 페이지는 자동으로 추출했습니다. 이 새 도면의 벽·문·창 자동 판독과 방·층간 연결은 아직 구현되지 않았습니다.','DWG·DXF는 선과 레이어를 추출합니다. CAD 레이어를 벽·문·창으로 지정하면 같은 3D 화면에 반영됩니다. PDF·이미지는 페이지를 추출하며 구조 보정이 필요합니다.')
s=s.replace('<label>도면 보정</label>','<details open id="cadPanel"><summary>CAD 레이어 분류</summary><p id="units" class="note"></p><div id="cadLayers"></div><button id="applyCad">분류 적용</button></details><label>도면 보정</label>')
s=s.replace("status();if(mode==='3d')render3d()}","cadControls();status();if(mode==='3d')render3d()}")
s=s.replace("const c=$('plan')", "const c=$('plan')")
code="""
function cadControls(){const page=D.pages[index];$('cadPanel').hidden=!page.cad;$('cadLayers').replaceChildren();if(!page.cad)return;$('units').textContent=page.unitNote+' · 불필요한 도곽·치수는 제외하세요.';const layers=[...new Set(page.cad.map(l=>l.layer))];for(const layer of layers){const row=document.createElement('label');row.textContent=layer;row.style.fontSize='11px';const sel=document.createElement('select');sel.dataset.layer=layer;sel.style.width='100%';for(const [val,label] of [['','제외'],['wall','벽'],['door','문'],['window','창']]){const o=document.createElement('option');o.value=val;o.textContent=label;sel.append(o)}sel.value=current().mapping?.[layer]||'';row.append(sel);$('cadLayers').append(row)}}
$('applyCad').onclick=()=>{const mapping={};for(const e of $('cadLayers').querySelectorAll('select'))mapping[e.dataset.layer]=e.value;current().mapping=mapping;current().shapes=current().shapes.filter(s=>!s.cad);for(const line of D.pages[index].cad){const type=mapping[line.layer];if(!type)continue;for(let i=1;i<line.p.length;i++)current().shapes.push({type,a:line.p[i-1],b:line.p[i],cad:true})}draw();text('레이어를 적용했습니다. 층 도면으로 지정하고 3D 검토를 누르세요.');persist()};
function persist(){if(window.LOCAL_JOB)fetch('/api/jobs/'+window.LOCAL_JOB+'/state',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(state)}).then(r=>{if(!r.ok)throw Error('저장 실패')}).catch(e=>text(e.message))}
setInterval(()=>{if(window.LOCAL_JOB)persist()},10000);
"""
s=s.replace("D.pages.forEach((p,i)=>",code+"\nD.pages.forEach((p,i)=>")
s=s.replace("$('save').onclick=()=>download", "$('save').onclick=()=>{persist();return download")
s=s.replace("JSON.stringify(state,null,2));$('load')", "JSON.stringify(state,null,2))};$('load')")
s=s.replace('<button id="zoomIn">','<button id="resetView">시점 복원</button><label style="margin:0">벽 투명도 <input id="opacity" type="range" min="0" max="95" value="55" style="width:80px"></label><button id="zoomIn">')
s=s.replace("let theta=.5,phi=.7,radius=55,target=new T.Vector3();", "let theta=.5,phi=.7,radius=55,target=new T.Vector3(),framed=false,homeTarget=new T.Vector3(),homeRadius=55;$('resetView').onclick=()=>{theta=.5;phi=.7;target.copy(homeTarget);radius=homeRadius;cameraUpdate()};$('opacity').oninput=()=>group.traverse(o=>{if(o.material?.transparent&&!o.userData.firePosition&&!o.userData.fireBackbone&&!o.userData.supplyContext)o.material.opacity=1-Number($('opacity').value)/100});")
s=s.replace("bounds.getCenter(target);radius=Math.max(20,bounds.getSize(new T.Vector3()).length()*1.25);", "bounds.getCenter(homeTarget);homeRadius=Math.max(20,bounds.getSize(new T.Vector3()).length()*1.25);if(!framed){target.copy(homeTarget);radius=homeRadius;framed=true;}")
s=s.replace(".45);", "(1-Number($('opacity').value)/100));")
s=s.replace('</html>', '<script>'+Path('work/touch-view.js').read_text('utf-8')+'\n'+Path('work/elevator-display.js').read_text('utf-8')+'\n'+Path('work/wall-surface.js').read_text('utf-8')+'\n'+Path('work/floor-details.js').read_text('utf-8')+'\n'+Path('work/drawing-workflow.js').read_text('utf-8')+'\n'+Path('work/drawing-gap.js').read_text('utf-8')+'\n'+Path('work/review-layout.js').read_text('utf-8')+'\n'+Path('work/fire-facilities.js').read_text('utf-8')+'\n'+Path('work/water-equipment.js').read_text('utf-8')+'\n'+Path('work/atrium.js').read_text('utf-8')+'\n'+Path('work/model-quality.js').read_text('utf-8')+'\n'+Path('work/water-supply-defaults.js').read_text('utf-8')+'</script></html>')
(p/'folder_review.html').write_text(s,'utf-8')
tools=p/'cad-tools';tools.mkdir(exist_ok=True)
for f in Path('work/cad-tools/libredwg').glob('*'):
 if f.suffix=='.dll' or f.name in ('dwg2dxf.exe','README.txt'):shutil.copyfile(f,tools/f.name)
print('Prepared common viewer and bundled CAD converter')

shutil.copy2('work/interpretation-ui.js',p/'interpretation-ui.js')
