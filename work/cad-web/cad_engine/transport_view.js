// Existing croquis UI conventions, adapted from Y-up to this CAD viewer's Z-up.
// Input vertices already share the building coordinate frame; never recenter.
function addTransportGeometry(T,B,groups,extrude){
 const roots=[],ramps=[];
 const mats={stair:new T.MeshLambertMaterial({color:0xe5c35a,side:T.DoubleSide}),elev:new T.MeshLambertMaterial({color:0xffdf89,side:T.DoubleSide}),ramp:new T.MeshLambertMaterial({color:0xc59661,side:T.DoubleSide})};
 function root(i,kind){const g=new T.Group();g.name=B.floors[i].name+'_'+kind;g.userData.transportKind=kind;g.userData.floorIndex=i;groups[i].add(g);roots.push(g);return g;}
 function line(g,points,color,closed=false){const geo=new T.BufferGeometry().setFromPoints(points.map(p=>new T.Vector3(...p)));const obj=new (closed?T.LineLoop:T.Line)(geo,new T.LineBasicMaterial({color}));g.add(obj);return obj;}
 function box(g,w,d,h,x,y,z,color){const m=new T.Mesh(new T.BoxGeometry(w,d,h),new T.MeshLambertMaterial({color}));m.position.set(x,y,z);g.add(m);return m;}
 B.floors.forEach((f,i)=>{
  const stairs=root(i,'stair'),elev=root(i,'elev'),debug=root(i,'anchor'),road=root(i,'ramp');debug.visible=false;
  for(const c of f.transport||[]){
   for(const p of c.anchor)line(debug,p.o.map(([x,y])=>[x,y,.07]),0xe34d59,true);
   if(c.room_region)for(const p of c.room_region)line(debug,p.o.map(([x,y])=>[x,y,.08]),0x008984,true);
   if(c.kind==='stair'){
    for(const step of c.meshes){const m=extrude(step.polys,step.z0,step.z1,mats.stair);if(m){m.name=f.name+'_'+c.id+'_step';stairs.add(m);}}
    if(!c.meshes.length)for(const p of c.region)line(stairs,p.o.map(([x,y])=>[x,y,.08]),c.connected?0xe5c35a:0x999999,true);
   }else{
    const pts=c.anchor[0].o,xs=pts.map(p=>p[0]),ys=pts.map(p=>p[1]),cx=(Math.min(...xs)+Math.max(...xs))/2,cy=(Math.min(...ys)+Math.max(...ys))/2;
    // Floor marker indicates position, rather than inventing a cabin at every floor.
    line(elev,[[cx-.45,cy,.12],[cx,cy-.45,.12],[cx+.45,cy,.12],[cx,cy+.45,.12]],0xb78a16,true);
    for(const p of c.region){line(elev,p.o.map(([x,y])=>[x,y,.04]),0x8b70ba,true);for(const [x,y] of p.o)line(elev,[[x,y,0],[x,y,f.h]],0xc5b9d8);}
    for(const id of c.door_ids||[]){const o=f.openings.find(o=>o.id===id);if(!o)continue;
     const p=o.geometry_polys?.[0]?.o||o.polys[0];let a=p[0],b=p[1],len=0;
     p.forEach((q,k)=>{const r=p[(k+1)%p.length],d=Math.hypot(r[0]-q[0],r[1]-q[1]);if(d>len){len=d;a=q;b=r;}});
     const g=new T.Group();g.position.set((a[0]+b[0])/2,(a[1]+b[1])/2,0);g.rotation.z=Math.atan2(b[1]-a[1],b[0]-a[0]);elev.add(g);const h=o.door_h||2.1;
     box(g,.08,.16,h,-len/2,0,h/2,0xb68a13);box(g,.08,.16,h,len/2,0,h/2,0xb68a13);box(g,len+.08,.16,.08,0,0,h,0xb68a13);
     for(const side of [-1,1])box(g,Math.max(.05,len/2-.02),.045,h-.08,side*len/4,0,(h-.08)/2,0xffe7a1);
     box(g,.014,.055,h-.08,0,-.025,(h-.08)/2,0x927019);
    }
   }
  }
  for(const r of f.model_ramps||[]){
   const vertices=[],N=Math.min(r.inner.length,r.outer.length);
   for(let k=0;k<N-1;k++)for(const [side,j] of [[0,k],[1,k],[1,k+1],[0,k],[1,k+1],[0,k+1]]){const q=side?r.outer[j]:r.inner[j];vertices.push(q[0],q[1],0);}
   const geo=new T.BufferGeometry();geo.setAttribute('position',new T.Float32BufferAttribute(vertices,3));const mesh=new T.Mesh(geo,mats.ramp);road.add(mesh);
   const edges=[];for(const path of [r.inner,r.outer])edges.push(line(road,path.map(q=>[...q,0]),0x845528));
   ramps.push({data:r,geo,edges,N});
  }
 });
 function slope(percent,reverse=false){for(const r of ramps){const a=r.geo.attributes.position;let index=0;const rise=r.data.length_m*percent/100;
  for(let k=0;k<r.N-1;k++)for(const j of [k,k,k+1,k,k+1,k+1])a.setZ(index++,.035+rise*(reverse?1-j/(r.N-1):j/(r.N-1)));
  a.needsUpdate=true;r.geo.computeVertexNormals();r.geo.computeBoundingBox();r.geo.computeBoundingSphere();
  r.edges.forEach(e=>{const a=e.geometry.attributes.position;for(let j=0;j<r.N;j++)a.setZ(j,.06+rise*(reverse?1-j/(r.N-1):j/(r.N-1)));a.needsUpdate=true;e.geometry.computeBoundingSphere();});
 }}
 slope(10);return {roots,ramps,slope};
}
