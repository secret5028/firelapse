// Visibility graph outside the recorded ground footprint; no invented doors.
const cross=(a,b)=>a[0]*b[1]-a[1]*b[0];
const sub=(a,b)=>[a[0]-b[0],a[1]-b[1]];
const distance=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1]);
const nearest=(p,a,b)=>{const d=sub(b,a),t=Math.max(0,Math.min(1,((p[0]-a[0])*d[0]+(p[1]-a[1])*d[1])/(d[0]*d[0]+d[1]*d[1]||1)));return [a[0]+t*d[0],a[1]+t*d[1],p[2]];};
export function exteriorPath(vehicle,entry,polys,contains){
 const rings=polys.flatMap(p=>[p.o,...(p.h||[])]),edges=rings.flatMap(r=>r.map((a,i)=>[a,r[(i+1)%r.length]]));
 let boundary=null,best=Infinity;for(const [a,b] of edges){const p=nearest(entry,a,b),d=distance(p,entry);if(d<best){best=d;boundary=p;}}
 if(!boundary)return null;
 const onBoundary=p=>edges.some(([a,b])=>distance(p,nearest(p,a,b))<1e-6);
 const inside=p=>contains(p,polys)&&!onBoundary(p);
 const clear=(a,b)=>{
  const d=sub(b,a),times=[0,1];for(const [c,e] of edges){const v=sub(e,c),den=cross(d,v);if(Math.abs(den)<1e-10)continue;const u=sub(c,a),t=cross(u,v)/den,w=cross(u,d)/den;if(t>0&&t<1&&w>=0&&w<=1)times.push(t);}
  times.sort((a,b)=>a-b);for(let i=1;i<times.length;i++){const t=(times[i-1]+times[i])/2;if(inside([a[0]+d[0]*t,a[1]+d[1]*t]))return false;}return true;
 };
 if(clear(vehicle,boundary))return [vehicle,boundary,entry];
 const nodes=[vehicle,boundary];for(const ring of rings)for(let i=0;i<ring.length;i++){const p=ring[i],a=ring[(i+ring.length-1)%ring.length],b=ring[(i+1)%ring.length];if(Math.abs(cross(sub(p,a),sub(b,p)))>1e-6)nodes.push([...p,vehicle[2]]);}
 const costs=nodes.map(()=>Infinity),previous=[],done=new Set();costs[0]=0;
 while(done.size<nodes.length){let at=-1;for(let i=0;i<nodes.length;i++)if(!done.has(i)&&(at<0||costs[i]<costs[at]))at=i;if(at<0||!Number.isFinite(costs[at]))break;
  if(at===1){const path=[];for(let i=1;i!==undefined;i=previous[i])path.push(nodes[i]);return [...path.reverse(),entry];}
  done.add(at);for(let j=0;j<nodes.length;j++)if(!done.has(j)){const next=costs[at]+distance(nodes[at],nodes[j]);if(next<costs[j]&&clear(nodes[at],nodes[j])){costs[j]=next;previous[j]=at;}}
 }return null;
}
