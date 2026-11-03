import {execFileSync} from 'node:child_process';
import fs from 'node:fs';import path from 'node:path';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),{chromium}=require(process.env.PYROCAST_PLAYWRIGHT||'playwright');
const phase=process.argv[2]||'after',out=path.resolve('reviews/wall-opening-lines-20261103',phase);fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const report={errors:[],samples:[]};
try{
 const p=await browser.newPage({viewport:{width:1280,height:720},deviceScaleFactor:1});p.setDefaultTimeout(120000);p.on('pageerror',e=>report.errors.push(e.message));
 await p.addInitScript(()=>{performance.now=()=>180000;const raf=requestAnimationFrame;window.requestAnimationFrame=cb=>raf(()=>{if(!window.__holdFrames)cb(180000);});});
 await p.route('**/operating.js*',async route=>{const r=await route.fetch();await route.fulfill({response:r,body:(await r.text()).replace('const app=await attach(viewer);','const app=await attach(viewer);window.__ui=app;window.__ready=true;')});});
 if(phase==='before'){const old=execFileSync('git',['-c','safe.directory=*','-C','simulation/results/github-publish-20261026','show','HEAD:PyroCast/simulation/viewer/overlay.js'],{encoding:'utf8',maxBuffer:3000000});await p.route('**/overlay.js*',async route=>{const r=await route.fetch();await route.fulfill({response:r,body:old});});}
 await p.goto('http://127.0.0.1:8832/data/wando-coldstore/model.html');await p.waitForFunction(()=>window.__ready);
 await p.evaluate(()=>{const r=document.getElementById('liteRoom');r.value='CAD_1F_R5';r.onchange();document.getElementById('liteFocus').click();window.__holdFrames=true;window.__ui.store.dispatch('openings/set',{interior:true,exterior:true});window.__ui.render();});
 for(const time of [0,1325,2100]){
  await p.evaluate(t=>{const el=document.getElementById('liteTime');el.value=t;el.oninput();window.__ui.render();},time);
  report.samples.push(await p.evaluate(()=>{const scene=window.__ui.host.scene,building=scene.getObjectByName('building'),lines=[],meshes=[];building.traverse(o=>{if(o.isLineSegments)lines.push({name:o.name,count:o.geometry.attributes.position.count});if(o.isMesh)meshes.push({name:o.name,opacity:o.material.opacity,transparent:o.material.transparent,geometry:o.geometry.type});});return {time:window.__ui.store.get('playback').t_s,lines,meshes};}));
  await p.locator('#v canvas').screenshot({path:path.join(out,`${time}.png`)});
 }
 await p.evaluate(()=>{window.__ui.dispose();window.dispatchEvent(new PageTransitionEvent('pagehide'));});report.subscriptionsAfterDispose=await p.evaluate(()=>window.__ui.store.diagnostics().subscriptions);assert.equal(report.subscriptionsAfterDispose,0);assert.deepEqual(report.errors,[]);
}finally{fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify(report,null,2));await browser.close();}
