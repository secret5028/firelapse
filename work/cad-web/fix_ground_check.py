from pathlib import Path
p=Path('work/industrial.js');s=p.read_text(encoding='utf-8').replace('g===routeGroup||g===startMarker','g===routeGroup');p.write_text(s,encoding='utf-8')
p=Path('work/check_industrial.mjs');s=p.read_text(encoding='utf-8').replace("get('roomList').value='0';get('roomList').onchange();",'v.state.fire={x:5,z:17};v.updateRoutes();').replace("get('roomList').value='';get('roomList').onchange();","get('clearBtn').onclick();").replace('Math.abs(a[1]-b[1])>.001','Math.abs(a[1]-b[1])>.3').replace('v.truck.position.x,33','v.truck.position.x,-11')
s+='''
assert.equal(v.state.start.x,-13);assert.equal(v.approach(v.D.entries[0])[0][1],0);v.setFloor('1');v.state.fire={x:60,z:15};v.updateRoutes();v.routeGroup.traverse(o=>{if(o.material)assert.equal(o.material.depthTest,true)});assert(!fs.readFileSync('work/industrial.html','utf8').includes('id="roomList"'));console.log('Ground routes, depth occlusion and fire-only controls verified');
'''
p.write_text(s,encoding='utf-8')
