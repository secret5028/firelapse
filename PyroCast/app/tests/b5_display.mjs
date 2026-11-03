import fs from 'node:fs';import path from 'node:path';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),{chromium}=require(process.env.PYROCAST_PLAYWRIGHT||'playwright');
const phase=process.argv[2]||'before',out=path.resolve(process.env.PYROCAST_REVIEW_DIR||'reviews/B5-20261103',phase);fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const report={errors:[],defaults:[],options:[]};
try{
 const p=await browser.newPage({viewport:{width:1280,height:720},deviceScaleFactor:1});p.setDefaultTimeout(120000);
 p.on('pageerror',e=>{report.errors.push(e.message);console.log('PAGEERROR',e.message);});p.on('console',m=>{if(m.type()==='error'){report.errors.push(m.text());console.log('CONSOLE',m.text());}});
 await p.addInitScript(()=>{performance.now=()=>180000;const raf=requestAnimationFrame;window.requestAnimationFrame=cb=>raf(()=>cb(180000));});
 await p.route('**/model.html',async route=>{const r=await route.fetch();let h=await r.text(),key='await (await import("/cfbt/overlay.js")).attach({',i=h.indexOf(key);if(i>=0){const j=h.indexOf('\n</script>',i),old=h.slice(i,j),arg=old.slice(key.length-1,old.lastIndexOf(');'));h=h.slice(0,i)+'window.__cad='+arg+';window.__ui=await (await import("/cfbt/overlay.js")).attach(window.__cad);window.__ready=true;'+h.slice(j);}await route.fulfill({response:r,body:h});});
 await p.route('**/operating.js',async route=>{const r=await route.fetch();await route.fulfill({response:r,body:(await r.text()).replace('const app=await attach(viewer);','const app=await attach(viewer);window.__ui=app;window.__cad=viewer;window.__ready=true;')});});
 const settle=()=>p.evaluate(async()=>{window.__ui.render();for(let i=0;i<6;i++)await new Promise(requestAnimationFrame);});
 const inspect=()=>p.evaluate(()=>{const a=window.__ui,v=window.__cad,lights=[];v.S.traverse(o=>{if(o.isPointLight)lights.push({id:o.userData.fireId,intensity:o.intensity,color:o.color.toArray()});});return {settings:a.store.get('realView'),time:a.store.get('playback').t_s,stats:a.layers.find(l=>l.constructor.id==='smoke').diagnostics().stats,camera:{position:v.C.position.toArray(),target:v.O.target.toArray()},lights};});
 async function load(url){console.log('LOAD',url);await p.goto(url);await p.waitForFunction(()=>window.__ready);await settle();console.log('READY');}
 await load('http://127.0.0.1:8780/cad-result/90d3c325f238a3c4/model.html');
 for(const [id,t,floor] of [['S09',1420,'3F'],['S09',1800,'3F'],['S06',890,'3F'],['S09',1800,'전체']]){
  await p.evaluate(async({id,t,floor})=>{const e=document.getElementById('liteCase');e.value=id;await e.onchange();const s=document.getElementById('liteTime');s.value=t;s.oninput();[...document.querySelectorAll('#fbtn button')].find(b=>b.textContent===floor).click();if(floor==='전체')window.__ui.store.dispatch('layers/toggle',{id:'core',visible:true});},{id,t,floor});await settle();
  const name=id+'-'+t+'-'+floor;await p.locator('#v canvas').screenshot({path:path.join(out,name+'.png')});report.defaults.push({name,...await inspect()});console.log('DEFAULT',phase,name);
 }
 if(phase==='after'){
  for(const [building,times] of [['S09',[600,1420,2400]],['Wando-P1',[1000,1400,2100]]]){
   if(building==='Wando-P1')await load('http://127.0.0.1:8832/data/wando-coldstore/model.html');
   else await p.evaluate(async()=>{const c=document.getElementById('liteCase');c.value='S09';await c.onchange();});
   await p.evaluate(building=>{const ui=window.__ui;ui.store.dispatch('realView/set',{smokeMode:'soot',flameStyle:'four_stage'});const floor=building==='S09'?'3F':'1F';[...document.querySelectorAll('#fbtn button')].find(b=>b.textContent===floor).click();const r=document.getElementById('liteRoom');r.value=[...r.options].find(o=>building==='S09'?o.textContent.includes('R2_C0'):o.value==='CAD_1F_R5').value;r.onchange();},building);
   for(const t of times){
    await p.evaluate(t=>{const e=document.getElementById('liteTime');e.value=t;e.oninput();document.getElementById('iso').click();},t);await settle();
    for(const view of ['iso','room']){
     if(view==='room'){await p.evaluate(()=>document.getElementById('liteFocus').click());await settle();}
     const name=`${building}-${t}-${view}`;await p.screenshot({path:path.join(out,name+'.png')});report.options.push({name,...await inspect()});console.log('OPTION',name);
    }
   }
  }
  // Wando default roundtrip, same camera/time and the full canvas (no panel delta).
  await p.evaluate(()=>window.__ui.store.dispatch('realView/set',{smokeMode:'current',flameStyle:'current'}));await settle();await p.locator('#v canvas').screenshot({path:path.join(out,'roundtrip-before.png')});
  await p.evaluate(()=>window.__ui.store.dispatch('realView/set',{smokeMode:'soot',flameStyle:'four_stage'}));await settle();
  await p.evaluate(()=>window.__ui.store.dispatch('realView/set',{smokeMode:'current',flameStyle:'current'}));await settle();await p.locator('#v canvas').screenshot({path:path.join(out,'roundtrip-after.png')});
 }
 assert.deepEqual(report.errors,[]);
}finally{fs.writeFileSync(path.join(out,'capture.json'),JSON.stringify(report,null,2));await browser.close();}
