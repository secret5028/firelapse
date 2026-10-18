from pathlib import Path
p=Path(__file__).with_name('cad_cfast_multifloor_overlay.js')
s=p.read_text('utf8')
def sub(a,b):
 global s
 assert a in s,a[:100]
 s=s.replace(a,b,1)
sub('<select id="cfMode"', '<div class="cfViews"><button id="cfBasic" aria-pressed="true">기본 모드</button><button id="cfReal" aria-pressed="false">실감 보기</button></div><label id="cfCutLabel" hidden><input id="cfCut" type="checkbox" checked> 앞벽 절개 (보기만)</label><select id="cfMode"')
sub('<option value="zones">','<option value="zones" selected>')
sub('<details><summary>층별 계산값</summary><div id="cfFloors"></div></details>', '<details open><summary>시간별 연기 확산</summary><p><small>표시 기준: 광학밀도 OD ≥ 0.001/m<br>도달 시각은 5초 간격 · 위험 기준 아님</small></p><div id="cfFloors"></div><div id="cfSpreadRooms"></div></details>')
sub('#cfPanel button{margin:4px 0}', '#cfPanel button{margin:4px 0}.cfViews{display:flex;gap:5px}.cfViews button{flex:1;padding:7px 2px}.cfViews button[aria-pressed="true"]{background:#ecc677;color:#183245}.cfArrival{display:block;width:100%;text-align:left;font-size:11px;padding:5px}.cfArrival.active{border-left:3px solid #e7bb64}#cfSpreadRooms{margin-top:8px;font-size:11px;line-height:1.6}')
sub('<div>3F 예시 · 계단 / 승강로 / B1↔1F 외기 램프 연결</div>', '<div class="cfRow"><span>경과 시간</span><button data-cf-minute="5">5분</button><button data-cf-minute="10">10분</button><button data-cf-minute="20">20분</button><button data-cf-minute="30">30분</button><span>3F 예시 · 30분까지 1 MW 유지</span></div>')
sub('const meshes=new Map(),cached=new Map()', 'const realRenderer=createCfastRealistic({rows,roots,geometry,fire,centre,floorIndex});\n const arrival=new Map(rows.map(r=>[r.key,r.series.find(v=>Math.max(v[4],v[5])>=.001)?.[0]??null]));\n const meshes=new Map(),cached=new Map()')
sub('optionFloor=null;','optionFloor=null,realView=false;\n'+'''
 // A viewing cut only; geometry and simulation connections are never edited.
 const cutMaterials=[...new Set([...XR.map(k=>mat[k]),...glassM.map(m=>m.material)])],cutPlane=new THREE.Plane();
 let cutBackup=null,outlineBackup=null;
 function cutaway(){
  const on=enabled&&realView&&$('cfCut').checked&&selFloor!=='all';
  if(on){
   if(!cutBackup){cutBackup=cutMaterials.map(m=>[m,m.clippingPlanes,m.opacity]);outlineBackup=$('layer_outline')?.checked;R.localClippingEnabled=true;}
   const r=rowMap.get(selected)||fire,c=centre(r),normal=new THREE.Vector3(c[0]-C.position.x,c[1]-C.position.y,0).normalize();
   const pts=geometry(r).flatMap(p=>p.o),front=Math.min(...pts.map(p=>p[0]*normal.x+p[1]*normal.y));
   cutPlane.normal.copy(normal);cutPlane.constant=-front-.15;
   for(const [m] of cutBackup){m.clippingPlanes=[cutPlane];m.opacity=1;}
   if($('layer_outline')?.checked){$('layer_outline').checked=false;$('layer_outline').dispatchEvent(new Event('change'));}
  }else if(cutBackup){
   for(const [m,planes,opacity] of cutBackup){m.clippingPlanes=planes;m.opacity=opacity;}cutBackup=null;
   if($('layer_outline')&&outlineBackup!==null){$('layer_outline').checked=outlineBackup;$('layer_outline').dispatchEvent(new Event('change'));}outlineBackup=null;
  }
 }
''')
sub("function draw(){choices();const mode=$('cfMode').value;", "function draw(){choices();const mode=realView?'real':$('cfMode').value;")
sub('  const r=rowMap.get(selected)||fire,v=cached.get(r.key)', '  if(realView)for(const m of meshes.values())for(const obj of Object.values(m))obj.visible=false;\n  const r=rowMap.get(selected)||fire,v=cached.get(r.key)')
sub("marker.visible=enabled&&mode!=='fire'", "marker.visible=enabled&&!realView&&mode!=='fire'")
sub("$('cfClock').textContent=fmt(time);", "realRenderer.setState({enabled:enabled&&realView,cached,q,h});cutaway();$('cfBasic').setAttribute('aria-pressed',!realView);$('cfReal').setAttribute('aria-pressed',realView);$('cfMode').hidden=realView;$('cfCutLabel').hidden=!realView;\n  $('cfClock').textContent=fmt(time);")
sub("['smoke','fire','zones'].includes(mode)","['smoke','fire','zones','real'].includes(mode)")
sub("$('cfMeaning').textContent=mode==='zones'?", "$('cfMeaning').textContent=realView?'立体 연기: 계산된 상·하부층 높이와 광학밀도에 연동. 화염은 화점에만 표시. 연기 결·흔들림은 시각 효과입니다.'.replace('立体','입체'):mode==='zones'?")
old="  $('cfFloors').replaceChildren();for(const f of B.floors){const fr=rows.filter(r=>r.floor===f.name),temps=fr.map(r=>cached.get(r.key)[1]),ods=fr.map(r=>cached.get(r.key)[4]),p=document.createElement('div');p.textContent=`${f.name} · 최고 ${Math.max(20,...temps).toFixed(1)}°C · OD ${Math.max(0,...ods).toFixed(3)}`;$('cfFloors').append(p)}"
new="""  $('cfFloors').replaceChildren();for(const f of B.floors){const fr=rows.filter(r=>r.floor===f.name),active=fr.filter(r=>Math.max(...cached.get(r.key).slice(4,6))>=.001),times=fr.map(r=>arrival.get(r.key)).filter(t=>t!==null),first=times.length?Math.min(...times):null,p=document.createElement('button');p.className='cfArrival'+(active.length?' active':'');p.textContent=`${f.name} · ${active.length}/${fr.length}구획 · ${first===null?'30분 내 표시 없음':`첫 표시 ${fmt(first)}`}`;p.onclick=()=>{setFloor(f.name);const target=active.sort((a,b)=>cached.get(b.key)[4]-cached.get(a.key)[4])[0];if(target){selected=target.key;$('cfRoom').value=selected;}iso();draw()};$('cfFloors').append(p)}
  const smoky=rows.filter(r=>(selFloor==='all'||r.floor===selFloor)&&Math.max(...cached.get(r.key).slice(4,6))>=.001).sort((a,b)=>cached.get(b.key)[4]-cached.get(a.key)[4]);$('cfSpreadRooms').replaceChildren();const title=document.createElement('div');title.textContent=`현재 연기 표시 공간 ${smoky.length}개 (농도순)`;$('cfSpreadRooms').append(title);for(const r of smoky){const b=document.createElement('button');b.className='cfArrival';b.textContent=`${r.floor} ${r.id} ${r.name} · OD ${cached.get(r.key)[4].toFixed(3)}`;b.onclick=()=>{setFloor(r.floor);selected=r.key;$('cfRoom').value=selected;draw();$('cfZoneFocus').click()};$('cfSpreadRooms').append(b)}
"""
sub(old,new)
sub('verticalPaths:paths.length,modelHash:hash','verticalPaths:paths.length,modelHash:hash,duration:data.duration,smokeRooms:smoky.length,rendering:realRenderer.stats()')
sub("const t=now/1000,mode=$('cfMode').value;", "const t=now/1000,mode=realView?'real':$('cfMode').value;realRenderer.animate(now);")
sub(" $('cfTime').oninput=e=>", " $('cfBasic').onclick=()=>{realView=false;draw()};$('cfReal').onclick=()=>{realView=true;draw()};$('cfCut').onchange=draw;\n for(const b of timeline.querySelectorAll('[data-cf-minute]'))b.onclick=()=>{time=Math.min(data.duration,+b.dataset.cfMinute*60);playing=false;draw()};\n $('cfTime').oninput=e=>")
# Refresh the clipping plane while orbiting, without triggering geometry changes.
sub("function tick(now){requestAnimationFrame(tick);", "function tick(now){requestAnimationFrame(tick);if(realView)cutaway();")
p.write_text(s,'utf8')
print(p)
