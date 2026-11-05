// Display/routing geometry only. Room graph, fire inputs and stair costs stay intact.
import {expandedObstacle,crossesObstacle} from './obstacles.js';
const distance=(a,b)=>Math.hypot(...a.map((v,i)=>v-b[i]));
const caches=new WeakMap();
function boundaryDistance(p,polys){let best=Infinity;for(const q of polys)for(const ring of [q.o,...(q.h||[])])for(let i=0;i<ring.length;i++){const a=ring[i],b=ring[(i+1)%ring.length],dx=b[0]-a[0],dy=b[1]-a[1],d=dx*dx+dy*dy,t=d?Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/d)):0;best=Math.min(best,Math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy));}return best;}
function navigation(room,contains){
 if(caches.has(room))return caches.get(room);
 const points=room.polys.flatMap(p=>p.o),xs=points.map(p=>p[0]),ys=points.map(p=>p[1]),x0=Math.min(...xs),y0=Math.min(...ys),w=Math.max(...xs)-x0,h=Math.max(...ys)-y0;
 const step=Math.max(.25,Math.sqrt(w*h/12000)),nx=Math.ceil(w/step),ny=Math.ceil(h/step),boxes=(room.obstacles||[]).map(expandedObstacle),nodes=[],byKey=new Map();
 const inside=p=>contains(p,room.polys)&&!boxes.some(b=>crossesObstacle(p,p,b));
 const clear=(a,b,portal=false)=>{if(boxes.some(r=>crossesObstacle(a,b,r)))return false;const n=Math.max(2,Math.ceil(distance(a,b)/.08));for(let i=0;i<=n;i++){const t=i/n,p=a.map((v,k)=>v+(b[k]-v)*t);if(!inside(p)&&!(portal&&(distance(p,a)<.5||distance(p,b)<.5)))return false;}return true;};
 for(let y=0;y<ny;y++)for(let x=0;x<nx;x++){const p=[x0+(x+.5)*w/nx,y0+(y+.5)*h/ny,room.point[2]];if(!inside(p))continue;const clearance=Math.min(boundaryDistance(p,room.polys),...boxes.map(b=>Math.hypot(Math.max(b.min[0]-p[0],0,p[0]-b.max[0]),Math.max(b.min[1]-p[1],0,p[1]-b.max[1]))));const node={p,x,y,index:nodes.length,clearance};nodes.push(node);byKey.set(x+','+y,node);}
 const clearance=p=>Math.min(boundaryDistance(p,room.polys),...boxes.map(b=>Math.hypot(Math.max(b.min[0]-p[0],0,p[0]-b.max[0]),Math.max(b.min[1]-p[1],0,p[1]-b.max[1]))));
 const nav={nodes,byKey,inside,clear,clearance,paths:new Map()};caches.set(room,nav);return nav;
}
function gridPath(nav,a,b){
 const key=JSON.stringify([a,b]);if(nav.paths.has(key))return nav.paths.get(key);
 const closest=p=>nav.nodes.filter(n=>distance(n.p,p)<1.5&&nav.clear(p,n.p,true)).sort((x,y)=>(y.clearance-.2*distance(y.p,p))-(x.clearance-.2*distance(x.p,p)))[0];
 const start=closest(a),end=closest(b);if(!start||!end)return null;
 const cost=new Float64Array(nav.nodes.length).fill(Infinity),prev=new Int32Array(nav.nodes.length).fill(-1),heap=[];cost[start.index]=0;
 const push=row=>{heap.push(row);let i=heap.length-1;while(i){const p=(i-1)>>1;if(heap[p][0]<=row[0])break;heap[i]=heap[p];i=p;}heap[i]=row;};
 const pop=()=>{const first=heap[0],last=heap.pop();if(heap.length){let i=0;while(i*2+1<heap.length){let j=i*2+1;if(j+1<heap.length&&heap[j+1][0]<heap[j][0])j++;if(heap[j][0]>=last[0])break;heap[i]=heap[j];i=j;}heap[i]=last;}return first;};
 push([0,start.index]);while(heap.length){const [c,i]=pop();if(c!==cost[i])continue;if(i===end.index)break;const n=nav.nodes[i];for(const [dx,dy] of [[1,0],[-1,0],[0,1],[0,-1]]){const q=nav.byKey.get((n.x+dx)+','+(n.y+dy));if(!q||!nav.clear(n.p,q.p))continue;
  const next=c+distance(n.p,q.p)*(1+3/Math.max(.12,Math.min(n.clearance,q.clearance)));if(next<cost[q.index]){cost[q.index]=next;prev[q.index]=i;push([next,q.index]);}
 }}
 if(!Number.isFinite(cost[end.index]))return null;const path=[];for(let i=end.index;i>=0;i=prev[i])path.push(nav.nodes[i].p);path.reverse();path.unshift(a);path.push(b);
 const compact=[];for(const p of path){if(compact.length&&distance(compact.at(-1),p)<1e-7)continue;while(compact.length>1){const u=compact.at(-2),v=compact.at(-1);if(Math.abs(distance(u,v)+distance(v,p)-distance(u,p))>1e-6)break;compact.pop();}compact.push(p);}
 // Remove grid stair-steps only where the shortcut retains wall clearance.
 const smooth=compact.slice(0,2);let at=1;while(at<compact.length-2){let next=at+1;for(let j=compact.length-2;j>at+1;j--){const p=compact[at],q=compact[j],required=Math.min(.6,nav.clearance(p),nav.clearance(q))*.8;
  if(nav.clear(p,q,at===0||j===compact.length-1)&&Array.from({length:19},(_,i)=>(i+1)/20).every(t=>nav.clearance(p.map((v,k)=>v+(q[k]-v)*t))>=required)){next=j;break;}}
  smooth.push(compact[next]);at=next;
 }
 if(smooth.at(-1)!==compact.at(-1))smooth.push(compact.at(-1));nav.paths.set(key,smooth);return smooth;
}
export function roundedPath(points,clear){
 if(points.length<3)return points;const out=[points[0]];
 for(let i=1;i<points.length-1;i++){const a=points[i-1],b=points[i],c=points[i+1],ab=distance(a,b),bc=distance(b,c);if(ab<1e-8||bc<1e-8)continue;
  let radius=Math.min(.8,ab*.4,bc*.4),curve=null;
  for(let attempt=0;attempt<5;attempt++,radius*=.5){const p=b.map((v,k)=>v+(a[k]-v)*radius/ab),q=b.map((v,k)=>v+(c[k]-v)*radius/bc),samples=Array.from({length:9},(_,j)=>{const t=j/8;return b.map((v,k)=>(1-t)**2*p[k]+2*(1-t)*t*v+t*t*q[k]);});if(samples.slice(1).every((p,j)=>clear(samples[j],p))){curve=samples;break;}}
  if(curve)out.push(...curve);else out.push(b);
 }out.push(points.at(-1));return out;
}
export function centerRoomSegments(parts,rooms,contains){
 const result=[],warnings=[];for(let i=0;i<parts.length;){const first=parts[i];if(first.stair||!first.room){result.push(first);i++;continue;}let j=i+1;while(j<parts.length&&!parts[j].stair&&parts[j].room===first.room&&parts[j].floor===first.floor&&distance(parts[j-1].b,parts[j].a)<1e-6)j++;
  const original=parts.slice(i,j),room=rooms.get(first.room),nav=navigation(room,contains),a=first.a,b=original.at(-1).b;
  let path;if(room.corridor)path=gridPath(nav,a,b);else{const center=nav.inside(room.point)?room.point:nav.nodes.slice().sort((x,y)=>distance(x.p,room.point)-distance(y.p,room.point))[0]?.p;
   if(center){const left=nav.clear(a,center,true)?[a,center]:gridPath(nav,a,center),right=nav.clear(center,b,true)?[center,b]:gridPath(nav,center,b);if(left&&right)path=[...left,...right.slice(1)];}}
  if(!path){warnings.push(room.id);result.push(...original);i=j;continue;}
  path=roundedPath(path,(a,b)=>nav.clear(a,b));for(let k=1;k<path.length;k++){const length=distance(path[k-1],path[k]);if(length>1e-7)result.push({...first,a:path[k-1],b:path[k],length});}i=j;
 }return {segments:result,warnings};
}
