from pathlib import Path
p=Path('work/app.js');s=p.read_text(encoding='utf-8')
for old,new in [('#ca6570','#cdb34e'),('#f45b62','#ffd343'),('#be656a','#bfa352'),('#31bfff','#ffe375'),('#75e2ff','#fff0a0'),('#76dfff','#fff0a0')]:s=s.replace(old,new)
s=s.replace("mechanicalColor={hydrant:'#ffd343',alarmValve:'#ffd343'}", "mechanicalColor={hydrant:'#ef4958',alarmValve:'#ef4958'}").replace("'#ffe475',.72", "'#ff8b95',.72").replace('적색 문짝','황색 문짝')
s=s.replace("entrance:'west',", "entrance:'all',")
old="if(segmentClear(start,ps[0],f))ps.unshift(start);if(segmentClear(ps.at(-1),end,f))ps.push(end);const reduced=[ps[0]];let a=0;while(a<ps.length-1){let b=ps.length-1;while(b>a+1&&!segmentClear(ps[a],ps[b],f))b--;reduced.push(ps[b]);a=b}"
new="if(!segmentClear(start,ps[0],f)||!segmentClear(ps.at(-1),end,f))return null;ps.unshift(start);ps.push(end);const reduced=[];for(const p of ps){if(reduced.length&&Math.hypot(p.x-reduced.at(-1).x,p.z-reduced.at(-1).z)<1e-8)continue;while(reduced.length>=2){const a=reduced.at(-2),b=reduced.at(-1),cross=(b.x-a.x)*(p.z-b.z)-(b.z-a.z)*(p.x-b.x),dot=(b.x-a.x)*(p.x-b.x)+(b.z-a.z)*(p.z-b.z);if(Math.abs(cross)>1e-8||dot<0)break;reduced.pop()}reduced.push(p)}"
assert old in s;s=s.replace(old,new)
a=s.index('const routeCache=');b=s.index('let currentRoutes=',a)
s=s[:a]+'''const routeCache=new Map();
function roomEntry(side,t,entrance=state.entrance){if(t.f===1)return entrance==='west'?{x:0,z:10.5,f:1}:{x:30.2,z:15,f:1};return side==='west'?{x:0,z:4.1,f:2}:{x:31.3,z:4.6,f:2}}
function routeDistance(points){return points.reduce((sum,p,i)=>i?sum+Math.hypot(p.x-points[i-1].x,p.y-points[i-1].y,p.z-points[i-1].z):0,0)}
function candidatesForEntrance(entrance){
const west=entrance==='west',start=west?{x:.7,z:10.5}:{x:30.2,z:14.5},t=state.target,result=[],entryName=west?'주출입구 후보':'보조출입구 후보';
const outside=(west?[{x:-7,z:21},{x:-7,z:10.5},{x:-.35,z:10.5}]:[{x:30.2,z:23},{x:30.2,z:15.35}]).map(p=>({...p,y:.15,f:1,external:true}));
const entry=west?{x:0,z:10.5,y:.15,f:1,threshold:true}:{x:30.2,z:15,y:.15,f:1,threshold:true};
if(t.f===1){if(state.fire){const p=pathfind(start,t,1);if(p)result.push({via:'같은 층',description:'외부 → 출입문 → 화점 후보',points:[...outside,entry,...p]})}else result.push({via:'같은 층',description:'외부 → 방 출입문',points:[...outside,entry]})}
else for(const side of ['west','east']){const sp=stairPoints(side),end=state.fire?t:roomEntry(side,t,entrance),a=pathfind(start,sp[0],1),b=pathfind(sp.at(-1),end,2);if(a&&b)result.push({via:side==='west'?'좌측 계단':'우측 계단',description:'외부 → 출입문 → '+(side==='west'?'좌측':'우측')+' 계단 → '+(state.fire?'화점 후보':'방 진입문'),points:[...outside,entry,...a,...sp.slice(1,-1),...b]})}
for(const r of result){r.length=routeDistance(r.points);r.entrance=entrance;r.entryName=entryName;}
result.sort((a,b)=>a.length-b.length);for(let i=0;i<result.length;i++){result[i].optimal=i===0;result[i].extraDistance=result[i].length-result[0].length;result[i].name=(i===0?'최단 · ':'대안 · ')+result[i].via;}
return result;}
function calcRoutes(){const key=JSON.stringify([state.entrance,state.target,state.fire]);if(routeCache.has(key))return routeCache.get(key);
let result;if(state.entrance==='all'){result=['west','east'].flatMap(id=>{const candidates=candidatesForEntrance(id);return candidates.length?[{...candidates[0],name:candidates[0].entryName}]:[]}).sort((a,b)=>a.length-b.length)}else result=candidatesForEntrance(state.entrance);
routeCache.set(key,result);return result;}
''' + s[b:]
s=s.replace("const color=i===0?'#ff4c61':'#ff9294'", "const color=i===0?'#ffda35':'#fff099'")
s=s.replace("state.fire?'#ff653c':'#ff5470'", "state.fire?'#ff653c':'#ffda35'")
s=s.replace("'#ffb3ab',.7", "state.fire?'#ffb3ab':'#fff099',.7")
s=s.replace("'<span class=\"distance\">약 '+Math.round(r.length)+'m</span><b>'+(i+1)+' · '+r.name+'</b><p>'+r.description+'</p>'", "'<span class=\"distance\">약 '+r.length.toFixed(1)+'m</span><b>'+r.name+'</b><div class=\"routevia\">'+(r.optimal?'최단 · ':'+')+(r.optimal?r.via:r.extraDistance.toFixed(1)+'m')+'</div>'")
s=s.replace("state.entrance=e.target.value;renderRoutes()", "state.entrance=e.target.value;state.chosen=0;renderRoutes()")
s=s.replace('function preset(){state.fire=false;', 'function preset(){state.chosen=0;state.fire=false;')
s=s.replace('state.fire=true;state.pick=false;', 'state.fire=true;state.chosen=0;state.pick=false;')
s=s.replace('도면상 진입 후보 · 현장 통행·연기·열 미반영. 승강기 제외. 거리도 근사값입니다.', '모델상 최단 · 현장 안전성 미평가')
p.write_text(s,encoding='utf-8')
p=Path('work/viewer.html');h=p.read_text(encoding='utf-8')
for old,new in [('#ca6570','#cdb34e'),('#f45b62','#ffd343'),('#31bfff','#ffe375'),('#ff4c61','#ffda35')]:h=h.replace(old,new)
h=h.replace('background:#ffd343"></i>소방시설', 'background:#ef4958"></i>소방시설')
h=h.replace('<select id="entrance">', '<select id="entrance"><option value="all">각 출입구 최단 경로 비교</option>')
h=h.replace('진입 후보 <span', '진입별 최단 <span').replace('적색 문짝','황색 문짝').replace('황색 계열로 표시합니다.','적색 계열로 표시합니다.')
h=h.replace('<li>경로는 도면을', '<li>최단 경로는 0.4m 격자의 8방향 A* 탐색으로 구합니다. 층간 연결은 등록된 계단만 사용하며, 외부 접근·층내 이동·계단의 3D 길이를 합산합니다. 출입구별 가능한 계단 경유 후보를 비교합니다. 최단 보장은 이 이산 모델의 허용된 연결에 한정되며 실제 공간의 연속 최단거리나 현장 안전성을 뜻하지 않습니다.</li><li>경로는 도면을')
h=h.replace('</style>', '.routecard.chosen{border-color:#e5c545;background:#373326}.routecard .distance{color:#ffeb8a}.routevia{font-size:12px;color:#b8bba3;margin-top:6px}</style>')
p.write_text(h,encoding='utf-8')
p=Path('work/folder_review.html');h=p.read_text(encoding='utf-8').replace("door:'#f33b62',window:'#0fa2ff'", "door:'#ffd343',window:'#ffe375'").replace("sh.type==='door'?'#f34b63':'#30b9ff'", "sh.type==='door'?'#ffd343':'#ffe375'").replace('붉은 프레임','황색 프레임');p.write_text(h,encoding='utf-8')
p=Path('outputs/소방공간뷰-사용안내.txt');h=p.read_text(encoding='utf-8').replace('- 적색: 문·열림 방향, 계단과 진입 경로','- 황색: 문·창·열림 방향, 계단과 진입 경로').replace('- 황색: 도면에 직접 확인된 소방기계(알람밸브)','- 적색: 도면에 직접 확인된 소방기계(알람밸브)');h+='\n최단 경로: 0.4m 이동 격자의 A* 탐색 결과와 계단 이동거리를 합산하여 출입구별 최단 후보를 비교합니다. 모델상 최단이며 현장 안전성은 평가하지 않습니다.\n';p.write_text(h,encoding='utf-8')
print('Updated palette and entrance-by-entrance shortest routes.')
