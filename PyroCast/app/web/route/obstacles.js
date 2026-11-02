// Planar, axis-aligned obstacle footprints. Only rooms with explicit obstacles
// use this visibility graph; existing CAD routes without obstacles are untouched.
export function expandedObstacle(o){
 const [x,y]=o.center_m,[w,d]=o.size_m,c=o.clearance_m??.5;
 return {id:o.id,min:[x-w/2-c,y-d/2-c],max:[x+w/2+c,y+d/2+c]};
}
export function crossesObstacle(a,b,r){
 let lo=0,hi=1;
 for(let i=0;i<2;i++){
  const d=b[i]-a[i],min=r.min[i]+1e-8,max=r.max[i]-1e-8;
  if(Math.abs(d)<1e-12){if(a[i]<=min||a[i]>=max)return false;continue;}
  const u=(min-a[i])/d,v=(max-a[i])/d;lo=Math.max(lo,Math.min(u,v));hi=Math.min(hi,Math.max(u,v));
  if(lo>=hi)return false;
 }
 return hi>0&&lo<1;
}
export function avoidObstacles(a,b,obstacles,inside){
 if(!obstacles?.length)return [a,b];
 const boxes=obstacles.map(expandedObstacle),nodes=[a,b];
 for(const r of boxes)for(const x of [r.min[0]-.0001,r.max[0]+.0001])for(const y of [r.min[1]-.0001,r.max[1]+.0001]){
  const p=[x,y,a[2]];if(inside(p)&&!boxes.some(q=>crossesObstacle(p,p,q)))nodes.push(p);
 }
 const clear=(p,q)=>!boxes.some(r=>crossesObstacle(p,q,r))&&Array.from({length:19},(_,i)=>(i+1)/20).every(t=>inside(p.map((v,i)=>v+(q[i]-v)*t)));
 const costs=nodes.map(()=>Infinity),prev=[],done=new Set();costs[0]=0;
 while(done.size<nodes.length){let at=-1;for(let i=0;i<nodes.length;i++)if(!done.has(i)&&(at<0||costs[i]<costs[at]))at=i;
  if(at<0||!Number.isFinite(costs[at]))break;if(at===1){const path=[];for(let i=1;i!==undefined;i=prev[i])path.push(nodes[i]);return path.reverse();}
  done.add(at);for(let j=0;j<nodes.length;j++)if(!done.has(j)&&clear(nodes[at],nodes[j])){
   const cost=costs[at]+Math.hypot(...nodes[at].map((v,i)=>v-nodes[j][i]));if(cost<costs[j]){costs[j]=cost;prev[j]=at;}
  }
 }
 return null;
}
