from pathlib import Path
s=Path('work/check_runtime_v2.mjs').read_text(encoding='utf-8')
s+='''
for(const mode of ['detail','site'])for(const top of [false,true]){
ctx.window.fireViewer.setMode(mode);vm.runInContext('resetCamera('+top+')',ctx);
const projected=vm.runInContext("(()=>{const n=new THREE.Vector3(state.mode==='site'?0:.707,0,state.mode==='site'?-1:-.707);return target.clone().add(n.multiplyScalar(10)).project(camera).sub(target.clone().project(camera));})()",ctx);
assert(Math.abs(projected.x)<1e-6);assert(projected.y>0);
}
assert.equal(vm.runInContext('equipMeshes.length',ctx),2);
assert.equal(vm.runInContext("pickables.filter(o=>o.userData.info?.name.includes('소화전')).length",ctx),0);
assert.equal(vm.runInContext("pickables.filter(o=>o.userData.info?.name.includes('알람밸브')).length",ctx),2);
console.log('PASS north-up reset for both views and elevations; no hydrant markers; two sourced AV markers.');
'''
Path('work/check_runtime_v3.mjs').write_text(s,encoding='utf-8')
