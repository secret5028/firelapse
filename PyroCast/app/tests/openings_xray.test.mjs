import assert from 'node:assert/strict';
import fs from 'node:fs';import {pathToFileURL} from 'node:url';
import {OpeningsLayer} from '../web/layers/openings.js';
import {openingFraction} from '../web/state/fixed_openings.js';
const T=await import(pathToFileURL(process.cwd()+'/cad-project/work/cad-web/local-resources/cad-assets/three.module.js'));
const B=JSON.parse(fs.readFileSync('data/parkmarine-hotel/building.json','utf8')),before=JSON.stringify(B),hash='a'.repeat(64);
const asset={source_hash:hash,floors:B.floors.map(f=>({id:f.name,floor:f,group:new T.Group()}))};
const camera=new T.PerspectiveCamera(),layer=new OpeningsLayer(T,{camera,geometryFor:()=>asset});layer.mount(new T.Scene(),{subscribe:()=>()=>{}});
let frame={building:{source_hash:hash},resultMeta:null,floor:{floor_id:'5F'},t_s:0};layer.setData(frame);layer.tick();const floor=layer.views.find(v=>v.row.id==='5F');assert(floor.windows.children.length>1);
const states={};floor.windows.children.forEach((line,i)=>{states[line.userData.openingId]={open:i%2===0};});frame={...frame,fixedOpenings:{states}};layer.setData(frame);
for(const side of [-1,1]){camera.position.set(side*100,side*100,10);layer.tick();for(const line of floor.windows.children){assert(line.visible);assert.equal(line.material.depthTest,false);assert.equal(line.material.depthWrite,false);assert.equal(line.renderOrder,46);assert.equal(line.material.color.getHexString(),'62dcb0');assert.equal(line.userData.cross.visible,!states[line.userData.openingId].open);assert.equal(line.userData.cross.material.depthTest,false);assert.equal(line.userData.cross.renderOrder,46);}}
// Fractional effective areas, including doors, are independent of the binary open flag.
assert.equal(openingFraction({open:true}),1);assert.equal(openingFraction({open:false}),0);assert.equal(openingFraction(null),null);
const partialLines=[floor.windows.children[0],floor.doors.children.find(l=>l.userData.cross)];
for(const fraction of [0,.25,.5,.75,1]){
 for(const line of partialLines)states[line.userData.openingId]={open:fraction>0,effective_fraction:fraction};
 layer.tick();
 for(const line of partialLines){const d=line.userData,partial=fraction>0&&fraction<1;
  assert.equal(d.displayFraction,fraction);assert.equal(d.partialFill.visible,partial);assert.equal(d.divider.visible,partial);assert.equal(d.cross.visible,fraction<1);
  assert.equal(d.partialFill.material.depthTest,false);assert.equal(d.partialFill.material.depthWrite,false);assert.equal(d.partialFill.material.opacity,.22);
  const [a,b]=d.frameVertices,position=d.partialFill.geometry.getAttribute('position'),end=new T.Vector3().fromBufferAttribute(position,1);
  assert(Math.abs(a.distanceTo(end)/a.distanceTo(b)-(1-fraction))<1e-4);
  assert.equal(d.stateLabel,`개방 ${fraction*100}% · 닫힘 ${(1-fraction)*100}%`);
 }
}
const builds=layer.buildCount;layer.setPartVisible('window',false);layer.tick();assert(floor.windows.visible); // confirmed state still shown, same as doors
layer.setData({...frame,fixedOpenings:null});layer.tick();assert(!floor.windows.visible);layer.setPartVisible('window',true);layer.tick();assert(floor.windows.visible);assert(floor.windows.children.every(l=>!l.userData.cross.visible));
layer.setData({...frame,floor:{floor_id:'4F'}});layer.tick();assert(!floor.windows.visible);assert.equal(layer.buildCount,builds);assert.equal(JSON.stringify(B),before);const resources=[...layer.resources];let disposed=0;resources.forEach(r=>r.addEventListener('dispose',()=>disposed++));layer.dispose();assert.equal(disposed,resources.length);
console.log('PASS: facade x-ray; 0/25/50/75/100% open area for doors/windows; binary fallback; scope; input unchanged; no rebuild; disposal');
