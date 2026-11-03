import fs from 'node:fs';import path from 'node:path';import assert from 'node:assert/strict';import {createRequire} from 'node:module';import {fileURLToPath} from 'node:url';
process.chdir(path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..'));
const require=createRequire(import.meta.url),{chromium}=require(process.env.PYROCAST_PLAYWRIGHT||'playwright');
const stage='gains',out=path.resolve('reviews/rollover-sliders-20261103/gains');fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const report={stage,errors:[],scenes:[],cases:[]};
try{
 const p=await browser.newPage({viewport:{width:1280,height:720},deviceScaleFactor:1});p.setDefaultTimeout(120000);p.on('pageerror',e=>report.errors.push(e.message));
 await p.addInitScript(()=>{performance.now=()=>180000;const raf=requestAnimationFrame;window.requestAnimationFrame=cb=>raf(()=>cb(180000));});
 await p.route('**/cfbt/overlay.js',async route=>{const r=await route.fetch();let s=await r.text();assert(s.includes('clock={now:()=>performance.now()}'));s=s.replace('clock={now:()=>performance.now()}','clock={now:()=>180000}');await route.fulfill({response:r,body:s});});
 await p.route('**/model.html',async route=>{const r=await route.fetch();let h=await r.text(),key='await (await import("/cfbt/overlay.js")).attach({',i=h.indexOf(key),j=h.indexOf('\n</script>',i),old=h.slice(i,j),arg=old.slice(key.length-1,old.lastIndexOf(');'));if(i<0)return route.fulfill({response:r,body:h});h=h.slice(0,i)+'window.__cad='+arg+';window.__ui=await (await import("/cfbt/overlay.js")).attach(window.__cad);window.__ready=true;'+h.slice(j);await route.fulfill({response:r,body:h});});
 await p.route('**/operating.js',async route=>{const r=await route.fetch(),s=(await r.text()).replace('const app=await attach(viewer);','const app=await attach(viewer);window.__cad=viewer;window.__ui=app;window.__ready=true;');await route.fulfill({response:r,body:s});});
 await p.goto('http://127.0.0.1:8780/cad-result/90d3c325f238a3c4/model.html');await p.waitForFunction(()=>window.__ready);
 for(const [id,t,floor] of [['S09',1420,'3F'],['S09',1800,'3F'],['S06',890,'3F'],['S09',1800,'전체']]){
  await p.evaluate(async({id,t,floor})=>{const e=document.getElementById('liteCase');e.value=id;await e.onchange();const s=document.getElementById('liteTime');s.value=t;s.oninput();[...document.querySelectorAll('#fbtn button')].find(b=>b.textContent===floor).click();window.__ui.render();for(let k=0;k<5;k++)await new Promise(requestAnimationFrame);},{id,t,floor});
  await p.evaluate(()=>document.getElementById('sceneGainControls').hidden=true);const name=id+'-'+t+'-'+floor;await p.locator('#v canvas').screenshot({path:path.join(out,name+'.png')});report.scenes.push({name,...await p.evaluate(()=>({case:window.__ui.diagnostics().case_id,calls:window.__cad.R.info.render.calls}))});
 }

 await p.evaluate(async()=>{document.getElementById('sceneGainControls').hidden=false;const t=document.getElementById('liteTime');t.value=1420;t.oninput();[...document.querySelectorAll('#fbtn button')].find(b=>b.textContent==='3F').click();window.__ui.render();for(let k=0;k<5;k++)await new Promise(requestAnimationFrame);});
 const set=async(id,value)=>p.evaluate(async({id,value})=>{const n=document.getElementById(id);n.value=value;n.dispatchEvent(new Event('input',{bubbles:true}));window.__ui.render();for(let k=0;k<3;k++)await new Promise(requestAnimationFrame);},{id,value});
 const values=()=>p.evaluate(()=>({state:window.__ui.store.get('realView'),inputs:Object.fromEntries(['scenesmokeGain','sceneflameGain','displaysmokeGain','displayflameGain'].map(id=>[id,Number(document.getElementById(id).value)]))}));
 report.defaults=await values();assert.equal(report.defaults.state.smokeOpacity,.7);assert.equal(report.defaults.state.smokeGain,1);assert.equal(report.defaults.state.flameGain,1);
 await p.locator('#v').screenshot({path:path.join(out,'S09-default-controls.png')});
 for(const [smoke,flame] of [[30,50],[150,200],[100,100]]){
  await set('scenesmokeGain',smoke);await set('sceneflameGain',flame);const v=await values();assert.equal(v.inputs.displaysmokeGain,smoke);assert.equal(v.inputs.displayflameGain,flame);assert.equal(v.state.smokeOpacity,.7);
  await p.locator('#v').screenshot({path:path.join(out,`S09-${smoke}-${flame}.png`)});(report.gains??=[]).push(v);
 }
 await p.click('#shellTab-display');await set('displaysmokeGain',80);await set('displayflameGain',120);report.panelSync=await values();assert.equal(report.panelSync.inputs.scenesmokeGain,80);assert.equal(report.panelSync.inputs.sceneflameGain,120);
 await p.screenshot({path:path.join(out,'display-panel.png')});
 await p.click('#shellTab-result');
 const downloadPromise=p.waitForEvent('download',{timeout:180000});await p.click('#exportHTML');const download=await downloadPromise;const html=path.join(out,'PyroCast-S09-gains.html');await download.saveAs(html);report.offlineBytes=fs.statSync(html).size;
 const offline=await browser.newPage({viewport:{width:1280,height:720}});const offlineErrors=[],http=[];offline.on('pageerror',e=>offlineErrors.push(e.message));offline.on('request',r=>{if(/^https?:/.test(r.url()))http.push(r.url());});
 await offline.goto('file:///'+html.replaceAll('\\','/'),{waitUntil:'domcontentloaded',timeout:180000});await offline.waitForFunction(()=>document.documentElement.dataset.offlineReady==='true',{},{timeout:180000});
 assert.equal(await offline.locator('#scenesmokeGain').inputValue(),'80');assert.equal(await offline.locator('#sceneflameGain').inputValue(),'120');
 await offline.locator('#scenesmokeGain').evaluate(e=>{e.value=150;e.dispatchEvent(new Event('input',{bubbles:true}));});assert.equal(await offline.locator('#displaysmokeGain').inputValue(),'150');
 await offline.screenshot({path:path.join(out,'offline.png')});report.offline={httpRequests:http.length,errors:offlineErrors,savedSmoke:80,savedFlame:120,liveSmoke:150};assert.equal(http.length,0);assert.deepEqual(offlineErrors,[]);await offline.close();
 await p.evaluate(()=>window.__ui.dispose());report.dispose=await p.evaluate(()=>({controls:document.querySelectorAll('#sceneGainControls').length,subscriptions:window.__ui.store.diagnostics().subscriptions}));assert.deepEqual(report.dispose,{controls:0,subscriptions:0});
 assert.equal(report.errors.length,0);
}finally{fs.writeFileSync(path.join(out,'review.json'),JSON.stringify(report,null,2));await browser.close();}
