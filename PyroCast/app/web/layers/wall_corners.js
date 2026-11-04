import {outsideWallOpeningIntervals} from './wall_opening_lines.js';
// Display geometry only: reject seams inside the union of touching wall pieces.
export const isWallMesh=o=>o.isMesh&&/(?:_wall|_door_head|_win_low|_win_head)$/.test(o.name||'');
export function isReplacedWallOutline(T,o,floor){
 if(!o.isLineSegments)return false;if(/_(edge|wall)(_|$)/i.test(o.name||''))return true;if(!o.userData.cadOutline)return false;
 const bounds=source=>{source.updateWorldMatrix(true,false);source.geometry.computeBoundingBox();return source.geometry.boundingBox.clone().applyMatrix4(source.matrixWorld);};
 const b=bounds(o);return floor.objects.filter(isWallMesh).some(m=>{const q=bounds(m);return b.min.distanceTo(q.min)<.002&&b.max.distanceTo(q.max)<.002;});
}
function insideRing(p,ring){let yes=false;for(let i=0,j=ring.length-1;i<ring.length;j=i++){const a=ring[i],b=ring[j];if((a.y>p.y)!==(b.y>p.y)&&p.x<(b.x-a.x)*(p.y-a.y)/(b.y-a.y)+a.x)yes=!yes;}return yes;}
function solidFor(T,source,floor){
 source.updateWorldMatrix(true,false);floor.updateWorldMatrix(true,false);const matrix=new T.Matrix4().copy(floor.matrixWorld).invert().multiply(source.matrixWorld),inverse=matrix.clone().invert(),geo=source.geometry;
 geo.computeBoundingBox();const bounds=geo.boundingBox.clone(),world=bounds.clone().applyMatrix4(matrix),shapes=geo.parameters?.shapes;
 const polys=shapes?(Array.isArray(shapes)?shapes:[shapes]).map(s=>({o:s.getPoints(1),h:s.holes.map(h=>h.getPoints(1))})):null;
 // CAD extrusion has a translated z range; XY shape coordinates remain CAD-local.
 if(!polys&&geo.type!=='BoxGeometry')return null;
 const p=new T.Vector3();return {source,matrix,world,inside(v){if(!world.containsPoint(v))return false;p.copy(v).applyMatrix4(inverse);if(!bounds.containsPoint(p))return false;return !polys||polys.some(q=>insideRing(p,q.o)&&!q.h.some(h=>insideRing(p,h)));}};
}
export function wallCornerSegments(T,floor,cuts){
 const solids=floor.objects.filter(isWallMesh).map(o=>solidFor(T,o,floor.group)).filter(Boolean),segments=[],seen=new Set();
 const eps=.006;
 for(const solid of solids){
  const edge=new T.EdgesGeometry(solid.source.geometry,30),a=new T.Vector3(),b=new T.Vector3(),pos=edge.attributes.position;
  for(let i=0;i<pos.count;i+=2){a.fromBufferAttribute(pos,i).applyMatrix4(solid.matrix);b.fromBufferAttribute(pos,i+1).applyMatrix4(solid.matrix);if(a.distanceTo(b)<.02)continue;
   const d=b.clone().sub(a).normalize(),axis=Math.abs(d.z)>.9?new T.Vector3(1,0,0):new T.Vector3(0,0,1),u=new T.Vector3().crossVectors(d,axis).normalize(),v=new T.Vector3().crossVectors(d,u).normalize();
   const nearby=solids.filter(s=>s.world.clone().expandByScalar(eps*2).intersectsBox(new T.Box3().setFromPoints([a,b])));
   const corner=t=>{const p=a.clone().lerp(b,t);let n=0;for(let k=0;k<8;k++){const theta=Math.PI/8+k*Math.PI/4,q=p.clone().addScaledVector(u,eps*Math.cos(theta)).addScaledVector(v,eps*Math.sin(theta));if(nearby.some(s=>s.inside(q)))n++;}return n>0&&n<8&&n!==4;};
   // Split at wall-piece extents so partial contacts do not leave seam fragments.
   const ts=[0,1];for(const s of nearby)for(const axis of ['x','y','z']){const delta=b[axis]-a[axis];if(Math.abs(delta)<1e-9)continue;for(const limit of [s.world.min[axis],s.world.max[axis]]){const t=(limit-a[axis])/delta;if(t>1e-6&&t<1-1e-6)ts.push(t);}}
   ts.sort((x,y)=>x-y);for(let j=1;j<ts.length;j++){const lo=ts[j-1],hi=ts[j];if((hi-lo)*a.distanceTo(b)<.01||!corner((lo+hi)/2))continue;
    const p=a.clone().lerp(b,lo),q=a.clone().lerp(b,hi);for(const [start,end] of outsideWallOpeningIntervals(p.toArray(),q.toArray(),cuts)){const x=p.clone().lerp(q,start).toArray(),y=p.clone().lerp(q,end).toArray(),key=[x,y].map(p=>p.map(n=>Math.round(n*1000)).join(',')).sort().join('|');if(seen.has(key))continue;seen.add(key);segments.push(...x,...y);}
   }
  }edge.dispose();
 }
 // Joining collinear fragments keeps large CAD floors to one inexpensive line batch.
 const lines=new Map();for(let i=0;i<segments.length;i+=6){const a=new T.Vector3(...segments.slice(i,i+3)),b=new T.Vector3(...segments.slice(i+3,i+6)),d=b.clone().sub(a).normalize();
  const first=[d.x,d.y,d.z].find(x=>Math.abs(x)>1e-6);if(first<0)d.negate();const anchor=a.clone().addScaledVector(d,-a.dot(d)),key=[...d.toArray().map(n=>Math.round(n*1e5)),...anchor.toArray().map(n=>Math.round(n*1e3))].join(',');
  if(!lines.has(key))lines.set(key,{d,anchor,spans:[]});const line=lines.get(key);line.spans.push([a.dot(line.d),b.dot(line.d)].sort((x,y)=>x-y));
 }
 const out=[];for(const {d,anchor,spans} of lines.values()){spans.sort((a,b)=>a[0]-b[0]);let [lo,hi]=spans[0];const push=()=>out.push(...anchor.clone().addScaledVector(d,lo).toArray(),...anchor.clone().addScaledVector(d,hi).toArray());for(const [a,b] of spans.slice(1)){if(a<=hi+1e-5)hi=Math.max(hi,b);else{push();lo=a;hi=b;}}push();}
 return out;
}
