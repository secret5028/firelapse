const fs=require('fs'),path=require('path'),crypto=require('crypto');
const {chromium}=require('C:/Users/예방/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const phase=process.argv[2]||'before',dir=__dirname,out=path.join(dir,phase),cache=path.join(dir,'api-cache');fs.mkdirSync(out,{recursive:true});fs.mkdirSync(cache,{recursive:true});
const report={phase,scenes:[],errors:[],httpErrors:[],blockedWrites:[],toggles:[]};
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try{
async function pageFor(url,width,height=1000){
 const p=await browser.newPage({viewport:{width,height},deviceScaleFactor:1});p.setDefaultTimeout(60000);
 p.on('pageerror',e=>report.errors.push({url,message:e.message}));
 await p.addInitScript(()=>{performance.now=()=>180000;const raf=requestAnimationFrame,pending=[];window.requestAnimationFrame=cb=>raf(()=>window.__pauseRAF?pending.push(cb):cb(180000));window.__resumeRAF=()=>{window.__pauseRAF=false;for(const cb of pending.splice(0))window.requestAnimationFrame(cb);};let seed=123456789;Math.random=()=>((seed=(1664525*seed+1013904223)>>>0)/4294967296);});
 await p.route('**/*',async r=>{const req=r.request(),u=new URL(req.url());
  if(!['GET','HEAD'].includes(req.method())){report.blockedWrites.push({url:req.url(),method:req.method()});return r.fulfill({status:409,contentType:'application/json',body:'{"error":"THEME-1 read-only verification"}'});}
  if(u.pathname==='/models/ai/connection')return r.fulfill({contentType:'application/json',body:'{"connected":false,"storage":"server_memory"}'});
  if(u.pathname.endsWith('/controller.js')||u.pathname==='/cfbt/overlay.js'){
   const res=await r.fetch();let t=await res.text();t=t.replace('return Object.freeze({store,host,layers,render,install,dispose,diagnostics:', 'window.__themeViewer=viewer;return window.__themeUI=Object.freeze({store,host,layers,render,install,dispose,diagnostics:');return r.fulfill({response:res,body:t});
  }
  if(/\/cfbt\/(lite\/|r8\/|model-info|calculation|reuse\/)|\/models\/(catalog|simulation)/.test(u.pathname)&&!u.pathname.endsWith('.js')&&!u.pathname.includes('/export/')){
   const f=path.join(cache,crypto.createHash('sha256').update(req.url()).digest('hex')+'.json');
   if(fs.existsSync(f)){const v=JSON.parse(fs.readFileSync(f));return r.fulfill({status:v.status,contentType:v.type,body:Buffer.from(v.body,'base64')});}
   const res=await r.fetch();const body=await res.body();fs.writeFileSync(f,JSON.stringify({url:req.url(),status:res.status(),type:res.headers()['content-type']||'application/json',body:body.toString('base64')}));return r.fulfill({response:res,body});
  }
  return r.continue();
 });
 p.on('response',r=>{if(r.status()>=400)report.httpErrors.push({url:r.url(),status:r.status()});});
 await p.goto(url);await p.waitForFunction(()=>window.__themeUI&&document.body.classList.contains('cfbtReady'));await p.waitForTimeout(600);
 return p;
}
async function settle(p){await p.evaluate(async()=>{window.__themeUI.render();for(let i=0;i<12;i++)await new Promise(requestAnimationFrame);});}
async function shot(p,name,canvas=false){await settle(p);
 if(phase==='stage1-paired'){
  const data=JSON.parse(fs.readFileSync(path.join(dir,'tokens.json'))),map={...data.base,...data.compat};
  await p.evaluate(async map=>{window.__pauseRAF=true;await new Promise(r=>setTimeout(r,100));const expand=t=>t.replace(/var\(--([\w-]+)\)/g,(all,k)=>map[k]??all);const restore=[];
   for(const e of document.querySelectorAll('style')){const t=e.textContent;restore.push(()=>e.textContent=t);e.textContent=expand(t);}
   for(const e of document.querySelectorAll('[style]')){const t=e.getAttribute('style');restore.push(()=>e.setAttribute('style',t));e.setAttribute('style',expand(t));}
   for(const link of document.querySelectorAll('link[rel=stylesheet]')){if(!link.href.endsWith('/overlay.css'))continue;const style=document.createElement('style');style.textContent=expand(await(await fetch(link.href)).text());link.after(style);link.disabled=true;restore.push(()=>{style.remove();link.disabled=false;});}
   window.__restoreTheme=()=>{for(const f of restore.reverse())f();};
  },map);
  const beforeDir=path.join(dir,'paired-before');fs.mkdirSync(beforeDir,{recursive:true});await (canvas?p.locator('#v canvas'):p).screenshot({path:path.join(beforeDir,name+'.png')});
  await p.evaluate(()=>__restoreTheme());
 }
 await (canvas?p.locator('#v canvas'):p).screenshot({path:path.join(out,name+'.png')});
 const row=await p.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,tab:document.querySelector('#pyroShellTabs [aria-selected=true]')?.id,floor:__themeUI.store.get('floor'),case:__themeUI.diagnostics().case_id,selection:__themeUI.store.get('selection'),time:__themeUI.store.get('playback').t_s,theme:getComputedStyle(document.documentElement).getPropertyValue('--bg-panel').trim(),status:[...document.querySelectorAll('.status-ok,.status-busy,.status-error')].map(e=>({id:e.id,class:e.className,color:getComputedStyle(e).color})),smallText:[...document.querySelectorAll('#pyroShellSidebar *,#pyroShellHeader *,#sceneResultList *')].filter(e=>e.getClientRects().length&&e.textContent.trim()&&parseFloat(getComputedStyle(e).fontSize)<11).map(e=>({id:e.id,cls:e.className,size:getComputedStyle(e).fontSize}))}));report.scenes.push({name,canvas,...row});if(phase==='stage1-paired')await p.evaluate(()=>__resumeRAF());console.log(name);}
for(const [building,url] of [['hotel','http://127.0.0.1:8842/model.html'],['intech','http://127.0.0.1:8844/model.html'],['wando','http://127.0.0.1:8832/data/wando-coldstore/model.html']]){
 for(const width of [1440,375]){
  const p=await pageFor(url,width,width===375?844:1000);
  await p.evaluate(async building=>{const e=document.getElementById('liteCase');const opt=[...e.options].find(o=>building==='hotel'?o.textContent.includes('5F'):true);if(opt){e.value=opt.value;await e.onchange();}const ui=__themeUI,r=ui.store.get('result');const id=r?.scenario?.origin_room_id;if(id){const room=ui.store.get('building').floors.flatMap(f=>f.rooms).find(r=>r.room_id===id);if(room)ui.store.dispatch('selection/set',{room_id:id,cell_id:room.cells[0]?.cell_id,source:'click'});}ui.store.dispatch('playback/seek',{t_s:1420});},building);
  if(width===375&&await p.locator('#shellMobileToggle').isVisible())await p.locator('#shellMobileToggle').click();
  for(const tab of building==='hotel'?['result','building','display']:['result']){
   await p.locator('#shellTab-'+tab).click();await shot(p,building+'-'+width+'-'+tab);
  }
  if(building==='hotel'&&width===1440&&phase==='stage2'){
   const state=()=>p.evaluate(()=>Object.fromEntries(['layers','realView','openings','risk','displayDetails'].map(k=>[k,__themeUI.store.get(k)])));const beforeState=await state();
   const boxes=p.locator('#shellPane-display input[type=checkbox]');const n=await boxes.count();
   for(let i=0;i<n;i++){const box=boxes.nth(i),id=await box.getAttribute('id'),before=await box.isChecked();await box.evaluate(e=>e.click());await box.evaluate(e=>e.click());const after=await box.isChecked();report.toggles.push({id,before,after});}
   report.toggleStateIdentical=JSON.stringify(beforeState)===JSON.stringify(await state());
   report.light=await p.evaluate(()=>{document.documentElement.setAttribute('data-theme','light');const v=getComputedStyle(document.documentElement);const colors=Object.fromEntries(['--bg-panel','--bg-card','--text','--accent'].map(k=>[k,v.getPropertyValue(k).trim()]));document.documentElement.removeAttribute('data-theme');return colors;});
  }
  await p.close();
 }
}
const p=await pageFor('http://127.0.0.1:8780/cad-result/90d3c325f238a3c4/model.html',1280,720);
for(const [id,t,floor] of [['S06',890,'3F'],['S09',1420,'3F'],['S09',1800,'3F'],['S09',1800,'all']]){
 await p.evaluate(async({id,t,floor})=>{const e=document.getElementById('liteCase');e.value=id;await e.onchange();const s=document.getElementById('shellFloor');if(floor==='all')document.querySelector('#fbtn button').click();else{s.value=floor;s.dispatchEvent(new Event('change'));}__themeUI.store.dispatch('playback/seek',{t_s:t});}, {id,t,floor});
 await shot(p,id+'-'+t+'-'+(floor==='all'?'전체':floor),true);
}
await p.close();
}catch(e){report.fatal=e.stack;console.error(e.stack);process.exitCode=1;}finally{fs.writeFileSync(path.join(out,'capture.json'),JSON.stringify(report,null,2));await browser.close();}})();
