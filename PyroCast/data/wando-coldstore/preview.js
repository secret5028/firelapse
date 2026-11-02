// Dimension-only preview through the existing scene host and BuildingLayer.
// No playback, fabricated fire results, simulation calls, or operational case switch.
import * as T from '/vendor/three.module.js';
import {createSceneHost} from '/app/web/scene/host.js';
import {createStore} from '/app/web/state/store.js';
import {BuildingLayer} from '/app/web/layers/building.js';

const $=id=>document.getElementById(id);
try {
 const [B,F]=await Promise.all(['building.json','fuel-inputs.json'].map(x=>fetch(x).then(r=>{if(!r.ok)throw Error(x);return r.json();})));
 const f=B.floors[0],source=new T.Group();source.name=f.floor_id;
 const objects=[],styles=[],slabs=[],labels=[],resources=new Set();
 const add=(o,color,opacity=null)=>{source.add(o);objects.push(o);styles.push({color,opacity});resources.add(o.geometry);resources.add(o.material);return o;};
 const line=(points,color,opacity=1)=>new T.Line(new T.BufferGeometry().setFromPoints(points.map(p=>new T.Vector3(...p))),new T.LineBasicMaterial({color,transparent:true,opacity,depthTest:false}));
 const solid=(x,y,z,w,d,h,color,opacity=.3)=>{const o=new T.Mesh(new T.BoxGeometry(w,d,h),new T.MeshBasicMaterial({color,transparent:true,opacity,depthWrite:false}));o.position.set(x,y,z);return add(o,color);};
 const slab=(room,z,color,opacity)=>{const shape=new T.Shape(room.polygon_m.map(p=>new T.Vector2(...p)));const o=new T.Mesh(new T.ShapeGeometry(shape),new T.MeshBasicMaterial({color,side:T.DoubleSide,transparent:true,opacity,depthWrite:false}));o.position.z=z;return add(o,color);};
 for(const r of f.rooms){
  const p=r.polygon_m,h=r.ceiling_z_m,fire=r.room_id==='R5',color=fire?'#dbbd70':'#aec3cc';
  slab(r,.015,fire?'#745b29':'#344d5e',.8);const roof=slab(r,h,'#c0ccd2',.18);roof.visible=false;slabs.push(roof);
  for(let i=0;i<p.length;i++){
   const a=p[i],b=p[(i+1)%p.length],horizontal=a[1]===b[1],lo=Math.min(horizontal?a[0]:a[1],horizontal?b[0]:b[1]),hi=Math.max(horizontal?a[0]:a[1],horizontal?b[0]:b[1]),fixed=horizontal?a[1]:a[0];
   const door=f.openings.find(v=>v.a===r.room_id&&Math.abs(v.center_m[horizontal?1:0]-fixed)<1e-6&&v.center_m[horizontal?0:1]>lo&&v.center_m[horizontal?0:1]<hi);
   const piece=(l,u,bottom,top)=>{if(u<=l)return;solid(horizontal?(l+u)/2:fixed,horizontal?fixed:(l+u)/2,(bottom+top)/2,horizontal?u-l:.4,horizontal?.4:u-l,top-bottom,color,.28);};
   if(door){const c=door.center_m[horizontal?0:1],half=door.width_m/2;piece(lo,c-half,0,h);piece(c+half,hi,0,h);piece(c-half,c+half,door.soffit_m,h);}else piece(lo,hi,0,h);
   add(line([[...a,0],[...a,h],[...b,h]],color,.65),color);
  }
  add(line([...p,p[0]].map(q=>[...q,.06]),fire?'#ffd16d':'#829cac',.9),fire?'#ffd16d':'#829cac');
  const xs=p.map(q=>q[0]),ys=p.map(q=>q[1]);
  const pos=r.room_id==='R1'?[9,12,h+1]:[(Math.min(...xs)+Math.max(...xs))/2,(Math.min(...ys)+Math.max(...ys))/2,h+1];
  const label=document.createElement('div');label.className='label'+(fire?' fire':'');label.style.textAlign='center';const title=document.createElement('b');title.textContent=r.room_id+(fire?' · 화점':'');label.append(title,document.createElement('br'),document.createTextNode(r.name.replace('·화점','')));$('labels').append(label);labels.push({label,point:new T.Vector3(...pos)});
 }
 for(const v of f.openings){const [x,y]=v.center_m,w=v.width_m/2,z=v.soffit_m,color=v.a==='R5'?'#ffd16d':'#6ce0d0';add(line([[x-w,y,0],[x-w,y,z],[x+w,y,z],[x+w,y,0],[x-w,y,0]],color),color);}
 const asset={source_hash:B.source_hash,floors:[{id:'1F',group:source,objects,styles}]};
 const layer=new BuildingLayer(T,{geometryFor:()=>asset}),store=createStore({validators:{building:x=>x.schema==='pyrocast.building/1'}});
 store.dispatch('building/set',B);store.dispatch('floor/set',{floor_id:'1F'});
 const scene=new T.Scene();scene.background=new T.Color('#0c1c29');
 const host=createSceneHost({container:$('view'),THREE:T,store,scene,layers:[layer],clock:{now:()=>0}});
 let theta=-Math.PI/2+.16,elevation=.66,distance=85,top=false;
 function render(){const pos=top?[36,10,105]:[36+Math.cos(theta)*distance*Math.cos(elevation),10+Math.sin(theta)*distance*Math.cos(elevation),3+distance*Math.sin(elevation)];
  store.dispatch('camera/fit',{mode:top?'top':'all',target:[36,10,2],pose:{position:pos,up:[0,0,1]}});layer.syncSource();host.render();
  const box=$('view').getBoundingClientRect();for(const {label,point} of labels){const v=point.clone().project(host.camera);label.style.left=(v.x+1)*box.width/2+'px';label.style.top=(1-v.y)*box.height/2+'px';}
 }
 $('iso').onclick=()=>{top=false;render();};$('top').onclick=()=>{top=true;render();};$('slab').onchange=()=>{slabs.forEach(o=>o.visible=$('slab').checked);render();};
 let drag=null;const c=host.renderer.domElement;c.addEventListener('pointerdown',e=>{drag=[e.clientX,e.clientY];c.setPointerCapture(e.pointerId);});c.addEventListener('pointermove',e=>{if(!drag)return;theta+=(e.clientX-drag[0])*.006;elevation=Math.max(.15,Math.min(1.4,elevation+(e.clientY-drag[1])*.005));drag=[e.clientX,e.clientY];top=false;render();});c.addEventListener('pointerup',()=>drag=null);c.addEventListener('pointercancel',()=>drag=null);c.addEventListener('wheel',e=>{e.preventDefault();distance=Math.max(30,Math.min(160,distance*Math.exp(e.deltaY*.001)));top=false;render();},{passive:false});window.addEventListener('resize',render);
 const dl=(id,rows)=>{for(const [k,v] of rows){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=k;dd.textContent=v;$(id).append(dt,dd);}};
 dl('summary',[['범위','1층 · 8실'],['창 / 실내 문','0 / 0'],['외기 출입문','8개'],['모델 면적',F.rooms.reduce((s,r)=>s+r.area_m2,0).toFixed(1)+' m²'],['상부 높이','6.405 m']]);
 const r=F.rooms.find(r=>r.room_id==='R5');dl('fuel',[['내부 치수','8.75 × 18.0 m'],['출입문','2.5 × 3.0 m'],['PU 등가 하중',r.fire_load_MJ_m2.toFixed(1)+' MJ/m²'],['총 에너지',(r.energy_MJ/1000).toFixed(2)+' GJ'],['HRRPUA','400 kW/m²'],['피복률','0.5'],['벽·천장 / 바닥','PU / 콘크리트']]);
 for(const n of B.geometry_notes){const li=document.createElement('li');li.textContent=n;$('notes').append(li);}
 render();$('status').textContent='building/1 로드 완료 · 계산 0회';
 window.addEventListener('beforeunload',()=>{host.dispose();resources.forEach(r=>r.dispose());});
}catch(e){$('error').textContent=e.stack;$('status').textContent='표시 실패';throw e;}
