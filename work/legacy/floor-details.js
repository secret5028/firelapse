function addFloorDetails(T,group,p,convert,y){
 for(const room of p.roomLabels||[]){
  const [x,z]=convert(room.point),c=document.createElement('canvas');const ctx=c.getContext('2d');ctx.font='32px sans-serif';c.width=Math.ceil(ctx.measureText(room.name).width)+36;c.height=64;ctx.fillStyle='#12334be8';ctx.fillRect(0,0,c.width,c.height);ctx.strokeStyle='#7195ab';ctx.strokeRect(1,1,c.width-2,c.height-2);ctx.font='32px sans-serif';ctx.fillStyle='#f2f7fb';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(room.name,c.width/2,c.height/2);
  const label=new T.Sprite(new T.SpriteMaterial({map:new T.CanvasTexture(c),transparent:true,depthTest:false,sizeAttenuation:false}));label.position.set(x,y+.35,z);label.scale.set(c.width/512*.14,c.height/512*.14,1);label.userData.layer='roomNames';label.renderOrder=30;group.add(label);
 }

 if(typeof addCentralOpen==='function')addCentralOpen(T,group,p,convert,y);
 if(p.floorOutline?.length>=3){
  const shape=new T.Shape(),points=p.floorOutline.map(convert);shape.moveTo(...points[0]);for(const q of points.slice(1))shape.lineTo(...q);shape.closePath();
  for(const contour of p.floorHoles||[]){const hole=new T.Path(),ps=contour.map(convert);hole.moveTo(...ps[0]);for(const q of ps.slice(1))hole.lineTo(...q);hole.closePath();shape.holes.push(hole);}
  const geo=new T.ExtrudeGeometry(shape,{depth:.16,bevelEnabled:false});geo.rotateX(Math.PI/2);
  const slab=new T.Mesh(geo,new T.MeshStandardMaterial({color:p.floor<0?'#aabec5':((p.isRoof===true||/지붕|옥상/.test(p.levelLabel||''))?'#93acb5':'#d4d0b7'),side:T.DoubleSide}));slab.userData.layer='floor';slab.position.y=y;group.add(slab);
  const edges=new T.LineSegments(new T.EdgesGeometry(geo,30),new T.LineBasicMaterial({color:'#637f91',transparent:true,opacity:.4}));edges.userData.layer='floor';edges.position.y=y;group.add(edges);
 }
 for(const st of p.stairs||[]){
  const a=convert(st.a),b=convert(st.b),width=Math.abs(b[0]-a[0]),length=Math.abs(b[1]-a[1]),rise=p.height;
  const x=Math.min(a[0],b[0]),z=Math.min(a[1],b[1]),landing=Math.min(width*.5,1.3),run=length-landing;
  const count=Math.max(4,Math.ceil(rise/.36)),step=run/count;
  const material=new T.MeshStandardMaterial({color:'#e5c35a'});const stairPositions=[];
  function box(w,h,d,px,py,pz){const m=new T.Mesh(new T.BoxGeometry(w,h,d),material);m.position.set(px,py,pz);m.updateMatrix();const g=m.geometry;g.applyMatrix4(m.matrix);stairPositions.push(...g.getAttribute('position').array);g.dispose();}
  for(let i=0;i<count;i++){
   const h=(i+1)*rise/(2*count);box(width*.46,.1,step,x+width*.24,y+h-.05,z+length-(i+.5)*step);
   box(width*.46,.1,step,x+width*.76,y+rise/2+h-.05,z+landing+(i+.5)*step);
  }
  box(width,.14,landing,x+width/2,y+rise/2-.07,z+landing/2);
  // Top landing meets the upper floor edge; all dimensions remain flagged as approximate.
  box(width*.5,.14,.5,x+width*.75,y+rise-.07,z+length+.25);
  const stairGeo=new T.BufferGeometry();stairGeo.setAttribute('position',new T.Float32BufferAttribute(stairPositions,3));stairGeo.computeVertexNormals();const stairMesh=new T.Mesh(stairGeo,material);stairMesh.userData.layer='stairs';group.add(stairMesh);
 }
}
// Width comes from the opening endpoints. Never infer type from width.
// Width comes from the opening endpoints. Never infer type from width.
function addDoorSwing(T,group,sh,a,b,y){
 const w=Math.hypot(b[0]-a[0],b[1]-a[1]);if(w<.1)return;
 const h=sh.openingHeight||2.1,u=[(b[0]-a[0])/w,(b[1]-a[1])/w],n=[-u[1],u[0]];
 const kind=sh.openingKind||'unknown';
 const at=(t,z=0,v=.025)=>new T.Vector3(a[0]+u[0]*t+n[0]*z,y+v,a[1]+u[1]*t+n[1]*z);
 function line(points){const obj=new T.Line(new T.BufferGeometry().setFromPoints(points),new T.LineBasicMaterial({color:0xe8bd49}));obj.userData={layer:'opening',doorType:kind,widthM:w};group.add(obj);}
 // Thin opening outline replaces the thick frame and upright swung leaf.
 line([at(0,0,0),at(0,0,h),at(w,0,h),at(w,0,0)]);
 function arrow(start,end){line([at(start),at(end)]);const sign=Math.sign(end-start);line([at(end-sign*.12,-.08),at(end),at(end-sign*.12,.08)]);}
 if(/sliding/i.test(kind)){const double=/double/i.test(kind)||sh.leaves===2;arrow(w*.48,w*.08);if(double)arrow(w*.52,w*.92);}
 else if(/revolv/i.test(kind)){const r=Math.min(w/2,.7);line(Array.from({length:17},(_,i)=>at(w/2+r*Math.cos(i*Math.PI/8),r*Math.sin(i*Math.PI/8))));}
 else if(/swing|hinged|single|double/i.test(kind)){
  const count=/double/i.test(kind)||sh.leaves===2?2:1;
  if(![-1,1].includes(sh.swingSide)||(count===1&&!['start','end'].includes(sh.hinge)))return;
  const side=sh.swingSide,angle=Math.min(180,Math.max(1,sh.openingAngle||90))*Math.PI/180;
  for(let i=0;i<count;i++){
   const end=count===2?i===1:sh.hinge==='end',x=end?w:0,r=w/count,sign=end?-1:1;
   const arc=Array.from({length:25},(_,j)=>{const t=angle*j/24;return at(x+sign*r*Math.cos(t),side*r*Math.sin(t));});
   line(arc);line([at(x),arc[arc.length-1]]);
  }
 }
 // Unknown type: outline only, with no invented swing or second leaf.
}

function addSceneReferences(T,scene,pages){
 const ext=[];for(const p of pages){const points=p.floorOutline||p.shapes.flatMap(s=>[s.a,s.b]);const origin=p.origin||[Math.min(...points.map(q=>q[0])),Math.min(...points.map(q=>q[1]))];for(const q of points)ext.push([(q[0]-origin[0])*p.scale,(q[1]-origin[1])*p.scale]);}
 if(!ext.length)return;
 const minX=Math.min(...ext.map(q=>q[0])),maxX=Math.max(...ext.map(q=>q[0])),maxZ=Math.max(...ext.map(q=>q[1]));
 const gridSize=Math.ceil(Math.max(maxX-minX,maxZ,60)/10)*10+40;
 const grid=new T.GridHelper(gridSize,gridSize,'#4b697e','#294457');grid.position.set((maxX+minX)/2,-.19,maxZ/2);grid.material.transparent=true;grid.material.opacity=.65;scene.add(grid);
 const ref=new T.Group();ref.position.set((minX+maxX)/2,-.16,maxZ+5);scene.add(ref);
 const materials={};const material=color=>materials[color]||(materials[color]=new T.MeshStandardMaterial({color,roughness:.65}));
 function box(w,h,d,x,y,z,color){const m=new T.Mesh(new T.BoxGeometry(w,h,d),material(color));m.position.set(x,y,z);ref.add(m);return m;}
 function cylinder(r,h,x,y,z,color,rotate=false){const m=new T.Mesh(new T.CylinderGeometry(r,r,h,20),material(color));m.position.set(x,y,z);if(rotate)m.rotation.x=Math.PI/2;ref.add(m);return m;}
 // Eight metre reference vehicle: chassis, cab, equipment body, roller doors and roof ladder.
 box(8,.24,2.35,0,.8,0,'#35444e');box(5.25,1.95,2.35,-1.25,1.9,0,'#bd2435');box(2.3,2.1,2.4,2.75,1.95,0,'#d73542');
 box(.04,.85,2.05,3.92,2.36,0,'#315a70');for(const z of [-1.211,1.211]){box(1.5,.8,.025,2.6,2.4,z,'#315a70');box(7.7,.16,.03,0,1.31,z,'#f3eee2');box(.28,.12,.05,3.5,1.03,z,'#fff3bc');for(const x of [-2.9,-1.25,.4]){box(1.35,1.38,.025,x,2.02,z,'#a4b0b7');for(let j=0;j<8;j++)box(1.29,.022,.038,x,1.45+j*.16,z,'#677781');}}
 for(const x of [-2.5,2.75])for(const z of [-1.18,1.18]){cylinder(.52,.28,x,.52,z,'#17232b',true);cylinder(.26,.3,x,.52,z,'#aebac1',true);}
 box(2.4,.15,2.6,2.7,.89,0,'#aebac1');box(1.4,.16,.35,2.7,3.1,0,'#458ce4');
 for(const z of [-.43,.43])box(4.9,.065,.065,-1.4,3.03,z,'#e9e9dd');for(let i=0;i<13;i++)box(.06,.055,.86,-3.7+i*.37,3.03,0,'#e9e9dd');
 // Human height is 1.75m, with feet resting on the same ground as the vehicle.
 const hx=5.1,hz=-.4;for(const dx of [-.12,.12]){box(.15,.67,.18,hx+dx,.42,hz,'#354956');box(.17,.12,.3,hx+dx,.06,hz+.055,'#202a33');}
 box(.45,.57,.23,hx,1.02,hz,'#e4ac36');for(const dx of [-.29,.29]){const arm=box(.13,.54,.15,hx+dx,1.0,hz,'#dca640');arm.rotation.z=dx>0?.10:-.10;}
 cylinder(.15,.28,hx,1.46,hz,'#d8ac83');const helmet=new T.Mesh(new T.SphereGeometry(.18,18,12,0,Math.PI*2,0,Math.PI/2),material('#efd267'));helmet.position.set(hx,1.57,hz);ref.add(helmet);
 const cv=document.createElement('canvas');cv.width=640;cv.height=80;const cx=cv.getContext('2d');cx.fillStyle='#18364ce8';cx.fillRect(0,0,640,80);cx.fillStyle='#e6f3ff';cx.font='28px Malgun Gothic';cx.textAlign='center';cx.fillText('소방차 8m · 사람 1.75m · 격자 1m',320,51);
 const label=new T.Sprite(new T.SpriteMaterial({map:new T.CanvasTexture(cv),depthTest:true}));label.position.set(0,.35,2.8);label.scale.set(10,1.25,1);ref.add(label);
}
