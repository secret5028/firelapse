import fs from 'node:fs';import path from 'node:path';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),{chromium}=require(process.env.PYROCAST_PLAYWRIGHT||'playwright');
const out=path.resolve('reviews/smoke-doorjet-20261103');
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const report={errors:[],scenes:[]};
try{
 const p=await browser.newPage({viewport:{width:1280,height:720}});p.setDefaultTimeout(120000);p.on('pageerror',e=>{report.errors.push(e.message);console.log(e.message);});p.on('console',m=>{if(m.type()==='error')report.errors.push(m.text());});
 await p.addInitScript(()=>{performance.now=()=>180000;const raf=requestAnimationFrame;window.requestAnimationFrame=cb=>raf(()=>cb(180000));});
 await p.route('**/operating.js',async route=>{const r=await route.fetch();await route.fulfill({response:r,body:(await r.text()).replace('const app=await attach(viewer);','const app=await attach(viewer);window.__ui=app;window.__cad=viewer;window.__ready=true;')});});
 await p.route('**/model.html',async route=>{const r=await route.fetch();let h=await r.text(),key='await (await import("/cfbt/overlay.js")).attach({',i=h.indexOf(key);if(i>=0){const j=h.indexOf('\n</script>',i),old=h.slice(i,j),arg=old.slice(key.length-1,old.lastIndexOf(');'));h=h.slice(0,i)+'window.__cad='+arg+';window.__ui=await (await import("/cfbt/overlay.js")).attach(window.__cad);window.__ready=true;'+h.slice(j);}await route.fulfill({response:r,body:h});});
 const settle=()=>p.evaluate(async()=>{window.__ui.render();for(let i=0;i<5;i++)await new Promise(requestAnimationFrame);});
 async function inspect(){return p.evaluate(()=>{const app=window.__ui,v=window.__cad,objects=[];v.S.traverse(o=>{if(o.userData.doorJet||o.userData.flameEffect)objects.push({name:o.name,visible:o.visible,position:o.position.toArray(),scale:o.scale.toArray(),data:o.userData});});return {time:app.store.get('playback').t_s,stats:app.layers.find(l=>l.constructor.id==='smoke').diagnostics().stats,objects,camera:{position:v.C.position.toArray(),target:v.O.target.toArray()}};});}
 await p.goto('http://127.0.0.1:8832/data/wando-coldstore/model.html');await p.waitForFunction(()=>window.__ready);
 for(const t of [1325,2100]){
  await p.evaluate(t=>{const el=document.getElementById('liteTime');el.value=t;el.oninput();const r=document.getElementById('liteRoom');r.value='CAD_1F_R5';r.onchange();document.getElementById('liteFocus').click();},t);await settle();report.scenes.push(await inspect());await p.screenshot({path:path.join(out,`Wando-P1-${t}-R5.png`)});
 }
 await p.evaluate(()=>{window.__cad.O.target.set(49.375,9.05,3.2025);document.getElementById('floor1').click();document.getElementById('iso').click();});await settle();await p.screenshot({path:path.join(out,'Wando-P1-2100-D1-view.png')});
 report.d1Camera=await p.evaluate(()=>({position:window.__cad.C.position.toArray(),target:window.__cad.O.target.toArray()}));
 await p.evaluate(()=>window.__ui.store.dispatch('layers/toggle',{id:'flame',visible:false}));await settle();report.toggleOff=await inspect();assert(report.toggleOff.objects.every(o=>!o.visible));
 console.log('Wando verified, loading 3F');await p.goto('http://127.0.0.1:8780/cad-result/90d3c325f238a3c4/model.html');await p.waitForFunction(()=>window.__ready);
 await p.evaluate(async()=>{const c=document.getElementById('liteCase');c.value='S09';await c.onchange();const t=document.getElementById('liteTime');t.value=1420;t.oninput();[...document.querySelectorAll('#fbtn button')].find(b=>b.textContent==='3F').click();const s=document.getElementById('liteRoom');s.value=[...s.options].find(o=>o.textContent.includes('R2_C1')).value;s.onchange();document.getElementById('liteFocus').click();});await settle();report.scenes.push(await inspect());await p.screenshot({path:path.join(out,'S09-1420-R2-door.png')});
 await p.evaluate(()=>{const v=window.__cad;let jet;v.S.traverse(o=>{if(o.userData.doorJet?.includes('CAD_3F_D8:'))jet=o;});const pos=jet.getWorldPosition(new v.THREE.Vector3());v.O.target.copy(pos);v.C.position.copy(pos).add(new v.THREE.Vector3(7,-8,7));v.O.update();});await settle();await p.screenshot({path:path.join(out,'S09-1420-R2-D8-close.png')});
 assert.equal(report.scenes[0].stats.doorJets.length,2);assert.equal(report.scenes[0].stats.wallGlows.length,1);assert(!report.scenes[0].stats.flames.includes('PU'));
 assert(Math.abs(report.scenes[0].stats.doorJets.reduce((n,j)=>n+j.q_kW,0)-6461.7671348)<1e-6);
 assert(report.scenes[2].stats.doorJets.length>0);assert.deepEqual(report.errors,[]);
}finally{fs.writeFileSync(path.join(out,'ui-verification.json'),JSON.stringify(report,null,2));await browser.close();}
