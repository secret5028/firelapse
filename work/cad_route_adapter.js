// Keep the established within-floor pathfinder. Replace only its index-based
// floor matching with the CAD model's explicit stair links (including B1/PH).
const AutoRoute=window.AutoRoute;
AutoRoute.generate=function(pages,fire,start){
 const target=pages.find(p=>'CAD|'+p.floor===fire.levelKey),ground=pages.find(p=>p.floor===1);
 if(!target||!ground)return {error:'화점 층과 지상 1층 자료가 필요합니다.'};
 const nodes=[{id:'start',page:ground,point:start},{id:'target',page:target,point:fire.position}],edges=new Map();
 const key=p=>'CAD|'+p.floor;
 const add=(a,b,points)=>{const distance=points.slice(1).reduce((n,p,i)=>n+Math.hypot(...p.map((v,k)=>v-points[i][k])),0);if(!edges.has(a))edges.set(a,[]);edges.get(a).push({to:b,points,distance})};
 for(const link of B.vertical_connections.filter(l=>l.kind==='stair')){
  const f=B.floors.find(f=>f.name===link.from_floor),t=B.floors.find(f=>f.name===link.to_floor),core=f.transport.find(c=>c.id===link.from_core);
  if(!core?.meshes.length)continue;
  // Route through the same generated steps and landings seen in the 3D model.
  const centers=core.meshes.map(s=>{const ps=s.polys.flatMap(p=>p.o);return [ps.reduce((v,p)=>v+p[0],0)/ps.length,s.z1,ps.reduce((v,p)=>v+p[1],0)/ps.length]}).sort((a,b)=>a[1]-b[1]);
  const stairPoints=centers.map(p=>[p[0],f.z-groundZ+p[1],-p[2]]);
  const from=stairPoints[0].slice();from[1]=f.z-groundZ;
  const to=stairPoints.at(-1).slice();to[1]=t.z-groundZ;
  const a={id:link.from_floor+':'+link.from_core+':bottom',page:pages.find(p=>p.levelLabel===f.name),point:from},b={id:link.from_floor+':'+link.from_core+':top',page:pages.find(p=>p.levelLabel===t.name),point:to};
  nodes.push(a,b);add(a.id,b.id,[from,...stairPoints,to]);add(b.id,a.id,[to,...stairPoints.slice().reverse(),from]);
 }
 const costs=new Map([['start',0]]),previous=new Map(),pending=new Set(['start']),settled=new Set(),walkCache=new Map();
 while(pending.size){const current=[...pending].reduce((a,b)=>costs.get(a)<=costs.get(b)?a:b);pending.delete(current);if(current==='target')break;if(settled.has(current))continue;settled.add(current);const a=nodes.find(n=>n.id===current);
  for(const b of nodes){if(a.id===b.id||key(a.page)!==key(b.page)||settled.has(b.id))continue;
   const cacheKey=[a.id,b.id].sort().join('|');let cached=walkCache.get(cacheKey);
   if(!walkCache.has(cacheKey)){const leg=AutoRoute.walk(a.page,[a.point[0],a.point[2]],[b.point[0],b.point[2]],a.id==='start'||b.id==='start');cached=leg?{from:a.id,points:leg.map(p=>[p[0],a.page.elevation,p[1]])}:null;walkCache.set(cacheKey,cached)}
   if(cached)add(a.id,b.id,cached.from===a.id?cached.points:cached.points.slice().reverse());
  }
  for(const edge of edges.get(current)||[]){const cost=costs.get(current)+edge.distance;if(cost<(costs.get(edge.to)??Infinity)){costs.set(edge.to,cost);previous.set(edge.to,{from:current,edge});pending.add(edge.to)}}
 }
 if(!previous.has('target'))return {error:'문·공간·계단의 연결 경로를 찾지 못했습니다. 직접 경로를 지정할 수 있습니다.'};
 const legs=[];for(let id='target';id!=='start';){const p=previous.get(id);legs.unshift(p.edge.points);id=p.from}
 const points=[];for(const leg of legs)for(const p of leg)if(!points.length||Math.hypot(...p.map((v,k)=>v-points.at(-1)[k]))>.01)points.push(p);
 return {points,length:costs.get('target'),fireId:fire.id,automatic:true};
};
