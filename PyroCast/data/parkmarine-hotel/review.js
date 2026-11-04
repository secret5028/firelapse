import * as T from 'three';
import {createModelReview,reviewRows} from '/app/web/panels/model_review.js';
const $=id=>document.getElementById(id);
try{
 const B=await(await fetch('building.json')).json(),rows=reviewRows(B);
 const scene=new T.Scene();scene.background=new T.Color('#102331');
 const camera=new T.PerspectiveCamera(45,1,.1,2000);camera.up.set(0,0,1);
 const renderer=new T.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));$('scene').prepend(renderer.domElement);
 let group=null,resources=[],chosen=null,top=false,theta=-.7,elevation=.8,distance=65,target=new T.Vector3(),floorName='1F';
 const line=(pts,color,opacity=1)=>{const g=new T.BufferGeometry().setFromPoints(pts.map(p=>new T.Vector3(...p))),m=new T.LineBasicMaterial({color,transparent:true,opacity,depthTest:false});resources.push(g,m);const o=new T.Line(g,m);group.add(o);return o;};
 function show(name,selected=null){floorName=name;chosen=selected;$('floor').value=name;if(group){scene.remove(group);resources.forEach(x=>x.dispose());}resources=[];group=new T.Group();scene.add(group);
  const f=B.floors.find(x=>x.name===name),points=f.rooms.flatMap(r=>r.polys.flatMap(p=>p.o||p)),xs=points.map(p=>p[0]),ys=points.map(p=>p[1]);
  target.set((Math.min(...xs)+Math.max(...xs))/2,(Math.min(...ys)+Math.max(...ys))/2,f.h/2);distance=Math.max(Math.max(...xs)-Math.min(...xs),Math.max(...ys)-Math.min(...ys))*1.55;
  for(const r of f.rooms){const issue=rows.some(x=>x.floor===name&&x.id===r.id&&x.status!=='자동보정'),color=chosen?.id===r.id?'#42e8ff':issue?'#edbf75':r.axiom_core_kind?'#a7d7e9':'#839dad';
   for(const part of r.polys){const p=part.o||part,shape=new T.Shape(p.map(q=>new T.Vector2(...q)));for(const hole of part.h||[])shape.holes.push(new T.Path(hole.map(q=>new T.Vector2(...q))));
    const g=new T.ShapeGeometry(shape),m=new T.MeshBasicMaterial({color,side:T.DoubleSide,transparent:true,opacity:issue?.15:.05,depthWrite:false});resources.push(g,m);group.add(new T.Mesh(g,m));
    for(const z of [.02,f.h])line([...p,p[0]].map(q=>[...q,z]),color,.65);
    for(let i=0;i<p.length;i++)line([[...p[i],0],[...p[i],f.h]],'#637f90',.15);
   }
  }
  for(const c of f.structural_columns||[])for(const part of c.polys){const p=part.o||part,shape=new T.Shape(p.map(q=>new T.Vector2(...q)));
   const g=new T.ExtrudeGeometry(shape,{depth:c.height_m||f.h,bevelEnabled:false}),m=new T.MeshBasicMaterial({color:chosen?.id===c.source_room_id?'#42e8ff':'#8495a0',transparent:true,opacity:.7});
   resources.push(g,m);group.add(new T.Mesh(g,m));
   for(const z of [.03,f.h])line([...p,p[0]].map(q=>[...q,z]),'#c2e8ed',.9);
  }
  for(const r of rows.filter(x=>x.floor===name&&x.point_m)){const [x,y]=r.point_m;line([[x-.2,y,.2],[x+.2,y,.2]],'#edbf75');line([[x,y-.2,.2],[x,y+.2,.2]],'#edbf75');}
  for(const o of f.openings){const own=rows.filter(x=>x.floor===name&&x.id===o.id),color=chosen?.id===o.id?'#42e8ff':own.some(x=>x.status==='자동보정')?'#7bd6c4':own.length?'#edbf75':'#638497';
   if(!o.superseded_by)for(const part of o.autocorrect_aperture_polys||o.geometry_polys||o.polys||[]){const p=part.o||part;if(p.length)line([...p,p[0]].map(q=>[...q,.1]),color,1);}
   if(!o.source_parent_id)for(const l of o.leaves||[]){
    if(!l.open)continue;
    const a=Math.atan2(l.closed[1]-l.hinge[1],l.closed[0]-l.hinge[0]),b=Math.atan2(l.open[1]-l.hinge[1],l.open[0]-l.hinge[0]);let delta=(b-a+Math.PI*3)%(Math.PI*2)-Math.PI;
    const r=l.r||Math.hypot(l.closed[0]-l.hinge[0],l.closed[1]-l.hinge[1]);
    line(Array.from({length:25},(_,i)=>[l.hinge[0]+r*Math.cos(a+delta*i/24),l.hinge[1]+r*Math.sin(a+delta*i/24),.13]),color,.9);
    line([[...l.hinge,.13],[...l.closed,.13]],color,.9);
   }
  }
  const selectedRoom=f.rooms.find(r=>r.id===selected?.id)||(f.structural_columns||[]).find(c=>c.source_room_id===selected?.id),selectedOpening=f.openings.find(o=>o.id===selected?.id);
  if(selectedRoom||selectedOpening){const p=(selectedRoom?.polys||selectedOpening?.polys||[]).flatMap(p=>p.o||p);if(p.length){const xx=p.map(q=>q[0]),yy=p.map(q=>q[1]);target.set((Math.min(...xx)+Math.max(...xx))/2,(Math.min(...yy)+Math.max(...yy))/2,.2);distance=Math.max(7,Math.max(Math.max(...xx)-Math.min(...xx),Math.max(...yy)-Math.min(...yy))*2.5);}}
  else if(selected?.point_m){target.set(...selected.point_m,.2);distance=12;}
  $('selected').textContent=chosen?`${chosen.floor} ${chosen.id} · ${chosen.status} · ${chosen.detail}`:`${name} · ${f.rooms.length}실 · 모서리 드래그 회전 / 휠 확대`;
  render();
 }
 function render(){const w=$('scene').clientWidth,h=$('scene').clientHeight;renderer.setSize(w,h,false);camera.aspect=w/h;camera.position.copy(target).add(top?new T.Vector3(0,-.01,distance):new T.Vector3(Math.cos(theta)*distance*Math.cos(elevation),Math.sin(theta)*distance*Math.cos(elevation),distance*Math.sin(elevation)));camera.lookAt(target);camera.updateProjectionMatrix();renderer.render(scene,camera);}
 const panel=createModelReview({container:$('review'),building:B,onLocate:r=>show(r.floor,r)});
 for(const f of B.floors){const o=document.createElement('option');o.value=f.name;o.textContent=f.name;$('floor').append(o);}
 $('floor').onchange=()=>show($('floor').value);$('top').onclick=()=>{top=true;render();};$('iso').onclick=()=>{top=false;render();};
 let drag=null;renderer.domElement.onpointerdown=e=>{drag=[e.clientX,e.clientY];renderer.domElement.setPointerCapture(e.pointerId);};renderer.domElement.onpointermove=e=>{if(!drag)return;theta+=(e.clientX-drag[0])*.006;elevation=Math.max(.15,Math.min(1.5,elevation+(e.clientY-drag[1])*.005));drag=[e.clientX,e.clientY];top=false;render();};renderer.domElement.onpointerup=renderer.domElement.onpointercancel=()=>drag=null;
 renderer.domElement.addEventListener('wheel',e=>{e.preventDefault();distance=Math.max(5,Math.min(250,distance*Math.exp(e.deltaY*.001)));render();},{passive:false});window.addEventListener('resize',render);
 const count=k=>rows.filter(r=>r.kind===k).length;
 $('summary').textContent=`${B.floors.length}개 도면 층 · ${B.floors.reduce((n,f)=>n+f.rooms.length,0)}공간 · 기둥 재분류 ${B.floors.reduce((n,f)=>n+(f.structural_columns||[]).length,0)}개 | 자동보정 ${B.model_review.corrections.length}건 | 연결 미확인 ${count('isolated_room')}공간 | 로더 오류 ${count('loader_failed')}층`;
 window.addEventListener('beforeunload',()=>{panel.dispose();resources.forEach(x=>x.dispose());renderer.dispose();});show(floorName);
 const query=new URLSearchParams(location.search);if(query.has('floor'))show(query.get('floor'),query.has('room')?{floor:query.get('floor'),id:query.get('room'),status:'실 확인',detail:'문 호와 연결 검토'}:null);
 window.__reviewReady=true;
}catch(e){$('error').textContent=e.stack;throw e;}
