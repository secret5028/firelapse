import * as T from 'three';
import {OrbitControls} from '/vendor/OrbitControls.js';
import {createModelReview} from '/app/web/panels/model_review.js';
const $=id=>document.getElementById(id),stage=$('stage');
const scene=new T.Scene();scene.background=new T.Color('#142936');
const camera=new T.PerspectiveCamera(42,1,.1,3000);camera.up.set(0,0,1);
const renderer=new T.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));stage.prepend(renderer.domElement);
const controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=false;
scene.add(new T.HemisphereLight(0xe4f4ff,0x50616c,2));const sun=new T.DirectionalLight(0xffffff,1.8);sun.position.set(30,-50,100);scene.add(sun);
let root=null,panel=null,selected=null,picks=[],wallMeshes=[],openingGroups=[],floors=[],generation=0,model=null,resources=[];
const keep=x=>(resources.push(x),x);
function draw(){renderer.render(scene,camera)}controls.addEventListener('change',draw);
function resize(){const r=stage.getBoundingClientRect();renderer.setSize(r.width,r.height);camera.aspect=r.width/r.height;camera.updateProjectionMatrix();draw()}new ResizeObserver(resize).observe(stage);
function shape(part){const p=part.o||part,s=new T.Shape(p.map(q=>new T.Vector2(q[0],q[1])));for(const h of part.h||[])s.holes.push(new T.Path(h.map(q=>new T.Vector2(q[0],q[1]))));return s}
function line(group,points,color,opacity=1){const g=keep(new T.BufferGeometry().setFromPoints(points.map(p=>new T.Vector3(...p)))),m=keep(new T.LineBasicMaterial({color,transparent:true,opacity})),o=new T.Line(g,m);group.add(o);return o}
function extrude(group,parts,z,h,color,opacity=.2,wall=true){if(!parts?.length||h<=0)return;const g=keep(new T.ExtrudeGeometry(parts.map(shape),{depth:h,bevelEnabled:false})),m=keep(new T.MeshLambertMaterial({color,transparent:true,opacity,depthWrite:false,side:T.DoubleSide})),o=new T.Mesh(g,m);o.position.z=z;group.add(o);if(wall)wallMeshes.push(o);return o}
function opening(group,a,b,z,h,color){const g=new T.Group();group.add(g);line(g,[[...a,z],[...b,z],[...b,z+h],[...a,z+h],[...a,z]],color,.9);openingGroups.push(g)}
function scanFloor(f,group,offset){const p=f.scan_page,outline=p.floorOutline||[],origin=p.origin||[Math.min(...outline.map(x=>x[0])),Math.min(...outline.map(x=>x[1]))],scale=p.scale,shift=p.modelShift||[0,0];
 const xy=q=>[(q[0]-origin[0]+shift[0])*scale+offset,-(q[1]-origin[1]+shift[1])*scale];
 const poly=outline.map(xy);if(poly.length>2)extrude(group,[poly],-.12,.12,0x78909d,.25,false);
 for(const s of p.shapes||[]){if(!s.a||!s.b)continue;const a=xy(s.a),b=xy(s.b),dx=b[0]-a[0],dy=b[1]-a[1],len=Math.hypot(dx,dy);if(len<.001)continue;
  if(s.type==='wall'){const n=[-dy/len*.06,dx/len*.06];extrude(group,[[[a[0]+n[0],a[1]+n[1]],[b[0]+n[0],b[1]+n[1]],[b[0]-n[0],b[1]-n[1]],[a[0]-n[0],a[1]-n[1]]]],0,p.wallHeight||p.height,0xb5c3cb,.27)}
  else if(s.type==='door'||s.type==='window'){// Old scan has no measured opening heights: mark the traced plane only.
   const g=new T.Group();group.add(g);line(g,[[...a,.08],[...b,.08]],s.type==='door'?0xecc46b:0x75d8c5);openingGroups.push(g);
  }
 }
}
function cadFloor(f,group){
 extrude(group,f.slab,-.15,.15,0x8198a5,.24,false);
 if(f.bands?.length)for(const b of f.bands){if(['wall','door_head','win_low','win_head'].includes(b.kind))extrude(group,b.polys,b.z0,b.z1-b.z0,0xb8c3cb,.25)}
 for(const r of f.rooms||[]){for(const part of r.polys||[]){const p=part.o||part;line(group,[...p,p[0]].map(x=>[...x,.04]),0x8da9b9,.5);
  if(!f.bands?.length){for(let i=0;i<p.length;i++){const a=p[i],b=p[(i+1)%p.length],len=Math.hypot(b[0]-a[0],b[1]-a[1]);if(!len)continue;const n=[-(b[1]-a[1])/len*.04,(b[0]-a[0])/len*.04];extrude(group,[[[a[0]+n[0],a[1]+n[1]],[b[0]+n[0],b[1]+n[1]],[b[0]-n[0],b[1]-n[1]],[a[0]-n[0],a[1]-n[1]]]],0,f.h,0xb8c3cb,.2)}}
  const mesh=new T.Mesh(keep(new T.ShapeGeometry(shape(part))),keep(new T.MeshBasicMaterial({transparent:true,opacity:0,depthWrite:false,side:T.DoubleSide})));mesh.position.z=.07;mesh.userData.room={floor:f.name,id:r.id,room:r};group.add(mesh);picks.push(mesh);
 }}
 for(const c of f.structural_columns||[])extrude(group,c.polys,0,c.height_m||f.h,0x9bacb5,.7,false);
 for(const o of f.openings||[]){if(o.superseded_by)continue;const leaf=o.leaves?.[0];let a=leaf?.hinge,b=leaf?.closed;
  if(!a||!b){const pts=(o.autocorrect_aperture_polys||o.geometry_polys||o.polys||[]).flatMap(x=>x.o||x);if(!pts.length)continue;const xs=pts.map(x=>x[0]),ys=pts.map(x=>x[1]),x0=Math.min(...xs),x1=Math.max(...xs),y0=Math.min(...ys),y1=Math.max(...ys);[a,b]=x1-x0>=y1-y0?[[x0,(y0+y1)/2],[x1,(y0+y1)/2]]:[[(x0+x1)/2,y0],[(x0+x1)/2,y1]];}
  const win=String(o.kind).includes('win');opening(group,a,b,win?(o.sill??f.sill??.9):0,win?Math.max(.1,(o.head??f.head??2.1)-(o.sill??f.sill??.9)):(o.door_h||f.door_h||2.1),win?0x75d8c5:0xecc46b);
 }
}
function bounds(){const b=new T.Box3();for(const f of floors)if(f.visible)b.expandByObject(f);return b}
function fit(top=false){const b=bounds();if(b.isEmpty())return;const c=b.getCenter(new T.Vector3()),s=b.getSize(new T.Vector3()),d=Math.max(s.x,s.y,s.z,5)*1.65;controls.target.copy(c);camera.position.copy(c).add(top?new T.Vector3(0,-.001,d):new T.Vector3(d*.65,-d*.9,d*.75));camera.near=.1;camera.far=Math.max(3000,d*10);camera.updateProjectionMatrix();controls.update();draw()}
function showFloor(value){for(const f of floors)f.visible=value==='all'||f.name===value;draw()}
function clear(){panel?.dispose();panel=null;if(root)scene.remove(root);for(const r of resources)r.dispose();resources=[];picks=[];wallMeshes=[];openingGroups=[];floors=[];selected=null}
function selectRoom(hit){if(selected){selected.parent.remove(selected);selected.geometry.dispose();selected.material.dispose();selected=null}if(!hit)return;const r=hit.room,group=floors.find(f=>f.name===hit.floor);if(!group)return;const pts=(r.polys||[]).flatMap(p=>{const q=p.o||p;return q.flatMap((a,i)=>[[...a,.1],[...q[(i+1)%q.length],.1]])});selected=new T.LineSegments(new T.BufferGeometry().setFromPoints(pts.map(p=>new T.Vector3(...p))),new T.LineBasicMaterial({color:0x42e8ff,depthTest:false,transparent:true,opacity:1}));group.add(selected);$('selection').textContent=`${hit.floor} ${hit.id} · ${(r.names||[]).join(' / ')||'용도 미확인'}`;draw()}
async function load(e){const ticket=++generation;$('loading').textContent='모델 불러오는 중…';$('error').textContent='';$('model').value=e.id;
 try{const response=await fetch(e.model_url);if(!response.ok)throw Error('모델 파일을 읽을 수 없습니다');const b=await response.json();if(ticket!==generation)return;clear();model=b;root=new T.Group();scene.add(root);
  const buildings=[...new Set(b.floors.map(f=>f.scan_page?.building).filter(Boolean))];
  for(const f of b.floors){const g=new T.Group();g.name=f.name;g.position.z=f.scan_page?.elevation??f.z??0;root.add(g);floors.push(g);if(f.scan_page)scanFloor(f,g,buildings.indexOf(f.scan_page.building)*100);else cadFloor(f,g)}
  $('name').textContent=e.label;$('source').textContent={cad:'CAD 원본',scan:'스캔 기반 · 열람 전용',reconstructed:'자료 기반 재구성'}[e.source_kind];$('source').className='badge'+(e.source_kind==='scan'?' scan':'');
  $('counts').textContent=`${e.floor_count}개 층/도면${e.room_count===null?' · 실 분할 미확정':' · '+e.room_count+'개 공간'}`;
  $('reason').textContent=e.execution_note;$('run').disabled=!e.simulation_enabled;$('run').title=e.execution_note;$('run').textContent=e.simulation_enabled?'운영 화면 · 시뮬레이션':'시뮬레이션 불가';$('run').onclick=e.simulation_enabled?()=>location.assign(e.operation_url):null;
  $('note').textContent=e.source_evidence+(b.notes?.length?'\n'+b.notes.join('\n'):'')+(e.id==='modori-scan'?'\n전체 보기의 동 간 간격은 열람용 분리 배치이며 실제 대지 배치가 아닙니다.':'');
  $('links').replaceChildren();if(/^cad-[a-f0-9]{32}$/.test(e.id)){const a=document.createElement('a');a.className='button';a.href='/models/new?review='+e.id.slice(4);a.textContent='공리·AI 모델 검토';$('links').append(a);}for(const [text,url] of [['기존 운영 화면 · 저장 결과',e.operation_url],['도면 보정·미완 위치 상세',e.review_url]])if(url){const a=document.createElement('a');a.className='button';a.href=url;a.textContent=text;$('links').append(a)}
  $('floor').replaceChildren(new Option('전체 건물','all'));for(const f of b.floors)$('floor').add(new Option(f.name,f.name));$('floor').value='all';
  panel=createModelReview({container:$('review'),building:b,onLocate:x=>{const f=b.floors.find(f=>f.name===x.floor);if(!f)return;$('floor').value=f.name;showFloor(f.name);const r=f.rooms?.find(r=>r.id===x.id);if(r)selectRoom({floor:f.name,id:r.id,room:r});else $('selection').textContent=`${x.floor} ${x.id} · ${x.detail}`;fit()}});
  $('selection').textContent=e.source_kind==='scan'?'스캔 형상 열람 · 문·창은 바닥 추적선, 높이 미확정':'실을 클릭하면 선택됩니다';
  wallMeshes.forEach(m=>m.material.opacity=$('walls').checked?.25:.85);openingGroups.forEach(g=>g.visible=$('openings').checked);fit();history.replaceState(null,'','?id='+e.id);window.__modelLibrary={ready:true,id:e.id,floors:b.floors.length,scan:e.source_kind==='scan',meshes:root.children.length};
 }catch(error){$('error').textContent=error.message;window.__modelLibrary={ready:false,error:error.message}}finally{if(ticket===generation)$('loading').textContent=''}
}
$('floor').onchange=()=>showFloor($('floor').value);$('iso').onclick=()=>fit();$('top').onclick=()=>fit(true);$('fit').onclick=()=>fit();
$('walls').onchange=()=>{wallMeshes.forEach(m=>m.material.opacity=$('walls').checked?.25:.85);draw()};$('openings').onchange=()=>{openingGroups.forEach(g=>g.visible=$('openings').checked);draw()};
let down=null;renderer.domElement.addEventListener('pointerdown',e=>down={x:e.clientX,y:e.clientY});renderer.domElement.addEventListener('pointerup',e=>{if(!down||Math.hypot(e.clientX-down.x,e.clientY-down.y)>5)return;const r=renderer.domElement.getBoundingClientRect(),ray=new T.Raycaster();ray.setFromCamera(new T.Vector2((e.clientX-r.left)/r.width*2-1,-(e.clientY-r.top)/r.height*2+1),camera);const hit=ray.intersectObjects(picks.filter(p=>p.parent.visible),false)[0];if(hit)selectRoom(hit.object.userData.room)});
try{const c=await(await fetch('/models/catalog.json')).json();for(const e of c.models)$('model').add(new Option(e.label+(e.source_kind==='scan'?' [열람 전용]':''),e.id));$('model').onchange=()=>load(c.models.find(e=>e.id===$('model').value));await load(c.models.find(e=>e.id===new URLSearchParams(location.search).get('id'))||c.models.find(e=>e.id==='parkmarine'));}catch(e){$('error').textContent=e.message}
