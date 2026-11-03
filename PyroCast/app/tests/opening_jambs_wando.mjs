import {execFileSync} from 'node:child_process';
import fs from 'node:fs';import path from 'node:path';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PYROCAST_PLAYWRIGHT||'playwright');
const out=path.resolve('reviews/opening-jambs-20261103');fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const report={};
try{for(const phase of ['before','after']){
 const p=await browser.newPage({viewport:{width:1280,height:720}}),errors=[];p.on('pageerror',e=>errors.push(e.message));
 await p.addInitScript(()=>{performance.now=()=>180000;const raf=requestAnimationFrame;window.requestAnimationFrame=cb=>raf(()=>{if(!window.__holdFrames)cb(180000);});});
 await p.route('**/operating.js*',async route=>{const r=await route.fetch();await route.fulfill({response:r,body:(await r.text()).replace('const app=await attach(viewer);','const app=await attach(viewer);window.__ui=app;window.__viewer=viewer;window.__ready=true;')});});
 if(phase==='before')for(const [url,file] of [['**/overlay.js*','simulation/viewer/overlay.js'],['**/exterior-layer.js*','data/wando-coldstore/exterior-layer.js']]){
  const body=execFileSync('git',['-c','safe.directory=*','-C','simulation/results/github-publish-20261026','show','b2a8efb:PyroCast/'+file],{encoding:'utf8',maxBuffer:3000000});await p.route(url,r=>r.fulfill({contentType:'text/javascript',body}));
 }
 await p.goto('http://127.0.0.1:8832/data/wando-coldstore/model.html');await p.waitForFunction(()=>window.__ready&&document.getElementById('wandoExterior'));
 await p.evaluate(()=>{window.__holdFrames=true;window.__ui.store.dispatch('openings/set',{interior:true,exterior:true});window.__ui.render();});
 await p.locator('#v canvas').screenshot({path:path.join(out,phase+'-context.png')});
 await p.evaluate(()=>{const {C,O}=window.__viewer;O.target.set(49.375,0,3.3);C.position.set(55,-14,8);O.update();window.__ui.render();});
 await p.locator('#v canvas').screenshot({path:path.join(out,phase+'-door.png')});
 report[phase]=await p.evaluate(()=>{const root=window.__ui.host.scene.getObjectByName('wando-photo-exterior'),surfaces=[];root.traverse(o=>{if(o.name==='wando-facade-surface')surfaces.push({opacity:o.material.opacity,transparent:o.material.transparent,vertices:o.geometry.attributes.position.count});});return {surfaces};});
 if(phase==='after'){assert.equal(report[phase].surfaces.length,21);assert(report[phase].surfaces.every(s=>s.vertices===6&&s.transparent&&Math.abs(s.opacity-.4816)<1e-8));}
 await p.evaluate(()=>{window.__ui.dispose();window.dispatchEvent(new PageTransitionEvent('pagehide'));});assert.equal(await p.evaluate(()=>window.__ui.store.diagnostics().subscriptions),0);assert.deepEqual(errors,[]);report[phase].errors=errors;await p.close();
}}finally{fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify(report,null,2));await browser.close();}
