// CAD scene bootstrap. All operational panels/layers are the existing shared app.
import * as T from 'three';
import {OrbitControls} from '/vendor/OrbitControls.js';
import {attach} from '/app/web/entry.js';
import {createGroundReference} from '/app/web/scene/ground_reference.js';
const $=id=>document.getElementById(id);
try{
 const [B,info,initial]=await Promise.all(['/building.json','/cfbt/model-info','/cfbt/lite/active.json'].map(async url=>{const r=await fetch(url),v=await r.json();if(!r.ok)throw Error(v.error);return v;}));
 document.body.dataset.operationUrl=info.operation_url;document.body.dataset.buildingLabel=info.label;document.title='FireLapse · '+info.label;
 const S=new T.Scene(),C=new T.PerspectiveCamera(45,1,.1,5000),R=new T.WebGLRenderer({antialias:true});
 S.background=new T.Color('#102331');C.up.set(0,0,1);R.setPixelRatio(Math.min(devicePixelRatio,2));$('v').prepend(R.domElement);
 const O=new OrbitControls(C,R.domElement),groups=[],legacyRoot=new T.Group();S.add(legacyRoot);
 S.add(new T.HemisphereLight(0xe4f4ff,0x50616c,2));const sun=new T.DirectionalLight(0xffffff,1.8);sun.position.set(30,-50,100);S.add(sun);
 const owned=[];const keep=x=>(owned.push(x),x);
 const shp=part=>{const p=part.o||part,s=new T.Shape(p.map(q=>new T.Vector2(q[0],q[1])));for(const h of part.h||[])s.holes.push(new T.Path(h.map(q=>new T.Vector2(q[0],q[1]))));return s;};
 function mesh(g,parts,z,h,color,opacity,kind='wall'){if(!parts?.length||h<=0)return;const o=new T.Mesh(keep(new T.ExtrudeGeometry(parts.map(shp),{depth:h,bevelEnabled:false})),keep(new T.MeshLambertMaterial({color,transparent:true,opacity,depthWrite:false,side:T.DoubleSide})));o.position.z=z;o.name=g.name+'_'+kind;g.add(o);}
 for(const f of B.floors){const g=new T.Group();g.name=f.name;g.position.z=f.z||0;groups.push(g);S.add(g);
  mesh(g,f.slab,-.15,.15,0x8a8a8a,.24,'slab');
  if(f.bands?.length)for(const b of f.bands)if(['wall','door_head','win_low','win_head'].includes(b.kind))mesh(g,b.polys,b.z0,b.z1-b.z0,0x93acb5,.25);
  for(const r of f.rooms||[])for(const part of r.polys||[]){const p=part.o||part;
   const line=new T.Line(keep(new T.BufferGeometry().setFromPoints([...p,p[0]].map(q=>new T.Vector3(...q,.04)))),keep(new T.LineBasicMaterial({color:0xaab7c0,transparent:true,opacity:.42})));line.name=f.name+'_outline';g.add(line);
   if(!f.bands?.length)for(let i=0;i<p.length;i++){const a=p[i],b=p[(i+1)%p.length],len=Math.hypot(b[0]-a[0],b[1]-a[1]);if(!len)continue;const n=[-(b[1]-a[1])/len*.04,(b[0]-a[0])/len*.04];mesh(g,[[[a[0]+n[0],a[1]+n[1]],[b[0]+n[0],b[1]+n[1]],[b[0]-n[0],b[1]-n[1]],[a[0]-n[0],a[1]-n[1]]]],0,f.h,0x93acb5,.25);}
  }
  for(const col of f.structural_columns||[])mesh(g,col.polys,0,col.height_m||f.h,0x93acb5,.7);
 }
 let floor=initial.rooms.find(r=>r.key===initial.fire_key)?.cad_floor||B.floors[0].name;
 const groundGrid=createGroundReference(T,B);if(groundGrid){S.add(groundGrid);keep(groundGrid.geometry);for(const m of Array.isArray(groundGrid.material)?groundGrid.material:[groundGrid.material])keep(m);}
 const setFloor=id=>{floor=id;for(const g of groups)g.visible=id==='all'||g.name===id;if(groundGrid)groundGrid.visible=id==='all'||id===groundGrid.userData.groundReference.floor;};setFloor(floor);
 for(const name of ['all',...B.floors.map(f=>f.name)]){const b=document.createElement('button');b.textContent=name==='all'?'전체':name;b.onclick=()=>setFloor(name);$('fbtn').append(b);}
 function fit(top=false){const bounds=new T.Box3();for(const f of B.floors)if(floor==='all'||floor===f.name)for(const part of f.slab||[])for(const xy of part.o||part)for(const z of [f.z||0,(f.z||0)+f.h])bounds.expandByPoint(new T.Vector3(...xy,z));if(bounds.isEmpty())return;
  const center=bounds.getCenter(new T.Vector3()),radius=bounds.getSize(new T.Vector3()).length()/2,vertical=C.fov*Math.PI/180,horizontal=2*Math.atan(Math.tan(vertical/2)*C.aspect),distance=radius/Math.sin(Math.min(vertical,horizontal)/2)*1.1;O.target.copy(center);C.position.copy(center).addScaledVector(top?new T.Vector3(0,-.001,1).normalize():new T.Vector3(1,-1,1.1).normalize(),distance);O.update();}
 C.aspect=Math.max(1,$('v').clientWidth)/Math.max(1,$('v').clientHeight);C.updateProjectionMatrix();fit();
 $('top').onclick=()=>fit(true);$('iso').onclick=()=>fit();$('resetView').onclick=()=>fit();$('zoomIn').onclick=()=>{C.position.sub(O.target).multiplyScalar(.8).add(O.target);O.update();};$('zoomOut').onclick=()=>{C.position.sub(O.target).multiplyScalar(1.25).add(O.target);O.update();};
 const viewer={THREE:T,B,S,C,O,R,groups,legacyRoot,shp,getFloor:()=>floor,setFloor,getScreeningFloor:()=>floor==='all'?null:floor,capabilities:{frozenRules:false,assistant:true,exportPost:true}};
 const app=await attach(viewer);
 let frame;function loop(){frame=requestAnimationFrame(loop);O.update();R.render(S,C);}loop();
 window.addEventListener('pagehide',()=>{cancelAnimationFrame(frame);app.dispose();O.dispose();for(const r of owned)r.dispose();R.dispose();},{once:true});
 document.body.dataset.operationReady='true';
}catch(e){$('error').textContent=e.stack;throw e;}
