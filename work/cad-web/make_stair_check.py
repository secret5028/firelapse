from pathlib import Path
s=Path('work/check_factory.mjs').read_text(encoding='utf-8-sig').split('assert(v.ready)')[0]
s+='''
const nodes=[];vm.runInContext('scene',ctx).traverse(o=>{if(o.userData.stairPart)nodes.push(o)});
assert.equal(nodes.filter(o=>o.userData.stairPart==='tread').length,60);
for(const o of nodes){const h=o.geometry.parameters.height;assert(h<=.180001);if(o.userData.stairPart==='tread')assert(Math.abs(h-.07)<1e-8)}
const high=nodes.filter(o=>o.userData.stairPart==='tread'&&o.position.y>6);assert(high.length>0);assert(high.every(o=>new RealThree.Box3().setFromObject(o).min.y>5.9));
console.log('PASS 60 thin stair treads, thin risers and landing, open underside beneath upper flights.');
'''
Path('work/check_thin_stairs.mjs').write_text(s,encoding='utf-8')
