// Source-position markers: these symbols do not assert shaft or cabin dimensions.
function addElevatorMarker(T,parent,x,y,z,name='승강기'){
 const g=new T.Group();g.userData.layer='elevator';g.name=name;parent.add(g);
 const face=new T.Mesh(new T.CircleGeometry(.65,4),new T.MeshBasicMaterial({color:0xffdb57,transparent:true,opacity:.65,depthWrite:false,side:T.DoubleSide}));face.rotation.x=-Math.PI/2;face.rotation.z=Math.PI/4;face.position.set(x,y+.06,z);g.add(face);
 const ring=new T.LineLoop(new T.BufferGeometry().setFromPoints([[-.65,0],[0,-.65],[.65,0],[0,.65]].map(([a,b])=>new T.Vector3(x+a,y+.08,z+b))),new T.LineBasicMaterial({color:0xc99a12,depthWrite:false}));g.add(ring);
 const c=document.createElement('canvas');c.width=256;c.height=64;const ctx=c.getContext('2d');ctx.fillStyle='#ffe28e';ctx.fillRect(0,0,256,64);ctx.strokeStyle='#ae7d08';ctx.lineWidth=4;ctx.strokeRect(2,2,252,60);ctx.fillStyle='#614500';ctx.font='bold 27px sans-serif';ctx.textAlign='center';ctx.fillText('↕ '+name,128,42,242);
 const label=new T.Sprite(new T.SpriteMaterial({map:new T.CanvasTexture(c),depthTest:false,depthWrite:false}));label.position.set(x,y+1.25,z);label.scale.set(2.6,.65,1);g.add(label);return g;
}
function addPageElevators(T,group,p,convert,y){
 for(const e of p.elevators||[]){const [x,z]=convert(e.p);addElevatorMarker(T,group,x,y,z,e.name);if(e.door)addElevatorDoor(T,group,convert(e.door.a),convert(e.door.b),y);}
}
function addElevatorDoor(T,parent,a,b,y){
 const width=Math.hypot(b[0]-a[0],b[1]-a[1]),height=2.1,g=new T.Group();g.userData.layer='elevator';g.userData.assumption='중앙개폐 슬라이딩문 · 높이 2.1m 기본값';parent.add(g);
 g.position.set((a[0]+b[0])/2,y,(a[1]+b[1])/2);g.rotation.y=-Math.atan2(b[1]-a[1],b[0]-a[0]);
 const box=(w,h,d,x,yy,color)=>{const m=new T.Mesh(new T.BoxGeometry(w,h,d),new T.MeshBasicMaterial({color}));m.position.set(x,yy,0);g.add(m);return m;};
 box(.09,height,.22,-width/2,height/2,0xb68a13);box(.09,height,.22,width/2,height/2,0xb68a13);box(width+.09,.1,.22,0,height,0xb68a13);
 for(const side of [-1,1]){const m=box(width/2-.018,height-.08,.055,side*width/4,(height-.08)/2,0xffe7a1);const edge=new T.LineSegments(new T.EdgesGeometry(m.geometry),new T.LineBasicMaterial({color:0xc29b33}));edge.position.copy(m.position);g.add(edge);}
 // Central seam and threshold distinguish sliding panels from swing doors.
 box(.015,height-.08,.065,0,(height-.08)/2,0x927019);box(width,.025,.24,0,.015,0xb68a13);
 return g;
}
