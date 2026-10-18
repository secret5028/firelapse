from pathlib import Path
s=Path('work/check_factory.mjs').read_text(encoding='utf-8-sig').split('assert(v.ready)')[0]
s=s.replace("FACTORY:JSON.parse(fs.readFileSync('work/factory-data.json','utf8')),FACTORY_ASSETS:{}","INDUSTRIAL:JSON.parse(fs.readFileSync('work/industrial-data.json','utf8')),INDUSTRIAL_ASSETS:{}").replace("'work/factory.js'","'work/industrial.js'").replace('ctx.window.factoryViewer','ctx.window.industrialViewer')
s+='''
assert(v.ready);assert.equal(v.equipmentMeshes.filter(o=>o.userData.equipment.type==='hydrant').length,8);
for(const f of ['1','2','3']){v.setFloor(f);for(const n of [1,2,3])assert.equal(v.groups[n].visible,String(n)===f)}
assert(!v.passable(2,50,16));assert(!v.passable(3,50,16));assert(!v.passable(1,30,6));
let count=0,missing=[];
for(const f of [1,2,3])for(const r of v.D.floors[f-1].rooms.filter(r=>r.entry)){
 const rs=v.computeRoutes(f,r.entry);if(rs.length!==10)missing.push([f,r.name,rs.length]);
 for(const route of rs){count++;assert.deepEqual([...route.path.at(-1)],[r.entry[0],v.D.floors[f-1].y+.15,r.entry[1]]);for(let i=1;i<route.path.length;i++){const a=route.path[i-1],b=route.path[i];if(Math.abs(a[1]-b[1])>.001)for(const p of [a,b])assert(p[2]>=.4&&p[2]<=3.5&&(p[0]<=5||p[0]>=93));} }
}
v.restore(true);const c=v.state.target.clone().project(v.camera),n=v.state.target.clone().add(new RealThree.Vector3(1,0,0)).project(v.camera);assert(n.y>c.y);assert(Math.abs(n.x-c.x)<1e-8);
v.showSystem('H');assert(v.coverage.children.length>0);console.log(JSON.stringify({checkedRoutes:count,missing,pass:'floor isolation, 8 hydrants, void and obstacle blocking, vertical motion only at stairs, route door endpoints, north-up'},null,2));assert.equal(missing.length,0);
'''
Path('work/check_industrial.mjs').write_text(s,encoding='utf-8')
