from pathlib import Path
p=Path('work/cad_viewer.js');s=p.read_text(encoding='utf-8-sig');src=Path('work/industrial.js').read_text(encoding='utf-8')
helpers='''
const THREE=T,V=(x=0,y=0,z=0)=>new T.Vector3(x,y,z);
const mat=(c,o=1)=>new T.MeshStandardMaterial({color:c,transparent:o<1,opacity:o,side:T.DoubleSide,depthWrite:o>=1});
function box(g,x,y,z,w,h,d,m){const mesh=new T.Mesh(new T.BoxGeometry(w,h,d),m);mesh.position.set(x+w/2,y+h/2,z+d/2);g.add(mesh);return mesh}
const scaleReference=new T.Group();scene.add(scaleReference);
'''+src[src.index('const truck=new'):src.index('const scaleLabel=')]+'''
truck.position.set(24,0,30);person.position.set(23,0,29);
label('소방차 8m · 사람 1.75m',28,.2,34,scaleReference);
const ground=box(scene,-12,-.2,-8,58,.18,52,mat(0x243e50));
let startPick=false;const startPoint=V(23,.03,28),startRing=new T.Mesh(new T.RingGeometry(.35,.52,32),new T.MeshBasicMaterial({color:0x319cff,side:T.DoubleSide}));startRing.rotation.x=-Math.PI/2;startRing.position.copy(startPoint);scene.add(startRing);
function moveStart(x,z){const delta=V(x-startPoint.x,0,z-startPoint.z);scaleReference.position.add(delta);startPoint.set(x,.03,z);startRing.position.copy(startPoint)}
$('start').onclick=()=>{startPick=!startPick;pick=false;$('start').classList.toggle('active',startPick);$('fire').classList.remove('active')};$('startClear').onclick=()=>{moveStart(23,28);startPick=false;$('start').classList.remove('active')};
const stairMat=mat(0xffd15a),railMat=mat(0xd8bd72);
function beam(g,a,b,r=.025){const d=b.clone().sub(a),m=new T.Mesh(new T.CylinderGeometry(r,r,d.length(),8),railMat);m.position.copy(a).add(b).multiplyScalar(.5);m.quaternion.setFromUnitVectors(V(0,1,0),d.normalize());g.add(m)}
const stairAudit=[];
function flight(g,x,z,run,width,y0,y1,axis,dir,count=20){const step=run/count,dh=(y1-y0)/count;for(let j=0;j<count;j++){const u=(dir>0?j:count-1-j)*step,yy=y0+(j+1)*dh;box(g,x+(axis==='x'?u:0),yy-.09,z+(axis==='z'?u:0),axis==='x'?step+.015:width,.09,axis==='z'?step+.015:width,stairMat);box(g,x+(axis==='x'?(dir>0?u:u+step-.045):0),yy-dh,z+(axis==='z'?(dir>0?u:u+step-.045):0),axis==='x'?.045:width,dh,axis==='z'?.045:width,stairMat)}
for(const side of [0,width]){const start=V(x+(axis==='x'?(dir>0?0:run):side),y0+1,z+(axis==='z'?(dir>0?0:run):side)),end=V(x+(axis==='x'?(dir>0?run:0):side),y1+1,z+(axis==='z'?(dir>0?run:0):side));beam(g,start,end);for(let j=0;j<=4;j++){const q=start.clone().lerp(end,j/4);beam(g,q.clone().add(V(0,-1,0)),q,.02)}}stairAudit.push({y0,y1,count})}
function stairPair(x,z,run,width,axis){const g=layerGroups[0].stairs;flight(g,x,z,run,width,1,4.25,axis,1);flight(g,x+(axis==='z'?width+.12:0),z+(axis==='x'?width+.12:0),run,width,4.25,7.5,axis,-1);box(g,x+(axis==='x'?run:0),4.13,z+(axis==='z'?run:0),axis==='x'?1:width*2+.12,.12,axis==='z'?1:width*2+.12,stairMat)}
// Footprints reconciled across 1F/2F; tread counts/heights use the 6.5 m storey rise.
stairPair(4.1,16.35,4.7,1.2,'x');stairPair(3.15,9,5,1.05,'z');stairPair(31.25,9.6,4.8,1.05,'z');stairPair(16.6,-2.3,5.4,1.05,'x');
// Entrance steps from grade to the +1.0 m first floor.
flight(layerGroups[0].stairs,25.6,23.6,1.8,5.2,0,1,'z',-1,6);
'''
# Add components after floor groups have been built.
idx=s.index('function visibility()');s=s[:idx]+helpers+s[idx:]
s=s.replace("poly(pts,mats[l.type],ls[l.type]);", "if(l.type!=='stairs')poly(pts,mats[l.type],ls[l.type]);")
s=s.replace("if(['doors','windows'].includes(l.type)){", "if(['doors','windows'].includes(l.type)&&l.p.length<=5){")
s=s.replace("shape.closePath();const mesh", "shape.closePath();if(i===1){const hole=new T.Path();hole.moveTo(4.0,-16.2);hole.lineTo(4.0,-19);hole.lineTo(9.9,-19);hole.lineTo(9.9,-16.2);hole.closePath();shape.holes.push(hole)}const mesh")
s=s.replace("opacity:.32", "opacity:.65")
s=s.replace("if(pick){if(ray", "if(startPick){if(ray.ray.intersectPlane(new T.Plane(V(0,1,0),0),p)&&(p.x<0||p.x>34||p.z>25||p.z< -4)){moveStart(p.x,p.z);startPick=false;$('start').classList.remove('active')}}else if(pick){if(ray")
s=s.replace("$('fire').onclick=()=>{", "$('fire').onclick=()=>{startPick=false;$('start').classList.remove('active');")
# Keep outgoing stairs visible when viewing their destination floor as well.
s=s.replace("groups.forEach((g,i)=>g.visible=floor==='all'||floor===String(i));", "groups.forEach((g,i)=>g.visible=floor==='all'||floor===String(i));scene.attach(layerGroups[0].stairs);layerGroups[0].stairs.visible=(floor==='all'||floor==='0'||floor==='1');")
s=s.replace("layerGroups.forEach(l=>l[input.dataset.layer].visible=input.checked)", "layerGroups.forEach((l,i)=>l[input.dataset.layer].visible=input.checked&&(input.dataset.layer!=='stairs'||i!==0||floor!=='2'))")
s += '\nwindow.cadViewer={scene,camera,groups,layerGroups,truck,person,stairAudit,renderer};\n'
p.write_text(s,encoding='utf-8')
q=Path('work/package_cad.py');t=q.read_text(encoding='utf-8-sig').replace("('stairs','계단 평면선')","('stairs','계단')").replace('<button id="fire">','<button id="start">출발점 지정</button><button id="startClear">해제</button><br><button id="fire">');t=t.replace('계단은 원본 평면선을 표시합니다.','계단은 1·2층의 위치를 대조해 얇은 디딤판·챌판·계단참·난간으로 구성했습니다. 단수와 일부 폭은 근사값입니다.').replace('바닥 외곽은 공통 외곽선에 따른 근사이며 계단 구멍·보이드 확인이 필요합니다.','바닥 외곽은 공통 외곽선에 따른 근사이며 내부 계단 위치는 2층 바닥에서 제외했습니다. 상세 개구부 치수는 검토가 필요합니다.').replace('CAD 원본 좌표 · 건축 검토용','소방공간뷰 · CAD 모델').replace('소방설비 자료 미제공','소방설비 자료 미제공 · 외부 출발점 변경 가능')
q.write_text(t,encoding='utf-8')
