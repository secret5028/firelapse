import fs from 'node:fs';
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {readLegacyCoreSource,coreTransport} from '../web/adapters/legacy_core.js';
import {CoreLayer,fallbackStairSteps} from '../web/layers/core.js';
const T=await import(pathToFileURL(process.cwd()+'/simulation/results/github-publish-20261026/PyroCast/cad-project/work/cad-web/local-resources/cad-assets/three.module.js'));
const b=JSON.parse(fs.readFileSync('data/parkmarine-hotel/building.json','utf8')),before=JSON.stringify(b),hash='a'.repeat(64),groups=b.floors.map(f=>{const g=new T.Group();g.name=f.name;g.position.z=f.z;return g;});
const shape=p=>{const s=new T.Shape(p.o.map(q=>new T.Vector2(...q)));for(const h of p.h||[])s.holes.push(new T.Path(h.map(q=>new T.Vector2(...q))));return s;};
const asset=readLegacyCoreSource({building:b,groups,sourceHash:hash,shapeFor:shape}),rows=asset.floors.flatMap(f=>f.floor.transport);
assert.equal(rows.length,25);assert(rows.every(r=>r.connected&&r.meshes.length===0));
const generated=rows.map(r=>fallbackStairSteps(T,r));
assert(generated.flat().length>0);
for(const [i,r] of rows.entries()){
 if(r.kind==='elev'||!r.to_floor)assert.equal(generated[i].length,0);
 else {assert(generated[i].length>0);assert.equal(Math.max(...generated[i].map(s=>s.z1)),r.rise_m);}
}
// Clip a return stair to a concave footprint with a hole: no tread may fill either void.
const fixture={kind:'stair',assumption:'simplified_return_stair_display_only',rise_m:3.1,region:[{o:[[0,0],[4,0],[4,6],[2,6],[2,4],[0,4]],h:[[[.4,.4],[1,.4],[1,1],[.4,1]]]}]};
for(const step of fallbackStairSteps(T,fixture))for(const p of step.polys){
 const x=p.o.reduce((s,q)=>s+q[0],0)/p.o.length,y=p.o.reduce((s,q)=>s+q[1],0)/p.o.length;
 assert(!(x<2&&y>4));assert(!(x>.4&&x<1&&y>.4&&y<1));
}
for(const f of asset.floors)for(const r of f.floor.transport)assert(!b.unconfirmed_vertical_cores.some(n=>n.floor===f.id&&n.core_id===r.id));
const layer=new CoreLayer(T,{geometryFor:()=>asset});layer.mount(new T.Scene(),{subscribe:()=>()=>{}});const frame={building:{source_hash:hash},resultMeta:null,floor:{floor_id:null}};layer.setData(frame);layer.setVisible(true);layer.tick();
assert.equal(layer.diagnostics().shells,25);assert.equal(layer.diagnostics().edges,25);assert.equal(layer.group.visible,true);
assert.equal(layer.diagnostics().treads,generated.flat().length);
for(const v of layer.views)for(const m of v.group.children)if(m.renderOrder===72)assert.equal(m.material.color.getHexString(),'2563eb');
for(const v of layer.views){assert.equal(v.group.position.z,v.row.floor.z);for(const mesh of v.group.children)assert.equal(mesh.material.depthTest,false);}
layer.setData({...frame,floor:{floor_id:'5F'}});assert.equal(layer.group.visible,false);layer.dispose();assert.equal(layer.resources.size,0);assert.equal(JSON.stringify(b),before);
const old=JSON.parse(fs.readFileSync('simulation/results/github-publish-20261026/PyroCast/cad-project/building.json','utf8'));for(const f of old.floors)assert.equal(coreTransport(old,f),f.transport);
console.log(JSON.stringify({hotelVisible:rows.length,stairs:rows.filter(r=>r.kind==='stair').length,elevators:rows.filter(r=>r.kind==='elev').length,treads:generated.flat().length,unconfirmedExcluded:10,factoryTransportUnchanged:true,buildingDataUnchanged:true}));
