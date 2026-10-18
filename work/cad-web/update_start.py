from pathlib import Path
p=Path(__file__).parent/'industrial.js';s=p.read_text(encoding='utf-8')
s=s.replace("fire:null,pick:false", "start:{x:31,z:-14},startPick:false,fire:null,pick:false",1)
a=s.index('function approach(');b=s.index('let solutionCache=',a)
s=s[:a]+'''const exteriorBlocks=[[-.15,-.15,98.75,32.15],[32.8,-19.2,41.2,-16.3]];
function outsideValid(x,z){return x>=-16&&x<=114&&z>=-32&&z<=39&&!exteriorBlocks.some(b=>x>b[0]&&x<b[2]&&z>b[1]&&z<b[3])}
function outsideClear(a,b){const n=Math.ceil(Math.hypot(a[0]-b[0],a[1]-b[1])/.08);for(let i=0;i<=n;i++){const t=n?i/n:0;if(!outsideValid(a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t))return false}return true}
function approach(e){const goal=[e.x,e.z===0?-.3:32.3],points=[[state.start.x,state.start.z],goal];for(const b of exteriorBlocks)points.push([b[0]-.05,b[1]-.05],[b[2]+.05,b[1]-.05],[b[2]+.05,b[3]+.05],[b[0]-.05,b[3]+.05]);const d=points.map(()=>Infinity),prev=points.map(()=>-1),used=new Set();d[0]=0;for(let k=0;k<points.length;k++){let u=-1;for(let i=0;i<points.length;i++)if(!used.has(i)&&(u<0||d[i]<d[u]))u=i;if(u<0||!Number.isFinite(d[u]))break;used.add(u);if(u===1)break;for(let v=0;v<points.length;v++)if(!used.has(v)&&outsideClear(points[u],points[v])){const nd=d[u]+Math.hypot(points[u][0]-points[v][0],points[u][1]-points[v][1]);if(nd<d[v]){d[v]=nd;prev[v]=u}}}if(!Number.isFinite(d[1]))return null;const p=[];for(let i=1;i>=0;i=prev[i])p.unshift([points[i][0],.15,points[i][1]]);p.push([e.x,.15,e.z],[e.inside[0],.15,e.inside[1]]);return p}
const startMarker=new THREE.Group();site.add(startMarker);
function updateStartMarker(){dispose(startMarker);const pts=[];for(let i=0;i<=32;i++)pts.push(V(state.start.x+.5*Math.cos(i/32*Math.PI*2),.1,state.start.z+.5*Math.sin(i/32*Math.PI*2)));stroke(startMarker,pts,0x258dff,.08)}
function selectStart(x,z){if(!outsideValid(x,z))return false;state.start={x,z};state.startPick=false;canvas.style.cursor='';$('startBtn').classList.remove('active');updateStartMarker();updateRoutes();return true}
'''+s[b:]
s=s.replace("for(const side of ['L','E']){const p=[...approach(entry,side),...inside]", "for(const side of ['custom']){const outer=approach(entry);if(!outer)continue;const p=[...outer,...inside]")
s=s.replace('도로 → 대지 진입 → 출입문 → ','진입 위치 → 출입문 → ')
s=s.replace("state.fire=null;state.pick=false;canvas.style.cursor='';", "state.fire=null;state.pick=false;state.startPick=false;$('startBtn').classList.remove('active');canvas.style.cursor='';")
s=s.replace("if(state.pick){let p=new THREE.Vector3();", "if(state.startPick){const p=new THREE.Vector3();if(ray.ray.intersectPlane(new THREE.Plane(V(0,1,0),.15),p)&&!selectStart(p.x,p.z))$('routeHint').textContent='건물과 소방차 밖의 지면을 선택하세요.';return}if(state.pick){let p=new THREE.Vector3();")
s=s.replace("$('fireBtn').onclick=()=>{", "$('startBtn').onclick=()=>{if(state.compare){$('routeHint').textContent='바닥 비교를 종료한 뒤 지정하세요.';return}state.pick=false;$('fireBtn').classList.remove('active');state.startPick=!state.startPick;canvas.style.cursor=state.startPick?'crosshair':'';$('startBtn').classList.toggle('active',state.startPick);$('routeHint').textContent=state.startPick?'외부 지면에서 진입 위치를 클릭하세요.':'진입 위치 지정 취소';};$('startResetBtn').onclick=()=>selectStart(31,-14);\n$('fireBtn').onclick=()=>{state.startPick=false;$('startBtn').classList.remove('active');")
s=s.replace("resize();showSystem('');", "resize();updateStartMarker();showSystem('');")
s=s.replace('coverage,nodes,scaleReference','coverage,nodes,selectStart,approach,outsideValid,startMarker,scaleReference')
p.write_text(s,encoding='utf-8')
p=Path(__file__).parent/'package_industrial.py';s=p.read_text(encoding='utf-8');s=s.replace('<h2>목적 공간</h2><select', '<h2>목적 공간</h2><div><button id="startBtn">진입 위치 지정</button><button id="startResetBtn">출발점 복원</button></div><select');s=s.replace('도로에서 대지 진입구를 거쳐 건물 출입문과 계단을 통과하는 경로입니다.','소방차·사람 옆을 기본 출발점으로 하며 진입 위치 지정으로 외부 지면에서 바꿀 수 있습니다. 건물 출입문과 계단을 통과하는 경로입니다.');s=s.replace('10개 출입구마다 양측 도로 접근 길이를 비교합니다.','10개 출입구마다 지정한 출발점에서의 접근 거리를 비교합니다.');p.write_text(s,encoding='utf-8')
