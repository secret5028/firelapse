// Display-only subtraction of opening interiors from CAD wall line segments.
// Coordinates are floor-local; opening frames and wall meshes are never edited.
export function wallOpeningVolumes(floor,time=0){
 const cuts=[];
 for(const o of floor.openings||[]){
  if(!['door','door_elev','open_passage','window'].includes(o.kind))continue;
  const doorLike=o.kind!=='window';
  let fraction=1;if(o.display_schedule){fraction=0;for(const [t,f] of o.display_schedule)if(t<=time)fraction=f;}
  if(!(fraction>0))continue;
  const rings=o.polys?.length?o.polys:(o.geometry_polys||[]).map(p=>p.o),points=rings.flat();
  let spans=(o.leaves||[]).filter(l=>l.hinge&&l.closed).map(l=>[l.hinge,l.closed]);
  if(!spans.length){let longest=0,span=null;for(const ring of rings)for(let i=0;i<ring.length;i++){
   const a=ring[i],b=ring[(i+1)%ring.length],d=Math.hypot(b[0]-a[0],b[1]-a[1]);if(d>longest){longest=d;span=[a,b];}
  }if(span)spans=[span];}
  const bottom=doorLike?(o.sill_m??0):(o.sill_m??o.sill??floor.sill??.9),top=doorLike?(o.door_h??floor.door_h??2.1):(o.head??floor.head??2.4);
  if(!(top>bottom))continue;
  for(const [a,b] of spans){const length=Math.hypot(b[0]-a[0],b[1]-a[1]);if(!(length>.02))continue;
   const u=[(b[0]-a[0])/length,(b[1]-a[1])/length],v=[-u[1],u[0]],along=p=>p[0]*u[0]+p[1]*u[1],across=p=>p[0]*v[0]+p[1]*v[1];
   // Window footprint may have several fragments: use its entire projected span.
   let lo=along(a),hi=along(b);if(o.kind==='window'&&points.length){lo=Math.min(...points.map(along));hi=Math.max(...points.map(along));}
   const center=(lo+hi)/2,half=(hi-lo)*fraction/2;
   const normal=across(a),near=points.length?Math.min(normal,...points.map(across)):normal-.075,far=points.length?Math.max(normal,...points.map(across)):normal+.075;
   const jambs=[center-half,center+half];
   // CAD jamb footprints can be wider/bevelled relative to the swing-leaf line.
   // Their extrusion corners must stop at the opening head as well.
   const seams=fraction===1?[...jambs,...points.map(along)]:jambs;
   cuts.push({id:o.id,u,v,jambs,seams,bottom,top,min:[center-half+.005,near-.015,bottom===0?-.015:bottom+.005],max:[center+half-.005,far+.015,top-.005]});
  }
 }
 return cuts;
}
export function outsideOpeningIntervals(a,b,cuts){
 let kept=[[0,1]];
 for(const c of cuts){
  const project=p=>[p[0]*c.u[0]+p[1]*c.u[1],p[0]*c.v[0]+p[1]*c.v[1],p[2]],p=project(a),q=project(b);
  let lo=0,hi=1,hit=true;
  for(let k=0;k<3;k++){const d=q[k]-p[k];if(Math.abs(d)<1e-10){if(p[k]<c.min[k]||p[k]>c.max[k]){hit=false;break;}}
   else {let x=(c.min[k]-p[k])/d,y=(c.max[k]-p[k])/d;if(x>y)[x,y]=[y,x];lo=Math.max(lo,x);hi=Math.min(hi,y);if(hi<=lo){hit=false;break;}}}
  if(!hit||hi<=lo)continue;
  kept=kept.flatMap(([x,y])=>hi<=x||lo>=y?[[x,y]]:[[x,Math.min(y,lo)],[Math.max(x,hi),y]].filter(([i,j])=>j-i>1e-8));
  if(!kept.length)break;
 }
 return kept;
}
// Extruded lintel/sill bands create artificial vertical seams at opening sides.
// Keep the actual jamb, but remove its extension above/below the rectangle.
// Only vertical wall edges at that opening are affected; roof edges, remote
// walls, meshes and the independent opening-frame layer remain untouched.
export function outsideWallOpeningIntervals(a,b,cuts){
 const vertical=Math.hypot(b[0]-a[0],b[1]-a[1])<1e-5&&Math.abs(b[2]-a[2])>1e-6;
 if(!vertical)return outsideOpeningIntervals(a,b,cuts);
 const extensions=[];
 for(const c of cuts){
  const along=a[0]*c.u[0]+a[1]*c.u[1],normal=a[0]*c.v[0]+a[1]*c.v[1];
  const acrossOpening=along>=c.min[0]-.025&&along<=c.max[0]+.025;
  if(normal<c.min[1]||normal>c.max[1]||(!acrossOpening&&!(c.seams||c.jambs)?.some(x=>Math.abs(along-x)<=.02)))continue;
  for(const [low,high] of [[-1e6,c.bottom],[c.top,1e6]])extensions.push({...c,min:[along-.025,c.min[1],low],max:[along+.025,c.max[1],high]});
 }
 return outsideOpeningIntervals(a,b,[...cuts,...extensions]);
}
export function trimWallLineGeometry(T,source,floorGroup,cuts){
 if(!source.isLineSegments||!(source.userData.cadOutline||/_(edge|wall)(_|$)/i.test(source.name||''))||!cuts.length)return null;
 const g=source.geometry,pos=g?.attributes.position;if(!pos)return null;
 source.updateWorldMatrix(true,false);floorGroup.updateWorldMatrix(true,false);
 const transform=new T.Matrix4().copy(floorGroup.matrixWorld).invert().multiply(source.matrixWorld),a=new T.Vector3(),b=new T.Vector3(),arrays={};
 for(const name of Object.keys(g.attributes))arrays[name]=[];
 let changed=false;const count=g.index?.count??pos.count,start=g.drawRange.start||0,end=Math.min(count,start+g.drawRange.count);
 for(let i=start;i+1<end;i+=2){const ia=g.index?g.index.getX(i):i,ib=g.index?g.index.getX(i+1):i+1;
  a.fromBufferAttribute(pos,ia).applyMatrix4(transform);b.fromBufferAttribute(pos,ib).applyMatrix4(transform);
  const intervals=outsideWallOpeningIntervals(a.toArray(),b.toArray(),cuts);if(intervals.length!==1||intervals[0][0]!==0||intervals[0][1]!==1)changed=true;
  for(const [lo,hi] of intervals)for(const t of [lo,hi])for(const [name,attr] of Object.entries(g.attributes))for(let k=0;k<attr.itemSize;k++){
   const x=attr.getComponent(ia,k),y=attr.getComponent(ib,k);arrays[name].push(x+(y-x)*t);
  }
 }
 if(!changed)return null;
 const result=new T.BufferGeometry();for(const [name,values] of Object.entries(arrays))result.setAttribute(name,new T.Float32BufferAttribute(values,g.attributes[name].itemSize));
 result.computeBoundingSphere();return result;
}
// Transparent extruded wall bands also expose their internal end caps as dark
// stripes above/below a jamb. Trim only those vertical caps, not wall fronts.
export function trimWallJambFaces(T,source,floorGroup,cuts){
 if(!source.isMesh||!/(?:_wall|_door_head|_win_low|_win_head)$/.test(source.name||'')||!cuts.length)return null;
 const g=source.geometry,pos=g?.attributes.position;if(!pos)return null;
 source.updateWorldMatrix(true,false);floorGroup.updateWorldMatrix(true,false);
 const matrix=new T.Matrix4().copy(floorGroup.matrixWorld).invert().multiply(source.matrixWorld),p=new T.Vector3(),arrays={};
 for(const name of Object.keys(g.attributes))arrays[name]=[];
 const vertex=i=>{p.fromBufferAttribute(pos,i).applyMatrix4(matrix);return {world:p.toArray(),attrs:Object.fromEntries(Object.entries(g.attributes).map(([name,a])=>[name,Array.from({length:a.itemSize},(_,k)=>a.getComponent(i,k))]))};};
 const blend=(a,b,t)=>({world:a.world.map((x,k)=>x+(b.world[k]-x)*t),attrs:Object.fromEntries(Object.keys(a.attrs).map(name=>[name,a.attrs[name].map((x,k)=>x+(b.attrs[name][k]-x)*t)]))});
 const clip=(poly,z,above)=>{const out=[];for(let i=0;i<poly.length;i++){const a=poly[i],b=poly[(i+1)%poly.length],ia=above?a.world[2]>=z:a.world[2]<=z,ib=above?b.world[2]>=z:b.world[2]<=z;if(ia)out.push(a);if(ia!==ib)out.push(blend(a,b,(z-a.world[2])/(b.world[2]-a.world[2])));}return out;};
 let changed=false;const count=g.index?.count??pos.count,start=g.drawRange.start||0,end=Math.min(count,start+g.drawRange.count);
 for(let i=start;i+2<end;i+=3){let poly=[0,1,2].map(k=>vertex(g.index?g.index.getX(i+k):i+k));
  for(const c of cuts){if(poly.length<3)break;
   const xyz=poly.map(v=>v.world),us=xyz.map(v=>v[0]*c.u[0]+v[1]*c.u[1]),vs=xyz.map(v=>v[0]*c.v[0]+v[1]*c.v[1]),zs=xyz.map(v=>v[2]);
   if(Math.max(...zs)-Math.min(...zs)<1e-6||Math.max(...us)-Math.min(...us)>.025||!(c.seams||c.jambs).some(j=>us.every(u=>Math.abs(j-u)<=.025))||vs.some(v=>v<c.min[1]||v>c.max[1]))continue;
   if(Math.min(...zs)>=c.bottom-1e-6&&Math.max(...zs)<=c.top+1e-6)continue;
   poly=clip(clip(poly,c.bottom,true),c.top,false);changed=true;
  }
  for(let k=1;k+1<poly.length;k++)for(const v of [poly[0],poly[k],poly[k+1]])for(const name of Object.keys(arrays))arrays[name].push(...v.attrs[name]);
 }
 if(!changed)return null;
 const result=new T.BufferGeometry();for(const [name,values] of Object.entries(arrays))result.setAttribute(name,new T.Float32BufferAttribute(values,g.attributes[name].itemSize));
 result.computeBoundingSphere();return result;
}
