from pathlib import Path
p=Path('work/app.js');s=p.read_text(encoding='utf-8')
s=s.replace('chosen:0}', 'chosen:0,invertY:true}')
a=s.index('function door(');b=s.index('function slab(',a)
s=s[:a]+'''function door(g,f,x,z,width,vertical){
const y=H*(f-1),known=(Math.abs(x)<.01)||(Math.abs(z-15)<.01)||(Math.abs(z-4.6)<.01);
let sign=1;if(Math.abs(x)<.01&&z<6)sign=-1;if(Math.abs(z-4.6)<.01)sign=-1;
const color=known?'#ffc45f':'#e59e51',m=mat(color,.9),ux=vertical?0:1,uz=vertical?1:0;
const info={name:'D동 '+f+'층 문 · '+(known?'열림 방향 판독':'열림 방향 미확인'),body:known?'도면의 문 열림 호를 바탕으로 방향을 근사했습니다. 노란 문짝과 화살표가 열리는 방향을 나타냅니다. 정확한 폭·힌지 위치는 현장 미확인입니다.':'문 위치 후보입니다. 점선 호는 임시 열림 방향으로 실제 방향이 확정되지 않았습니다.'};
const hx=x-ux*width/2,hz=z-uz*width/2;
for(const t of [-1,1])box(g,x+ux*width/2*t,y+1.1,z+uz*width/2*t,.12,2.2,.12,m,info);
const lintel=box(g,x,y+2.24,z,vertical?.14:width+.18,.14,vertical?width+.18:.14,m,info);
const angle=sign*Math.PI*.4,vx=ux*Math.cos(angle)-uz*Math.sin(angle),vz=ux*Math.sin(angle)+uz*Math.cos(angle);
const leaf=box(g,hx+vx*width/2,y+1.05,hz+vz*width/2,width,2.1,.075,mat(color,.6),info);leaf.rotation.y=-Math.atan2(vz,vx);outline(leaf,color);
for(let i=0;i<24;i++){if(!known&&i%3===1)continue;const aa=sign*i/24*Math.PI/2,bb=sign*(i+1)/24*Math.PI/2;
const point=a=>({x:hx+(ux*Math.cos(a)-uz*Math.sin(a))*width,y:y+.22,z:hz+(ux*Math.sin(a)+uz*Math.cos(a))*width});drawSegment(g,point(aa),point(bb),color,.032)}
const end=sign*Math.PI/2,ex=hx+(ux*Math.cos(end)-uz*Math.sin(end))*width,ez=hz+(ux*Math.sin(end)+uz*Math.cos(end))*width;
const arrow=new THREE.Mesh(new THREE.ConeGeometry(.13,.35,8),new THREE.MeshBasicMaterial({color}));arrow.position.set(ex,y+.22,ez);arrow.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),new THREE.Vector3(sign*(-ux*Math.sin(end)-uz*Math.cos(end)),0,sign*(ux*Math.cos(end)-uz*Math.sin(end))).normalize());g.add(arrow);
box(g,x,y+.035,z,vertical?.5:width,.07,vertical?width:.5,mat(color,.8),info);
}
''' + s[b:]
a=s.index('function windowSlot(');b=s.index('function stairs(',a)
s=s[:a]+'''function windowSlot(g,f,x,z,w,vertical=false){const y=H*(f-1),info={name:'창문 / 개구부 후보',body:'청색 프레임은 도면 배경선에서 추정한 창문입니다. 창의 개폐 방식·높이·치수는 미확인입니다.'};
const glass=box(g,x,y+1.45,z,vertical?.24:w,1.15,vertical?w:.24,mat('#31bfff',.78),info);outline(glass,'#75e2ff');windowMats.push(glass.material);
for(const h of [.86,2.04])box(g,x,y+h,z,vertical?.28:w+.16,.10,vertical?w+.16:.28,mat('#76dfff'),info);
for(const t of [-.5,0,.5])box(g,x+(vertical?0:w*t),y+1.45,z+(vertical?w*t:0),.10,1.2,.28,mat('#76dfff'),info);}
''' + s[b:]
# Place the outdoor approach in the detail view; it is a local, approximate apron.
a=s.index('label(model,\'좌측 출입문')
s=s[:a]+'''const apron=box(model,16,-.08,20,54,.10,7,mat('#485d69'));outline(apron,'#7994a5');
box(model,-6,-.08,10,8,.10,15,mat('#485d69'));
label(model,'외부 접근 · 주출입구 후보',-6,.6,21,'#7df0d4',1);
''' + s[a:]
a=s.index('const routeCache=');b=s.index('let currentRoutes=',a)
s=s[:a]+'''const routeCache=new Map();
function roomEntry(side,t){if(t.f===1)return state.entrance==='west'?{x:0,z:10.5,f:1}:{x:30.2,z:15,f:1};return side==='west'?{x:0,z:4.1,f:2}:{x:31.3,z:4.6,f:2}}
function calcRoutes(){const cacheKey=JSON.stringify([state.entrance,state.target,state.fire]);if(routeCache.has(cacheKey))return routeCache.get(cacheKey);
const west=state.entrance==='west',start=west?{x:.7,z:10.5}:{x:30.2,z:14.5},t=state.target,result=[];
const outside=(west?[{x:-7,z:21},{x:-7,z:10.5},{x:-.35,z:10.5}]:[{x:30.2,z:23},{x:30.2,z:15.35}]).map(p=>({...p,y:.15,f:1,external:true}));
const entry=west?{x:0,z:10.5,y:.15,f:1}:{x:30.2,z:15,y:.15,f:1};
if(t.f===1){if(state.fire){const p=pathfind(start,t,1);if(p)result.push({name:'외부에서 1층 진입',description:'외부 → 출입문 → 지정 화점 후보',points:[...outside,entry,...p]})}else result.push({name:'1층 방 출입문 도착',description:'외부 → 선택 공간의 출입문에서 종료',points:[...outside,entry]})}
else for(const side of ['west','east']){const sp=stairPoints(side),end=state.fire?t:roomEntry(side,t),a=pathfind(start,sp[0],1),b=pathfind(sp.at(-1),end,2);if(a&&b)result.push({name:side==='west'?'좌측 계단 경유':'우측 계단 경유',description:'외부 → 출입문 → '+(side==='west'?'좌측':'우측')+' 계단 → '+(state.fire?'화점 후보':'방 진입문'),points:[...outside,entry,...a,...sp.slice(1,-1),...b]})}
for(const r of result)r.length=r.points.reduce((sum,p,i)=>i?sum+Math.hypot(p.x-r.points[i-1].x,p.y-r.points[i-1].y,p.z-r.points[i-1].z):0,0);routeCache.set(cacheKey,result);return result}
''' + s[b:]
# The final endpoint marker belongs to a room entrance unless a fire was placed.
s=s.replace('const t=state.target;if(state.floor', "const endpoint=currentRoutes[Math.max(0,state.chosen)]?.points.at(-1);const t=state.fire?state.target:(endpoint?{x:endpoint.x,z:endpoint.z,f:state.target.f}:state.target);if(state.floor")
s=s.replace("state.fire?'지정 화점 후보':'목적지'", "state.fire?'지정 화점 후보':'방 진입문 · 경로 끝'")
s=s.replace("$('destination').selectedOptions[0].textContent;", "$('destination').selectedOptions[0].textContent+' · 문까지';")
s=s.replace('cam.phi+dy*.006', 'cam.phi+dy*.006*(state.invertY?-1:1)')
s=s.replace("$('resetBtn').onclick=", "$('invertY').onchange=e=>state.invertY=e.target.checked;$('resetBtn').onclick=")
# Recenter an ordinary click on geometry without consuming dedicated fire selection.
needle="const hits=raycaster.intersectObjects(pickables.filter(effectivelyVisible),false);"
s=s.replace(needle,"const surfaces=raycaster.intersectObjects((state.mode==='detail'?model:site).children,true).filter(h=>h.object.isMesh&&effectivelyVisible(h.object));if(surfaces.length){target.copy(surfaces[0].point);updateCamera();}else{const p=new THREE.Vector3();if(raycaster.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0,1,0),state.mode==='detail'?-H*((Number(state.floor)||1)-1):0),p)){target.copy(p);updateCamera();}}"+needle)
# Ensure selected room entrance is exact rather than a snapped nearby grid point.
s=s.replace("const p=pathfind(start,t,1);", "const p=pathfind(start,t,1);")
p.write_text(s,encoding='utf-8')
p=Path('work/viewer.html');h=p.read_text(encoding='utf-8')
h=h.replace('출발 출입문','외부 진입 방향').replace('D동 좌측 출입문 · 1층','외부 → 주출입구 후보 · 좌측').replace('D동 우측 코어 출입문 · 1층','외부 → 보조출입구 후보 · 우측')
h=h.replace('2층 전시공간 중앙','2층 전시공간').replace('2층 승강기 앞','2층 코어 연결 공간').replace('1층 대공간 중앙','1층 대공간')
h=h.replace('<label class="check"><input id="labels"', '<label class="check"><input id="invertY" type="checkbox" checked> 마우스 상하 반전</label><label class="check"><input id="labels"')
h=h.replace('background:#47c9de','background:#ffc45f').replace('문·창문</span>','문·열림 방향</span><span><i class="dot" style="background:#31bfff"></i>창문</span>')
h=h.replace('적색은 목적지로 향하는 진입 후보입니다.','화점 미지정 시 선택 공간의 진입문에서 끝납니다. 지정 시 화점 후보까지 이어집니다.')
h=h.replace('휠 누름 회전 · Shift+휠 누름 이동 · 휠 확대','클릭 중심 이동 · 휠 누름 회전 · Shift 이동 · 휠 확대')
h=h.replace('<p><b>터치:</b>', '<p><b>회전 중심:</b> 평상시 클릭한 지점으로 중심이 이동합니다. 화점 지정 대기 중에는 클릭이 화점 지정으로 작동합니다. 마우스 상하 반전은 기본 켜짐이며 왼쪽에서 해제할 수 있습니다.</p><p><b>터치:</b>')
h=h.replace('서측·동측','좌측·우측')
h=h.replace('<li>화점 지정은', '<li>외부 접근 구간은 상세 모델 주변의 평탄한 접근 공간을 근사한 것입니다. 배치도와의 정밀 좌표 연결은 미완료이며 주·보조출입구 대응은 후보입니다.</li><li>노란 문짝과 화살표는 열림 방향을 강조합니다. 점선 호는 방향 미확인입니다. 화점이 없으면 선택 공간으로 들어가는 계단 연결문 또는 외부 출입문에서 경로가 끝납니다.</li><li>화점 지정은')
p.write_text(h,encoding='utf-8')
print('Updated exterior access, room entry endpoints, opening direction, windows, inverted orbit, click pivot.')
