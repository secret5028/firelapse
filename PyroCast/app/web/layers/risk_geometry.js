// Legacy display geometry only; no condition or simulation calculations.
export function boundarySegments(room,original){
  // Smoke/risk outlines use exterior rings only; column/stair holes are not boxes.
  const edges=polys=>polys.flatMap(p=>p.o.map((a,i)=>[a,p.o[(i+1)%p.o.length]]).filter(([a,b])=>Math.hypot(b[0]-a[0],b[1]-a[1])>1e-7));
  const cellEdges=edges(room.cad_polys);if(!original)return cellEdges.map(([a,b])=>({a,b}));
  const outerEdges=edges(original.polys),segments=[];
  // Keep only overlap with the original CAD perimeter. Virtual cell cuts,
  // including their vertical uprights, are never drawn as room boundaries.
  for(const [a,b] of cellEdges){
   const dx=b[0]-a[0],dy=b[1]-a[1],len=Math.hypot(dx,dy),ux=dx/len,uy=dy/len;
   for(const [c,d] of outerEdges){
    if(Math.abs((c[0]-a[0])*uy-(c[1]-a[1])*ux)>.002||Math.abs((d[0]-a[0])*uy-(d[1]-a[1])*ux)>.002)continue;
    const tc=(c[0]-a[0])*ux+(c[1]-a[1])*uy,td=(d[0]-a[0])*ux+(d[1]-a[1])*uy;
    const lo=Math.max(0,Math.min(tc,td)),hi=Math.min(len,Math.max(tc,td));if(hi-lo<1e-6)continue;
    const q=[a[0]+lo*ux,a[1]+lo*uy],r=[a[0]+hi*ux,a[1]+hi*uy];
    segments.push({a:q,b:r});
   }
  }
  return segments;
 }
export function joinedSelectionRibbons(polygon,inset=.24,halfWidth=.035){
 const inRing=(p,ring)=>{let inside=false;for(let i=0,j=ring.length-1;i<ring.length;j=i++){
  const a=ring[i],b=ring[j];if((a[1]>p[1])!==(b[1]>p[1])&&p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0])inside=!inside;
 }return inside;};
 const inside=p=>inRing(p,polygon.o)&&!(polygon.h||[]).some(h=>inRing(p,h));
 const result=[];
 for(const [ri,raw] of [polygon.o,...(polygon.h||[])].entries()){
  const ring=raw.filter((p,i)=>!i||Math.hypot(p[0]-raw[i-1][0],p[1]-raw[i-1][1])>1e-7);
  if(ring.length>1&&Math.hypot(ring[0][0]-ring.at(-1)[0],ring[0][1]-ring.at(-1)[1])<1e-7)ring.pop();
  if(ring.length<3)continue;
  let area=0;for(let i=0;i<ring.length;i++){const a=ring[i],b=ring[(i+1)%ring.length];area+=a[0]*b[1]-b[0]*a[1];}
  const sign=(area>=0?1:-1)*(ri===0?1:-1);
  const normals=ring.map((a,i)=>{const b=ring[(i+1)%ring.length],len=Math.hypot(b[0]-a[0],b[1]-a[1]);return [-(b[1]-a[1])/len*sign,(b[0]-a[0])/len*sign];});
  const joins=ring.map((p,i)=>{const a=normals[(i+ring.length-1)%ring.length],b=normals[i],den=1+a[0]*b[0]+a[1]*b[1];
   let x=den>1e-6?(a[0]+b[0])/den:b[0],y=den>1e-6?(a[1]+b[1])/den:b[1];
   const length=Math.hypot(x,y);if(length>4){x*=4/length;y*=4/length;}return [x,y];
  });
  const offset=d=>ring.map((p,i)=>[p[0]+joins[i][0]*d,p[1]+joins[i][1]*d]);
  const fits=loop=>loop.every((a,i)=>{const b=loop[(i+1)%loop.length],n=Math.max(1,Math.ceil(Math.hypot(b[0]-a[0],b[1]-a[1])/.1));
   for(let j=0;j<=n;j++)if(!inside([a[0]+(b[0]-a[0])*j/n,a[1]+(b[1]-a[1])*j/n]))return false;return true;
  });
  for(let attempt=0;attempt<16;attempt++){
   const scale=2**(-attempt/2),outer=offset((inset-halfWidth)*scale),inner=offset((inset+halfWidth)*scale);
   if(fits(outer)&&fits(inner)){result.push({outer,inner,inset:inset*scale});break;}
  }
 }
 return result;
}

// Cut the existing ribbon into fixed-length dashes; no shader or line-width change.
export function dashedRibbonVertices(ribbons,dash=.4,gap=.2){
 const vertices=[],period=dash+gap;
 if(!(dash>0&&gap>0))throw Error('Positive dash and gap required');
 for(const {outer,inner} of ribbons){let distance=0;
  for(let i=0;i<outer.length;i++){
   const j=(i+1)%outer.length,a=outer[i],b=outer[j],c=inner[i],d=inner[j];
   const length=Math.hypot((b[0]+d[0]-a[0]-c[0])/2,(b[1]+d[1]-a[1]-c[1])/2);
   if(length<1e-8)continue;
   const point=(p,q,t)=>[p[0]+(q[0]-p[0])*t,p[1]+(q[1]-p[1])*t];
   for(let k=Math.floor(distance/period);k*period<distance+length;k++){
    const lo=Math.max(distance,k*period),hi=Math.min(distance+length,k*period+dash);
    if(hi<=lo)continue;
    const u=(lo-distance)/length,v=(hi-distance)/length;
    const quad=[point(a,b,u),point(a,b,v),point(c,d,v),point(c,d,u)];
    for(const index of [0,1,2,0,2,3])vertices.push(...quad[index],0);
   }
   distance+=length;
  }
 }
 return vertices;
}
