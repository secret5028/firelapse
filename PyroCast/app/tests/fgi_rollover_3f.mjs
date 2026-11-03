import fs from 'node:fs';import path from 'node:path';import assert from 'node:assert/strict';import {createRequire} from 'node:module';import {fileURLToPath} from 'node:url';
process.chdir(path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..'));
const require=createRequire(import.meta.url),{chromium}=require(process.env.PYROCAST_PLAYWRIGHT||'playwright');
const stage='fgi-state',out=path.resolve('reviews/fgi-rollover-state-20261103');fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const report={stage,errors:[],scenes:[],cases:[]};
try{
 const p=await browser.newPage({viewport:{width:1280,height:720},deviceScaleFactor:1});p.setDefaultTimeout(120000);p.on('pageerror',e=>report.errors.push(e.message));
 await p.addInitScript(()=>{performance.now=()=>180000;const raf=requestAnimationFrame;window.requestAnimationFrame=cb=>raf(()=>cb(180000));});
 await p.route('**/cfbt/overlay.js',async route=>{const r=await route.fetch();let s=await r.text();assert(s.includes('clock={now:()=>performance.now()}'));s=s.replace('clock={now:()=>performance.now()}','clock={now:()=>180000}');await route.fulfill({response:r,body:s});});
 await p.route('**/model.html',async route=>{const r=await route.fetch();let h=await r.text(),key='await (await import("/cfbt/overlay.js")).attach({',i=h.indexOf(key),j=h.indexOf('\n</script>',i),old=h.slice(i,j),arg=old.slice(key.length-1,old.lastIndexOf(');'));if(i<0)return route.fulfill({response:r,body:h});h=h.slice(0,i)+'window.__cad='+arg+';window.__ui=await (await import("/cfbt/overlay.js")).attach(window.__cad);window.__ready=true;'+h.slice(j);await route.fulfill({response:r,body:h});});
 await p.route('**/operating.js',async route=>{const r=await route.fetch(),s=(await r.text()).replace('const app=await attach(viewer);','const app=await attach(viewer);window.__cad=viewer;window.__ui=app;window.__ready=true;');await route.fulfill({response:r,body:s});});
 await p.goto('http://127.0.0.1:8780/cad-result/90d3c325f238a3c4/model.html');await p.waitForFunction(()=>window.__ready,null,{timeout:60000}).catch(async e=>{console.log(await p.locator('body').innerText());await p.screenshot({path:path.join(out,'3f-init-failure.png')});throw e;});

 await p.evaluate(async()=>{const e=document.getElementById('liteCase');e.value='S09';await e.onchange();const t=document.getElementById('liteTime');t.value=1420;t.oninput();[...document.querySelectorAll('#fbtn button')].find(b=>b.textContent==='3F').click();const s=document.getElementById('liteRoom');s.value=[...s.options].find(o=>o.textContent.includes('R2_C0')).value;s.onchange();window.__ui.render();for(let i=0;i<3;i++)await new Promise(requestAnimationFrame);});
 report.bars=await p.locator('#resultScores .resultScore').evaluateAll(es=>es.map(e=>e.dataset.type));assert.deepEqual(report.bars,['FO','FGI','backdraft']);
 report.origin=await p.evaluate(()=>{const r=window.__ui.store.get('result');return Object.entries(r.fgi_rollover_by_cell).filter(([k])=>k.startsWith('CAD_3F_R2_')).map(([k,v])=>({cell:k,excluded:v.excluded_origin}));});assert(report.origin.length>0);assert(report.origin.every(v=>v.excluded));
 await p.screenshot({path:path.join(out,'S09-1420-R2.png')});assert.deepEqual(report.errors,[]);
 const promise=p.waitForEvent('download');await p.click('#exportHTML');const dl=await promise,html=path.join(out,'S09-fgi-state.html');await dl.saveAs(html);
 const offline=await browser.newPage(),http=[],errors=[];offline.on('request',r=>{if(/^https?:/.test(r.url()))http.push(r.url());});offline.on('pageerror',e=>errors.push(e.message));
 await offline.goto('file:///'+html.replaceAll('\\','/'),{waitUntil:'domcontentloaded',timeout:180000});await offline.waitForFunction(()=>document.documentElement.dataset.offlineReady==='true',null,{timeout:180000});
 assert.equal(await offline.locator('#resultScores .resultScore').count(),3);assert.deepEqual(errors,[]);assert.equal(http.length,0);report.offline={bytes:fs.statSync(html).size,http:0,errors};await offline.close();await p.evaluate(()=>window.__ui.dispose());
}finally{fs.writeFileSync(path.join(out,'3f-ui-verification.json'),JSON.stringify(report,null,2));await browser.close();}
