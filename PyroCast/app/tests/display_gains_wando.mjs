import fs from 'node:fs';import path from 'node:path';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),{chromium}=require(process.env.PYROCAST_PLAYWRIGHT||'playwright');const out=path.resolve('reviews/rollover-sliders-20261103/gains');
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const report={errors:[]};try{const p=await browser.newPage({viewport:{width:1280,height:720}});p.setDefaultTimeout(120000);p.on('pageerror',e=>report.errors.push(e.message));
await p.addInitScript(()=>{performance.now=()=>180000;const raf=requestAnimationFrame;window.requestAnimationFrame=cb=>raf(()=>cb(180000));});
await p.route('**/operating.js',async route=>{const r=await route.fetch();await route.fulfill({response:r,body:(await r.text()).replace('const app=await attach(viewer);','const app=await attach(viewer);window.__ui=app;window.__ready=true;')});});
await p.goto('http://127.0.0.1:8832/data/wando-coldstore/model.html');await p.waitForFunction(()=>window.__ready);
await p.evaluate(async()=>{const t=document.getElementById('liteTime');t.value=2120;t.oninput();const s=document.getElementById('liteRoom');s.value=[...s.options].find(o=>o.textContent.includes('R5')).value;s.onchange();window.__ui.render();for(let i=0;i<3;i++)await new Promise(requestAnimationFrame);});
await p.locator('#v').screenshot({path:path.join(out,'Wando-P1-2120.png')});
report.default=await p.evaluate(()=>window.__ui.store.get('realView'));
await p.evaluate(()=>{const e=document.getElementById('scenesmokeGain');e.value=150;e.dispatchEvent(new Event('input',{bubbles:true}));document.getElementById('sceneflameGain').value=50;document.getElementById('sceneflameGain').dispatchEvent(new Event('input',{bubbles:true}));window.__ui.render();});
report.uniforms=await p.evaluate(()=>{const smoke=[],flame=[];window.__ui.host.scene.traverse(o=>{const u=o.material?.uniforms;if(u?.uOpacity)smoke.push(u.uOpacity.value);if(u?.uFire?.value===1)flame.push(u.uFlameGain.value);});return {smoke:[...new Set(smoke)],flame:[...new Set(flame)]};});
assert(report.uniforms.smoke.includes(1.0499999999999998)||report.uniforms.smoke.some(x=>Math.abs(x-1.05)<1e-12));assert(report.uniforms.flame.every(x=>x===.5));
await p.evaluate(()=>{window.__ui.dispose();window.dispatchEvent(new PageTransitionEvent('pagehide'));});report.dispose=await p.evaluate(()=>({controls:document.querySelectorAll('#sceneGainControls').length,subscriptions:window.__ui.store.diagnostics().subscriptions}));assert.deepEqual(report.dispose,{controls:0,subscriptions:0});assert.deepEqual(report.errors,[]);
}finally{fs.writeFileSync(path.join(out,'wando-review.json'),JSON.stringify(report,null,2));await browser.close();}
