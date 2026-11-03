import fs from 'node:fs';import path from 'node:path';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),{chromium}=require(process.env.PYROCAST_PLAYWRIGHT||'playwright');
const phase=process.argv[2]||'after',out=path.resolve('reviews/edge-scale-reference-20261103',phase);fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const report={errors:[],samples:[]};
try{
 const p=await browser.newPage({viewport:{width:1280,height:720},deviceScaleFactor:1});p.setDefaultTimeout(120000);p.on('pageerror',e=>report.errors.push(e.message));
 await p.addInitScript(()=>{performance.now=()=>180000;const raf=requestAnimationFrame;window.requestAnimationFrame=cb=>raf(()=>{if(!window.__holdFrames)cb(180000);});});
 await p.route('**/operating.js*',async route=>{const r=await route.fetch();await route.fulfill({response:r,body:(await r.text()).replace('const app=await attach(viewer);','const app=await attach(viewer);window.__ui=app;window.__ready=true;')});});
 await p.goto('http://127.0.0.1:8832/data/wando-coldstore/model.html');await p.waitForFunction(()=>window.__ready);
 await p.locator('#v canvas').screenshot({path:path.join(out,'initial.png')});
 await p.evaluate(()=>{const r=document.getElementById('liteRoom');r.value='CAD_1F_R5';r.onchange();document.getElementById('liteFocus').click();window.__holdFrames=true;});
 for(const time of [1325,1400,2100]){
  await p.evaluate(t=>{const el=document.getElementById('liteTime');el.value=t;el.oninput();window.__ui.render();},time);
  const sample=await p.evaluate(()=>{const walls=[],jets=[];window.__ui.host.scene.traverse(o=>{if(o.name.startsWith('cavity-wall-glow:'))walls.push({name:o.name,visible:o.visible,opacity:o.material.opacity,alphaMap:!!o.material.alphaMap,renderOrder:o.renderOrder,vertices:o.geometry.attributes.position.count});if(o.visible&&o.userData.doorJet)jets.push({id:o.userData.doorJet,renderOrder:o.renderOrder,...o.userData.values});});return {walls,jets};});
  report.samples.push({time,...sample});assert(sample.jets.length>0);assert.equal(sample.walls.length,0);
  await p.locator('#v canvas').screenshot({path:path.join(out,`${time}.png`)});
 }
 await p.evaluate(()=>{document.getElementById('iso').click();window.__ui.render();});
 await p.locator('#v canvas').screenshot({path:path.join(out,'scale-overview.png')});
 report.references=await p.evaluate(()=>{const T=window.__cad?.THREE;const root=window.__ui.host.scene.getObjectByName('route');const out={truck:0,person:0,positions:[]};root.traverse(o=>{if(o.name.startsWith('scale-truck:'))out.truck++;if(o.name.startsWith('scale-person:'))out.person++;if(o.name.startsWith('scale-'))out.positions.push({name:o.name,position:o.position.toArray()});});return out;});
 assert(report.references.truck>0&&report.references.person>0);
 report.scaleCheck=await p.evaluate(async()=>{
  const T=await import('/vendor/three.module.js'),a=window.__ui,root=a.host.scene.getObjectByName('route'),person=new T.Box3(),truck=new T.Box3();root.updateWorldMatrix(true,true);
  root.traverse(o=>{if(o.name.startsWith('scale-person:'))person.union(new T.Box3().setFromObject(o));if(o.name.startsWith('scale-truck:'))truck.union(new T.Box3().setFromObject(o));});
  a.store.dispatch('route/set',{vehicle_visible:false});a.render();const hidden=root.children.filter(o=>o.isGroup&&o.children.some(c=>c.name.startsWith('scale-'))).every(o=>!o.visible);
  a.store.dispatch('route/set',{vehicle_visible:true});a.render();const shown=root.children.some(o=>o.visible&&o.isGroup&&o.children.some(c=>c.name.startsWith('scale-')));
  return {person_m:person.getSize(new T.Vector3()).toArray(),truck_m:truck.getSize(new T.Vector3()).toArray(),hidden,shown};
 });
 assert(Math.abs(report.scaleCheck.person_m[2]-1.75)<1e-5);assert(Math.abs(report.scaleCheck.truck_m[0]-8)<1e-5);assert(report.scaleCheck.hidden&&report.scaleCheck.shown);
 await p.evaluate(()=>{window.__ui.dispose();window.dispatchEvent(new PageTransitionEvent('pagehide'));});report.subscriptionsAfterDispose=await p.evaluate(()=>window.__ui.store.diagnostics().subscriptions);assert.equal(report.subscriptionsAfterDispose,0);assert.deepEqual(report.errors,[]);
}finally{fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify(report,null,2));await browser.close();}
