import fs from 'node:fs';import path from 'node:path';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),{chromium}=require(process.env.PYROCAST_PLAYWRIGHT||'playwright');
const phase=process.argv[2]||'after',out=path.resolve('reviews/hose-depth-20261103',phase);fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const report={errors:[],samples:[]};
try{
 const p=await browser.newPage({viewport:{width:1280,height:720},deviceScaleFactor:1});p.setDefaultTimeout(120000);p.on('pageerror',e=>report.errors.push(e.message));
 await p.addInitScript(()=>{performance.now=()=>180000;const raf=requestAnimationFrame;window.requestAnimationFrame=cb=>raf(()=>{if(!window.__holdFrames)cb(180000);});});
 await p.route('**/operating.js*',async route=>{const r=await route.fetch();await route.fulfill({response:r,body:(await r.text()).replace('const app=await attach(viewer);','const app=await attach(viewer);window.__ui=app;window.__ready=true;')});});
 await p.goto('http://127.0.0.1:8832/data/wando-coldstore/model.html');await p.waitForFunction(()=>window.__ready);
 await p.locator('#v canvas').screenshot({path:path.join(out,'initial.png')});
 await p.evaluate(()=>{window.__holdFrames=true;document.getElementById('top').click();window.__ui.render();});
 await p.locator('#v canvas').screenshot({path:path.join(out,'top.png')});
 report.materials=await p.evaluate(()=>{const a=window.__ui,root=a.host.scene.getObjectByName('route');return root.children.filter(o=>o.isMesh).map(o=>({name:o.name,depthTest:o.material.depthTest,order:o.renderOrder}));});
 if(phase==='after'){assert(report.materials.some(m=>m.depthTest));assert(report.materials.some(m=>!m.depthTest));}
 await p.evaluate(()=>{window.__ui.dispose();window.dispatchEvent(new PageTransitionEvent('pagehide'));});report.subscriptionsAfterDispose=await p.evaluate(()=>window.__ui.store.diagnostics().subscriptions);assert.equal(report.subscriptionsAfterDispose,0);assert.deepEqual(report.errors,[]);
}finally{fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify(report,null,2));await browser.close();}
