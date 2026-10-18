/* Geometry-based route proposals. Never fall back to a line through walls. */
(function(root){
const cache=new Map(),step=.3;
const key=p=>p.building+'|'+p.floor;
function xy(p,a){const o=p.origin||[0,0];return [(a[0]-o[0])*p.scale,(a[1]-o[1])*p.scale];}
function inside(q,poly){let c=false;for(let i=0,j=poly.length-1;i<poly.length;j=i++){const a=poly[i],b=poly[j];if((a[1]>q[1])!==(b[1]>q[1])&&q[0]<(b[0]-a[0])*(q[1]-a[1])/(b[1]-a[1])+a[0])c=!c;}return c;}
function distance(q,a,b){const dx=b[0]-a[0],dz=b[1]-a[1],t=Math.max(0,Math.min(1,((q[0]-a[0])*dx+(q[1]-a[1])*dz)/(dx*dx+dz*dz||1)));return Math.hypot(q[0]-a[0]-t*dx,q[1]-a[1]-t*dz);}
function plan(p){const hash=JSON.stringify([p.shapes,p.scale,p.origin,p.floorPolygons,p.floorOutline]);if(cache.has(hash))return cache.get(hash);const shapes=p.shapes.map(s=>({...s,a:xy(p,s.a),b:xy(p,s.b)}));const doors=shapes.filter(s=>s.type==='door'&&s.openingKind!=='elevator');const walls=[];
for(const w of shapes.filter(s=>s.type==='wall')){const dx=w.b[0]-w.a[0],dz=w.b[1]-w.a[1],len=Math.hypot(dx,dz);if(len<.001)continue;const cuts=[];for(const d of doors){const off=q=>Math.abs((q[0]-w.a[0])*dz-(q[1]-w.a[1])*dx)/len;if(off(d.a)<.4&&off(d.b)<.4){let ts=[d.a,d.b].map(q=>((q[0]-w.a[0])*dx+(q[1]-w.a[1])*dz)/(len*len)).sort((a,b)=>a-b);if(ts[1]>0&&ts[0]<1)cuts.push([Math.max(0,ts[0]),Math.min(1,ts[1])]);}}cuts.sort((a,b)=>a[0]-b[0]);let from=0;const at=t=>[w.a[0]+dx*t,w.a[1]+dz*t];for(const [lo,hi]of cuts){if(lo>from)walls.push([at(from),at(lo)]);from=Math.max(from,hi);}if(from<1)walls.push([at(from),w.b]);}
const polys=(p.floorPolygons||[p.floorOutline]).filter(Boolean).map(poly=>poly.map(q=>xy(p,q)));const pts=shapes.flatMap(s=>[s.a,s.b]);const model={shapes,doors,walls,polys,bounds:[Math.min(...pts.map(q=>q[0])),Math.min(...pts.map(q=>q[1])),Math.max(...pts.map(q=>q[0])),Math.max(...pts.map(q=>q[1]))]};cache.set(hash,model);if(cache.size>32)cache.delete(cache.keys().next().value);return model;}
class Heap{constructor(){this.a=[];}push(v){let i=this.a.length;this.a.push(v);while(i){let p=(i-1)>>1;if(this.a[p][0]<=v[0])break;this.a[i]=this.a[p];i=p;}this.a[i]=v;}pop(){const r=this.a[0],v=this.a.pop();if(this.a.length){let i=0;while(i*2+1<this.a.length){let c=i*2+1;if(c+1<this.a.length&&this.a[c+1][0]<this.a[c][0])c++;if(this.a[c][0]>=v[0])break;this.a[i]=this.a[c];i=c;}this.a[i]=v;}return r;}}
function walk(p,start,end,outdoor=false){const m=plan(p),b=m.bounds,x0=Math.min(b[0],start[0],end[0])-3,z0=Math.min(b[1],start[1],end[1])-3,nx=Math.ceil((Math.max(b[2],start[0],end[0])+3-x0)/step),nz=Math.ceil((Math.max(b[3],start[1],end[1])+3-z0)/step);if(nx*nz>350000)return null;const N=nx*nz,blocked=new Uint8Array(N);const coord=i=>[x0+(i%nx)*step,z0+Math.floor(i/nx)*step];
// Rasterize walls locally, keeping source door cuts traversable.
if(!outdoor&&m.polys.length)for(let i=0;i<N;i++)if(!m.polys.some(poly=>inside(coord(i),poly)))blocked[i]=1;
for(const [a,b]of m.walls){const loX=Math.max(0,Math.floor((Math.min(a[0],b[0])-.2-x0)/step)),hiX=Math.min(nx-1,Math.ceil((Math.max(a[0],b[0])+.2-x0)/step)),loZ=Math.max(0,Math.floor((Math.min(a[1],b[1])-.2-z0)/step)),hiZ=Math.min(nz-1,Math.ceil((Math.max(a[1],b[1])+.2-z0)/step));for(let z=loZ;z<=hiZ;z++)for(let x=loX;x<=hiX;x++){const i=z*nx+x;if(distance(coord(i),a,b)<.2)blocked[i]=1;}}
for(const d of m.doors){const loX=Math.max(0,Math.floor((Math.min(d.a[0],d.b[0])-.6-x0)/step)),hiX=Math.min(nx-1,Math.ceil((Math.max(d.a[0],d.b[0])+.6-x0)/step)),loZ=Math.max(0,Math.floor((Math.min(d.a[1],d.b[1])-.6-z0)/step)),hiZ=Math.min(nz-1,Math.ceil((Math.max(d.a[1],d.b[1])+.6-z0)/step));for(let z=loZ;z<=hiZ;z++)for(let x=loX;x<=hiX;x++){const i=z*nx+x;if(distance(coord(i),d.a,d.b)<.45)blocked[i]=0;}}
function nearest(q){let best=-1,d=.7;const cx=Math.round((q[0]-x0)/step),cz=Math.round((q[1]-z0)/step);for(let z=cz-2;z<=cz+2;z++)for(let x=cx-2;x<=cx+2;x++){if(x<0||z<0||x>=nx||z>=nz)continue;let i=z*nx+x,dd=Math.hypot(...coord(i).map((v,k)=>v-q[k]));if(!blocked[i]&&dd<d){best=i;d=dd;}}return best;}
const s=nearest(start),t=nearest(end);if(s<0||t<0)return null;const scores=new Float64Array(N).fill(Infinity),prev=new Int32Array(N).fill(-1),heap=new Heap();scores[s]=0;heap.push([0,s]);while(heap.a.length){const [_,i]=heap.pop();if(i===t)break;const x=i%nx,z=Math.floor(i/nx);for(const [dx,dz]of [[1,0],[-1,0],[0,1],[0,-1]]){if(x+dx<0||x+dx>=nx||z+dz<0||z+dz>=nz)continue;const j=i+dx+dz*nx;if(blocked[j])continue;const cost=scores[i]+step;if(cost<scores[j]){scores[j]=cost;prev[j]=i;heap.push([cost+Math.hypot(...coord(j).map((v,k)=>v-coord(t)[k])),j]);}}}
if(!Number.isFinite(scores[t]))return null;const ids=[];for(let i=t;i!==-1;i=prev[i])ids.push(i);ids.reverse();const raw=ids.map(coord);const points=[start,...raw,end];const clean=[];for(const q of points){if(clean.length>1){const a=clean.at(-2),b=clean.at(-1);if(Math.abs((b[0]-a[0])*(q[1]-b[1])-(b[1]-a[1])*(q[0]-b[0]))<1e-7)clean.pop();}clean.push(q);}return clean;}
function stair(p,s){const q=s.corners?.map(a=>xy(p,a))||[xy(p,s.a),[xy(p,s.b)[0],xy(p,s.a)[1]],xy(p,s.b),[xy(p,s.a)[0],xy(p,s.b)[1]]],o=q[0],u=[q[1][0]-o[0],q[1][1]-o[1]],v=[q[3][0]-o[0],q[3][1]-o[1]],w=Math.hypot(...u),l=Math.hypot(...v),base=p.elevation??(p.floor-1)*p.height,at=(x,z,h)=>[o[0]+u[0]*x/w+v[0]*z/l,base+h,o[1]+u[1]*x/w+v[1]*z/l];const land=Math.min(w*.5,1.3);const center=[(q[0][0]+q[2][0])/2,(q[0][1]+q[2][1])/2];const doors=plan(p).doors.map(d=>({d,pt:[(d.a[0]+d.b[0])/2,(d.a[1]+d.b[1])/2]})).sort((a,b)=>Math.hypot(a.pt[0]-center[0],a.pt[1]-center[1])-Math.hypot(b.pt[0]-center[0],b.pt[1]-center[1]));const door=doors[0];return {door:door?.pt,shape:door?.d,points:[at(w*.24,l,0),at(w*.24,land/2,p.height/2),at(w*.76,land/2,p.height/2),at(w*.76,l+.25,p.height)],center};}

function generate(pages,fire,start){
 const target=pages.find(p=>key(p)===fire.levelKey)||pages.find(p=>p.floor===fire.floor);
 if(!target)return {error:'화점 층 정보가 없습니다.'};
 const levels=pages.filter(p=>p.included&&p.building===target.building&&p.floor>=1&&p.floor<=target.floor).sort((a,b)=>a.floor-b.floor);
 if(levels.length!==target.floor)return {error:'지상부터 화점까지 연결할 층 자료가 부족합니다.'};
 let best=null;
 for(let idx=0;idx<Math.max(1,(target.stairs||[]).length);idx++){
  let points=[start.slice()],contexts=[],valid=true;
  const push=ps=>{for(const q of ps)if(Math.hypot(...q.map((v,k)=>v-points.at(-1)[k]))>.01)points.push(q);};
  for(let j=0;j<levels.length;j++){
   const p=levels[j],y=p.elevation??(p.floor-1)*p.height,last=points.at(-1),from=[last[0],last[2]];
   const st=p.stairs?.[idx],s=st&&stair(p,st),terminal=p.floor===target.floor;
   if(!terminal&&!s){valid=false;break;}
   const end=terminal?[fire.position[0],fire.position[2]]:[s.points[0][0],s.points[0][2]];
   const leg=walk(p,from,end,j===0);
   if(!leg){valid=false;break;}
   push(leg.map(q=>[q[0],y,q[1]]));contexts.push({levelKey:key(p),stairIndex:terminal?null:idx,leg});
   if(!terminal)push(s.points);
  }
  if(valid){const length=points.slice(1).reduce((sum,q,i)=>sum+Math.hypot(...q.map((v,k)=>v-points[i][k])),0);if(!best||length<best.length)best={points,contexts,length,fireId:fire.id,automatic:true};}
 }
 return best||{error:'문·복도·계단의 연결이 끊겨 자동 경로를 생성하지 못했습니다. 도면과 모델의 개구부 연결 확인이 필요합니다.'};
}
// Select whole connected rooms along the route with door thresholds closed.
const contextCache=new Map();
function context(p,leg,stairIndex){
 const hash=JSON.stringify([p.shapes,p.scale,p.origin,leg,stairIndex]);if(contextCache.has(hash))return contextCache.get(hash);
 const m=plan(p),h=.4,b=m.bounds,x0=b[0]-1,z0=b[1]-1,nx=Math.ceil((b[2]-x0+1)/h),nz=Math.ceil((b[3]-z0+1)/h),N=nx*nz;
 if(N>120000)return {walls:[],doors:[],tiles:[],stairs:[]};
 const block=new Uint8Array(N),seen=new Uint8Array(N),at=i=>[x0+(i%nx)*h,z0+Math.floor(i/nx)*h];
 const barriers=m.walls.concat(m.doors.map(d=>[d.a,d.b]));
 for(let i=0;i<N;i++)if(m.polys.length&&!m.polys.some(poly=>inside(at(i),poly)))block[i]=1;
 for(const [a,b]of barriers){for(let z=Math.max(0,Math.floor((Math.min(a[1],b[1])-.3-z0)/h));z<=Math.min(nz-1,Math.ceil((Math.max(a[1],b[1])+.3-z0)/h));z++)for(let x=Math.max(0,Math.floor((Math.min(a[0],b[0])-.3-x0)/h));x<=Math.min(nx-1,Math.ceil((Math.max(a[0],b[0])+.3-x0)/h));x++){const i=z*nx+x;if(distance(at(i),a,b)<.3)block[i]=1;}}
 const queue=[];function seed(q){const x=Math.round((q[0]-x0)/h),z=Math.round((q[1]-z0)/h);if(x<0||z<0||x>=nx||z>=nz)return;const i=z*nx+x;if(!block[i]&&!seen[i]){seen[i]=1;queue.push(i);}}
 for(let j=0;j<leg.length;j++){const a=leg[j],b=leg[j+1]||a,n=Math.max(1,Math.ceil(Math.hypot(b[0]-a[0],b[1]-a[1])/h));for(let k=0;k<=n;k++)seed([a[0]+(b[0]-a[0])*k/n,a[1]+(b[1]-a[1])*k/n]);}
 if(stairIndex!=null){const st=stair(p,p.stairs[stairIndex]);seed(st.center);}
 for(let head=0;head<queue.length;head++){const i=queue[head],x=i%nx,z=Math.floor(i/nx);for(const [dx,dz]of [[1,0],[-1,0],[0,1],[0,-1]]){if(x+dx<0||z+dz<0||x+dx>=nx||z+dz>=nz)continue;const j=i+dx+dz*nx;if(!block[j]&&!seen[j]){seen[j]=1;queue.push(j);}}}
 function adjacent(a,b){const n=Math.ceil(Math.hypot(b[0]-a[0],b[1]-a[1])/h);for(let k=0;k<=n;k++){const x=Math.round((a[0]+(b[0]-a[0])*k/(n||1)-x0)/h),z=Math.round((a[1]+(b[1]-a[1])*k/(n||1)-z0)/h);for(let dz=-2;dz<=2;dz++)for(let dx=-2;dx<=2;dx++)if(x+dx>=0&&x+dx<nx&&z+dz>=0&&z+dz<nz&&seen[(z+dz)*nx+x+dx])return true;}return false;}
 const tiles=[];for(let z=0;z<nz;z++){let x=0;while(x<nx){if(!seen[z*nx+x]){x++;continue;}let end=x+1;while(end<nx&&seen[z*nx+end])end++;tiles.push([x0+x*h-h/2,z0+z*h-h/2,(end-x)*h,h]);x=end;}}
 const result={walls:m.walls.filter(([a,b])=>adjacent(a,b)),doors:m.doors.filter(d=>adjacent(d.a,d.b)),tiles,stairs:stairIndex==null?[]:[stairIndex]};
 contextCache.set(hash,result);if(contextCache.size>30)contextCache.delete(contextCache.keys().next().value);return result;
}
root.AutoRoute={generate,walk,plan,stair,xy,context};if(typeof module!=='undefined')module.exports=root.AutoRoute;
})(typeof window==='undefined'?globalThis:window);
