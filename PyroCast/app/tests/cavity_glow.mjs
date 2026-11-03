import fs from 'node:fs';import path from 'node:path';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),{chromium}=require(process.env.PYROCAST_PLAYWRIGHT||'playwright');
const phase=process.argv[2]||'after',out=path.resolve('reviews/cavity-glow-20261103',phase);fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const report={errors:[],samples:[]};
try{
 const p=await browser.newPage({viewport:{width:1280,height:720},deviceScaleFactor:1});p.setDefaultTimeout(120000);p.on('pageerror',e=>report.errors.push(e.message));
 await p.addInitScript(()=>{performance.now=()=>180000;const raf=requestAnimationFrame;window.requestAnimationFrame=cb=>raf(()=>{if(!window.__holdFrames)cb(180000);});});
 await p.route('**/operating.js',async route=>{const r=await route.fetch();await route.fulfill({response:r,body:(await r.text()).replace('const app=await attach(viewer);','const app=await attach(viewer);window.__ui=app;window.__ready=true;')});});
 await p.goto('http://127.0.0.1:8832/data/wando-coldstore/model.html');await p.waitForFunction(()=>window.__ready);
 await p.evaluate(()=>{const r=document.getElementById('liteRoom');r.value='CAD_1F_R5';r.onchange();document.getElementById('liteFocus').click();window.__holdFrames=true;});
 for(const time of [1325,1400,2100]){
  await p.evaluate(t=>{const el=document.getElementById('liteTime');el.value=t;el.oninput();window.__ui.render();},time);
  const sample=await p.evaluate(()=>{const walls=[],jets=[];window.__ui.host.scene.traverse(o=>{if(o.name.startsWith('cavity-wall-glow:'))walls.push({name:o.name,visible:o.visible,opacity:o.material.opacity,alphaMap:!!o.material.alphaMap,renderOrder:o.renderOrder,vertices:o.geometry.attributes.position.count});if(o.visible&&o.userData.doorJet)jets.push({id:o.userData.doorJet,renderOrder:o.renderOrder,...o.userData.values});});return {walls,jets};});
  report.samples.push({time,...sample});assert(sample.jets.length>0);if(phase==='after')assert(sample.walls.every(w=>w.alphaMap&&w.opacity<=.18&&w.renderOrder<20));
  await p.locator('#v canvas').screenshot({path:path.join(out,`${time}.png`)});
 }
 await p.evaluate(()=>{window.__ui.dispose();window.dispatchEvent(new PageTransitionEvent('pagehide'));});report.subscriptionsAfterDispose=await p.evaluate(()=>window.__ui.store.diagnostics().subscriptions);assert.equal(report.subscriptionsAfterDispose,0);assert.deepEqual(report.errors,[]);
}finally{fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify(report,null,2));await browser.close();}
