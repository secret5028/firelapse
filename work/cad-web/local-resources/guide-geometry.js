(function(root){
 const distance=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1]);
 function simplify(points,tolerance=1.2){
  if(points.length<3)return points.map(p=>p.slice());
  const a=points[0],b=points.at(-1),dx=b[0]-a[0],dy=b[1]-a[1],den=dx*dx+dy*dy;let at=0,max=0;
  for(let i=1;i<points.length-1;i++){const p=points[i],t=den?Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/den)):0,d=distance(p,[a[0]+t*dx,a[1]+t*dy]);if(d>max){max=d;at=i;}}
  return max>tolerance?[...simplify(points.slice(0,at+1),tolerance).slice(0,-1),...simplify(points.slice(at),tolerance)]:[a.slice(),b.slice()];
 }
 function snapInk(p,raster,radius=8){
  if(!raster)return p.slice();const {data,width,height}=raster;let best=p.slice(),score=Infinity;
  for(let y=Math.max(0,Math.floor(p[1]-radius));y<=Math.min(height-1,p[1]+radius);y++)for(let x=Math.max(0,Math.floor(p[0]-radius));x<=Math.min(width-1,p[0]+radius);x++){
   const d=Math.hypot(x-p[0],y-p[1]);if(d>radius)continue;const k=4*(y*width+x),gray=(data[k]+data[k+1]+data[k+2])/3;if(gray>165)continue;
   const cost=d+gray/255*2;if(cost<score){score=cost;best=[x,y];}
  }return best;
 }
 function straight(a,b,raster,radius=8){
  const len=distance(a,b);if(len<2||!raster)return[a,b];const n=Math.min(120,Math.max(8,Math.ceil(len/5))),samples=[];
  for(let i=0;i<=n;i++){const p=[a[0]+(b[0]-a[0])*i/n,a[1]+(b[1]-a[1])*i/n],q=snapInk(p,raster,radius);const x=Math.round(q[0]),y=Math.round(q[1]);if(x<0||y<0||x>=raster.width||y>=raster.height)continue;const k=4*(y*raster.width+x);if((raster.data[k]+raster.data[k+1]+raster.data[k+2])/3<165)samples.push(q);}
  if(samples.length<(n+1)*.65)return[a,b];
  const mean=[0,0];samples.forEach(p=>{mean[0]+=p[0]/samples.length;mean[1]+=p[1]/samples.length;});let xx=0,xy=0,yy=0;samples.forEach(p=>{const x=p[0]-mean[0],y=p[1]-mean[1];xx+=x*x;xy+=x*y;yy+=y*y;});
  let angle=.5*Math.atan2(2*xy,xx-yy),u=[Math.cos(angle),Math.sin(angle)],dir=[(b[0]-a[0])/len,(b[1]-a[1])/len];
  if(Math.abs(u[0]*dir[0]+u[1]*dir[1])<Math.cos(Math.PI/18))return[a,b];
  const residual=samples.map(p=>Math.abs((p[0]-mean[0])*u[1]-(p[1]-mean[1])*u[0])).sort((x,y)=>x-y);if(residual[Math.floor(residual.length*.8)]>2.5)return[a,b];
  return[a,b].map(p=>{const t=(p[0]-mean[0])*u[0]+(p[1]-mean[1])*u[1];return[mean[0]+t*u[0],mean[1]+t*u[1]];});
 }
 const points=s=>s.path?.length>1?s.path:[s.a,s.b];
 const expand=shapes=>shapes.flatMap(s=>{const p=points(s);return p.slice(1).map((b,i)=>{const out={...s,a:p[i],b};delete out.path;if(p.length>2){out.parentId=s.id;out.id=(s.id||'curve')+':'+i;}return out;});});
 root.GuideGeometry={distance,simplify,snapInk,straight,points,expand};if(typeof module!=='undefined')module.exports=root.GuideGeometry;
})(globalThis);
