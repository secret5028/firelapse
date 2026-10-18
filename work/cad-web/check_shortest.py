from pathlib import Path
s=Path('work/check_layers.mjs').read_text(encoding='utf-8')
s=s.replace("assert.equal(ctx.window.fireViewer.calcRoutes().length,1)", "assert.equal(ctx.window.fireViewer.calcRoutes().length,2)").replace("),'ffd343')", "),'ef4958')")
s+='''
const astar=ctx.pathfind.toString();vm.runInContext(astar.replace('function pathfind','function dijkstraReference').replace('dist[open[j]]+Math.hypot(q.x-goal.x,q.z-goal.z)','dist[open[j]]'),ctx);
const length=p=>p.reduce((s,b,i)=>i?s+Math.hypot(b.x-p[i-1].x,b.y-p[i-1].y,b.z-p[i-1].z):0,0);
for(const f of [1,2])for(const [a,b]of [[{x:1,z:10.5},{x:28,z:8.8}],[{x:29.7,z:14.5},{x:1,z:4.1}]]){
 const p=ctx.pathfind(a,b,f),q=ctx.dijkstraReference(a,b,f);assert(p&&q);assert(Math.abs(length(p)-length(q))<1e-7,'A* must match Dijkstra shortest distance');
}
for(const fire of [false,true])for(const t of [{x:17,z:7,f:2},{x:28,z:8.8,f:2},{x:17,z:7,f:1}]){
 const st=ctx.window.fireViewer.state;st.fire=fire;st.target=t;st.entrance='all';
 const rs=ctx.window.fireViewer.calcRoutes();assert.equal(rs.length,2);assert(rs[0].length<=rs[1].length);
 for(const r of rs){const all=ctx.candidatesForEntrance(r.entrance);assert.equal(r.length,Math.min(...all.map(p=>p.length)));assert(r.optimal);assert(r.points[0].external);for(let j=1;j<r.points.length;j++){const a=r.points[j-1],b=r.points[j];if(a.external||b.external||a.threshold||b.threshold)continue;if(a.f&&a.f===b.f)assert(ctx.segmentClear(a,b,a.f));else assert(a.f===0||b.f===0)}}
 st.entrance='east';const alternatives=ctx.window.fireViewer.calcRoutes();for(let i=1;i<alternatives.length;i++)assert(alternatives[i].length>=alternatives[i-1].length);
 console.log(fire?'fire':'door',JSON.stringify(t),rs.map(r=>r.entryName+' '+r.length.toFixed(1)+'m via '+r.via).join(' / '));
}
console.log('PASS A* vs Dijkstra; entrance-optimal candidate selection; sorted alternatives; valid internal paths and registered vertical links.');
'''
Path('work/check_shortest.mjs').write_text(s,encoding='utf-8')
