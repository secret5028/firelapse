// Dimension-only CAD bootstrap; all panels, playback and layers are production.
import * as T from '/vendor/three.module.js';
import {OrbitControls} from '/vendor/OrbitControls.js';
import {attach} from '/cfbt/overlay.js?v=hose-depth-1';
import {createIncidentLayer} from './incident-layer.js';
import {createExteriorLayer} from './exterior-layer.js';
import {createScaleReference} from './scale-reference.js';
const $=id=>document.getElementById(id);
try{
 const B=await (await fetch('./operating-building.json')).json(),S=new T.Scene(),C=new T.PerspectiveCamera(45,1,.01,1500),R=new T.WebGLRenderer({antialias:true});
 S.background=new T.Color('#102331');C.up.set(0,0,1);C.position.set(80,-45,60);R.setPixelRatio(Math.min(devicePixelRatio,2));$('v').append(R.domElement);
 const O=new OrbitControls(C,R.domElement);O.target.set(36,10,3);O.update();const groups=[],legacyRoot=new T.Group();S.add(legacyRoot);
 const shp=p=>{const shape=new T.Shape(p.o.map(q=>new T.Vector2(...q)));for(const ring of p.h||[]){const h=new T.Path(ring.map(q=>new T.Vector2(...q)));shape.holes.push(h);}return shape;};
 for(const f of B.floors){const g=new T.Group();g.name=f.name;S.add(g);groups.push(g);
  const box=(x,y,z,w,d,h)=>{const o=new T.Mesh(new T.BoxGeometry(w,d,h),new T.MeshBasicMaterial({color:'#93acb5',transparent:true,opacity:.18,depthWrite:false}));o.position.set(x,y,z);o.name=f.name+'_wall';g.add(o);
   const e=new T.LineSegments(new T.EdgesGeometry(o.geometry),new T.LineBasicMaterial({color:'#aab7c0',transparent:true,opacity:.42}));e.position.copy(o.position);e.name=f.name+'_edge';g.add(e);};
  for(const r of f.rooms){for(const p of r.polys){const slab=new T.Mesh(new T.ShapeGeometry(shp(p)),new T.MeshBasicMaterial({color:'#8a8a8a',side:T.DoubleSide,transparent:true,opacity:.15}));slab.position.z=.01;slab.name=f.name+'_slab_'+r.id;g.add(slab);
   for(let i=0;i<p.o.length;i++){const a=p.o[i],b=p.o[(i+1)%p.o.length],horizontal=a[1]===b[1],length=Math.hypot(b[0]-a[0],b[1]-a[1]);
    // The back-wall cavity occupies y=18..18.1, not an extra thick cube.
    const thickness=r.id==='CAVITY'?.012:.1;
    box((a[0]+b[0])/2,(a[1]+b[1])/2,f.h/2,horizontal?length:thickness,horizontal?thickness:length,f.h);
   }
  }}
 }
 const ref=new T.Group(),grid=new T.GridHelper(120,60,0x456071,0x263e4e);grid.rotation.x=Math.PI/2;grid.position.set(36,8,-.04);ref.add(grid);S.add(ref);
 const scaleReference=createScaleReference(T);ref.add(scaleReference);
 window.addEventListener('pagehide',()=>scaleReference.userData.dispose(),{once:true});
 let floor='1F';const setFloor=id=>{floor=id;for(const g of groups)g.visible=id==='all'||g.name===id;};$('all').onclick=()=>setFloor('all');$('floor1').onclick=()=>setFloor('1F');
 $('top').onclick=()=>{C.position.set(O.target.x,O.target.y,80);O.update();};$('iso').onclick=()=>{C.position.copy(O.target).add(new T.Vector3(25,-35,28));O.update();};$('resetView').onclick=()=>{O.target.set(36,10,3);C.position.set(85,-45,60);O.update();};
 $('zoomIn').onclick=()=>{C.position.sub(O.target).multiplyScalar(.8).add(O.target);O.update();};$('zoomOut').onclick=()=>{C.position.sub(O.target).multiplyScalar(1.25).add(O.target);O.update();};
 const viewer={THREE:T,B,S,C,O,R,groups,legacyRoot,shp,getFloor:()=>floor,setFloor};
 const app=await attach(viewer);
 // Include the scale references in the initial framing; room-only fitting can
 // put the person and most of the truck below the canvas in a narrow viewport.
 const scaleView=document.createElement('button');scaleView.id='wandoScaleView';scaleView.textContent='소방차·사람 보기';$('cameraButtons').append(scaleView);
 const showScale=()=>{
  app.store.dispatch('layers/toggle',{id:'route',visible:true});app.store.dispatch('route/set',{vehicle_visible:true});app.render();
  const box=new T.Box3(),room=B.floors[0].rooms.find(r=>r.id==='R5');
  for(const p of room.polys)for(const [x,y] of p.o)for(const z of [0,B.floors[0].h])box.expandByPoint(new T.Vector3(x,y,z));
  const route=S.getObjectByName('route');route?.updateWorldMatrix(true,true);
  route?.traverse(o=>{if(o.name.startsWith('scale-truck:')||o.name.startsWith('scale-person:'))box.union(new T.Box3().setFromObject(o));});
  const sphere=box.getBoundingSphere(new T.Sphere()),halfV=T.MathUtils.degToRad(C.fov/2),halfH=Math.atan(Math.tan(halfV)*C.aspect),distance=sphere.radius/Math.sin(Math.min(halfV,halfH))*1.12;
  O.target.copy(sphere.center);C.position.copy(sphere.center).addScaledVector(new T.Vector3(25,-35,28).normalize(),distance);O.update();app.render();
 };
 scaleView.onclick=showScale;showScale();
 const tactical=await(await fetch('./tactical.json')).json();
 const incident=createIncidentLayer(T,S,B,tactical,$('shellPane-display'));
 const exterior=createExteriorLayer(T,S,await(await fetch('./exterior.json')).json(),$('shellPane-display'));
 const offFloor=app.store.subscribe('floor',()=>incident.setFloor(app.store.get('floor').floor_id));
 window.addEventListener('pagehide',()=>{offFloor();incident.dispose();exterior.dispose();},{once:true});
 // A visible, time-linked label distinguishes the cut from static door frames.
 const cut=document.createElement('output');cut.className='wandoOpening';$('v').append(cut);
 const endpoint=document.createElement('div');endpoint.id='nativeOutputNotice';endpoint.textContent='순정 CFAST · 마지막 5 s 미출력 · 종료 59:55';endpoint.style.cssText='padding:8px;color:#ffd18a;font-size:12px';$('resultCase').prepend(endpoint);
 for(const id of ['exploreRun','exploreOriginRun','exploreMC','resultMCApplyWorst','exportHTML']){const el=$(id);if(el){el.disabled=true;el.title='P1 저장 결과 보기 전용';}}
 for(const el of document.querySelectorAll('#buildingDoors button')){el.disabled=true;el.title='P1 입력 고정';}
 function loop(){requestAnimationFrame(loop);O.update();R.render(S,C);
  const t=app.store.get('playback').t_s,f=t>=1800?1:t>=1320?.5:0,point=new T.Vector3(46.75,18,2.7).project(C),v=$('v');
  cut.textContent=`CUT · ${f===0?'닫힘':f===.5?'열림 1 × 2 m':'열림 2 × 2 m'}`;cut.style.left=(point.x+1)*v.clientWidth/2+'px';cut.style.top=(1-point.y)*v.clientHeight/2+'px';cut.hidden=point.z>1||(app.store.get('floor').floor_id!==null&&app.store.get('selection').room_id!=='CAD_1F_CAVITY');
 }loop();window.addEventListener('pagehide',()=>O.dispose());
}catch(e){$('error').textContent=e.stack;throw e;}
