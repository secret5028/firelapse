import fs from 'node:fs';import path from 'node:path';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),{chromium}=require(process.env.PYROCAST_PLAYWRIGHT||'playwright');
const out=path.resolve('reviews/fgi-rollover-state-20261103');fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const report={errors:[]};try{
const p=await browser.newPage({viewport:{width:1440,height:900}});p.setDefaultTimeout(120000);p.on('pageerror',e=>report.errors.push(e.message));
await p.addInitScript(()=>{performance.now=()=>180000;const raf=requestAnimationFrame;window.requestAnimationFrame=cb=>raf(()=>cb(180000));});
await p.route('**/operating.js',async route=>{const r=await route.fetch();await route.fulfill({response:r,body:(await r.text()).replace('const app=await attach(viewer);','const app=await attach(viewer);window.__ui=app;window.__ready=true;')});});
await p.goto('http://127.0.0.1:8832/data/wando-coldstore/model.html');await p.waitForFunction(()=>window.__ready);
async function sample(time,threshold=100,history=false){
 await p.evaluate(async({time,threshold,history})=>{const u=window.__ui;u.store.dispatch('risk/threshold',{ribbon:threshold});u.store.dispatch('risk/history',{enabled:history});const t=document.getElementById('liteTime');t.value=time;t.oninput();const s=document.getElementById('liteRoom');s.value=[...s.options].find(o=>o.textContent.includes('R5')).value;s.onchange();u.render();for(let i=0;i<3;i++)await new Promise(requestAnimationFrame);},{time,threshold,history});
 return p.evaluate(()=>{const u=window.__ui,dots=[];u.host.scene.traverse(o=>{if(o.name==='FGI rollover dots')dots.push({visible:o.visible,z:o.position.z,color:o.material.color.getHexString(),vertices:o.geometry.attributes.position.count});});return {types:Object.keys(u.store.get('risk').show),bars:[...document.querySelectorAll('#resultScores .resultScore')].map(e=>e.dataset.type),badge:document.getElementById('fgiRolloverBadge').hidden?null:document.getElementById('fgiRolloverBadge').textContent,selectedBadge:document.querySelector('#resultScores .fgiRolloverBadge')?.textContent,dots,diagnostics:u.diagnostics()};});
}
report.current=await sample(2120);assert.deepEqual(report.current.bars,['FO','FGI','backdraft']);assert.deepEqual(report.current.types,['FO','FGI','backdraft','smoke']);assert(report.current.badge.includes('롤오버 진행'));assert.equal(report.current.dots.filter(d=>d.visible).length,1);assert(report.current.dots.filter(d=>d.visible).every(d=>d.color==='f97316'));
await p.screenshot({path:path.join(out,'Wando-P1-2120-current.png')});
report.threshold120=await sample(2120,120);assert.equal(report.threshold120.badge,null);assert(!report.threshold120.dots.some(d=>d.visible));await p.screenshot({path:path.join(out,'Wando-P1-2120-threshold120.png')});
report.history=await sample(0,100,true);assert(report.history.badge.includes('이력'));assert.equal(report.history.dots.filter(d=>d.visible).length,1);await p.screenshot({path:path.join(out,'Wando-P1-0-history.png')});
report.zero=await sample(0);assert.equal(report.zero.badge,null);assert(!report.zero.dots.some(d=>d.visible));

await p.evaluate(()=>{window.__ui.dispose();window.dispatchEvent(new PageTransitionEvent('pagehide'));});report.dispose=await p.evaluate(()=>window.__ui.store.diagnostics());assert.equal(report.dispose.subscriptions,0);assert.deepEqual(report.errors,[]);
}finally{fs.writeFileSync(path.join(out,'ui-verification.json'),JSON.stringify(report,null,2));await browser.close();}
