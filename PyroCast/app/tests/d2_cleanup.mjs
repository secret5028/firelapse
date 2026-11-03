import fs from 'node:fs';import path from 'node:path';import assert from 'node:assert/strict';import {createRequire} from 'node:module';import {execFileSync} from 'node:child_process';import {fileURLToPath} from 'node:url';
process.chdir(path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..'));
const require=createRequire(import.meta.url),{chromium}=require(process.env.PYROCAST_PLAYWRIGHT||'playwright');
const stage=process.env.D2_STAGE||'before',out=path.resolve('reviews/D2-20261103',stage);fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const report={stage,errors:[],scenes:[],cases:[]};
try{
 const p=await browser.newPage({viewport:{width:1280,height:720},deviceScaleFactor:1});p.setDefaultTimeout(120000);p.on('pageerror',e=>report.errors.push(e.message));
 await p.addInitScript(()=>{performance.now=()=>180000;const raf=requestAnimationFrame;window.requestAnimationFrame=cb=>raf(()=>cb(180000));});
 await p.route('**/cfbt/overlay.js',async route=>{const r=await route.fetch();let s=stage.includes('before')?execFileSync('git',['-c','safe.directory=*','-C','simulation/results/github-publish-20261026','show','832cfe0:PyroCast/simulation/viewer/overlay.js'],{encoding:'utf8'}):await r.text();assert(s.includes('clock={now:()=>performance.now()}'));s=s.replace('clock={now:()=>performance.now()}','clock={now:()=>180000}');await route.fulfill({response:r,body:s});});
 await p.route('**/model.html',async route=>{const r=await route.fetch();let h=await r.text(),key='await (await import("/cfbt/overlay.js")).attach({',i=h.indexOf(key),j=h.indexOf('\n</script>',i),old=h.slice(i,j),arg=old.slice(key.length-1,old.lastIndexOf(');'));if(i<0)return route.fulfill({response:r,body:h});h=h.slice(0,i)+'window.__cad='+arg+';window.__ui=await (await import("/cfbt/overlay.js")).attach(window.__cad);window.__ready=true;'+h.slice(j);await route.fulfill({response:r,body:h});});
 await p.route('**/operating.js',async route=>{const r=await route.fetch(),s=(await r.text()).replace('const app=await attach(viewer);','const app=await attach(viewer);window.__cad=viewer;window.__ui=app;window.__ready=true;');await route.fulfill({response:r,body:s});});
 await p.goto('http://127.0.0.1:8780/cad-result/90d3c325f238a3c4/model.html');await p.waitForFunction(()=>window.__ready);
 for(const [id,t,floor] of [['S09',1420,'3F'],['S09',1800,'3F'],['S06',890,'3F'],['S09',1800,'전체']]){
  await p.evaluate(async({id,t,floor})=>{const e=document.getElementById('liteCase');e.value=id;await e.onchange();const s=document.getElementById('liteTime');s.value=t;s.oninput();[...document.querySelectorAll('#fbtn button')].find(b=>b.textContent===floor).click();window.__ui.render();for(let k=0;k<5;k++)await new Promise(requestAnimationFrame);},{id,t,floor});
  const name=id+'-'+t+'-'+floor;await p.locator('#v canvas').screenshot({path:path.join(out,name+'.png')});report.scenes.push({name,...await p.evaluate(()=>({case:window.__ui.diagnostics().case_id,calls:window.__cad.R.info.render.calls}))});
 }
 if(stage==='after'){
  for(const base of ['http://127.0.0.1:8780','http://127.0.0.1:8832']){
   if(base.endsWith('8832')){await p.goto(base+'/data/wando-coldstore/model.html');await p.waitForFunction(()=>window.__ready);}
   const ids=await p.locator('#liteCase option').evaluateAll(es=>es.map(e=>e.value));
   for(const id of ids){const value=await p.evaluate(async id=>{const e=document.getElementById('liteCase');e.value=id;await e.onchange();window.__ui.render();return {id,actual:window.__ui.diagnostics().case_id,rooms:document.getElementById('liteRoom').options.length,errors:window.__ui.store.get('result')?.errors||[]};},id);assert.equal(value.actual,id);assert(value.rooms>0);assert.equal(value.errors.length,0);report.cases.push({base,...value});fs.writeFileSync(path.join(out,'review.json'),JSON.stringify(report,null,2));}
  }
 }
 assert.equal(report.errors.length,0);
}finally{fs.writeFileSync(path.join(out,'review.json'),JSON.stringify(report,null,2));await browser.close();}
