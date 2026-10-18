from pathlib import Path
p=Path(__file__).parent/'industrial.js';s=p.read_text(encoding='utf-8')
s=s.replace('const yellow=mat', 'const spColor=0xde62e8,spMaterial=mat(spColor);\nconst yellow=mat')
s=s.replace('...size,red,e.name',"...size,e.system?.startsWith('SP')?spMaterial:red,e.name")
a=s.index('for(const f of D.floors){const y=f.y+1.3;');b=s.index('const wallBoxes=',a)
s=s[:a]+'''// Ceiling elevations are provisional, consistent with the model floor heights.
for(const f of D.floors){const y=f.n===1?5.7:f.n===2?9.3:12.1;for(const e of D.mechanical.filter(e=>e.type==='hydrant'&&e.f===f.n)){const x=f.n===2&&e.x<10.2?5:92;let pts=[V(x,y,1),V(e.x,y,1),V(e.x,y,e.z),V(e.x,f.y+1.2,e.z)];if(f.n===1&&e.x<88.9)pts=[V(92,5.7,1),V(88.9,5.7,1),V(88.9,9.3,1),V(Math.max(10.2,e.x),9.3,1),V(e.x,9.3,e.z),V(e.x,f.y+1.2,e.z)];stroke(layers[f.n].pipes,pts,0xec3549,.09)}}
stroke(layers[1].pipes,[V(92,.4,-1.2),V(92,.4,1),V(92,5.7,1)],0xec3549,.09);
for(const x of [5,92])stroke(layers[2].pipes,[V(x,6,1),V(x,9.3,1)],0xec3549,.09);
for(const x0 of [1.3,90.8])for(let z=9;z<31;z+=2.6){stroke(layers[1].sprinklers,[V(x0,5.7,z),V(x0+6,5.7,z)],spColor,.055);for(let x=x0;x<x0+6.1;x+=2.7){const h=new THREE.Mesh(new THREE.SphereGeometry(.1,6,6),spMaterial);h.position.set(x,5.65,z);layers[1].sprinklers.add(h)}}
'''+s[b:]
s=s.replace('mat(0xff4455,.17)','mat(spColor,.17)')
s=s.replace("state.fire=null;state.pick=false;fillRooms();", "state.fire=null;state.pick=false;canvas.style.cursor='';$('fireBtn').classList.remove('active');$('fireBtn').disabled=f==='all';$('fireBtn').title=f==='all'?'먼저 층을 선택하세요':'화점 지정 후 화면을 클릭하세요';fillRooms();")
s=s.replace("if(state.floor==='all'||state.compare)setFloor(String(state.routeFloor));state.pick=!state.pick;", "if(state.floor==='all'||state.compare){$('routeHint').textContent='먼저 층을 선택하세요.';return}state.pick=!state.pick;canvas.style.cursor=state.pick?'crosshair':'';$('routeHint').textContent=state.pick?'화점 위치를 화면에서 클릭하세요.':'구획실 선택 또는 화점 지정을 사용하세요.';")
s=s.replace("state.pick=false;$('fireBtn').classList.remove('active');updateRoutes();return", "state.pick=false;canvas.style.cursor='';$('fireBtn').classList.remove('active');updateRoutes();return")
s=s.replace("state.pick=false;state.fire=null;$('fireBtn')", "state.pick=false;state.fire=null;canvas.style.cursor='';$('fireBtn')")
p.write_text(s,encoding='utf-8')
p=Path(__file__).parent/'package_industrial.py';s=p.read_text(encoding='utf-8').replace('붉은색: 소방기계·배관','적색: 소화전·공통 급수<br>자홍색: 스프링클러<br>배관: 천장 기준 · 높이 임시값')
s=s.replace('>소화배관 계통</label>','>소화전 배관 · 적색</label>').replace('>확인된 SP 배관</label>','>SP 배관 · 자홍색</label>')
p.write_text(s,encoding='utf-8')
