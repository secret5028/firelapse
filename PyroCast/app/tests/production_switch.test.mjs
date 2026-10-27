import fs from 'node:fs';import path from 'node:path';import {fileURLToPath} from 'node:url';import {createRequire} from 'node:module';import assert from 'node:assert/strict';import {createHash} from 'node:crypto';
const require=createRequire(import.meta.url),{chromium}=require(process.env.PYROCAST_PLAYWRIGHT||'playwright');
const root=fileURLToPath(new URL('../../',import.meta.url)),out=path.join(root,'simulation/results/ui_refactor_production_20261028');fs.mkdirSync(out,{recursive:true});
const url='http://127.0.0.1:8780/cad-result/d018b4bb75da4475b1fd75447603c1a0/model.html';
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-background-timer-throttling','--disable-renderer-backgrounding']});
const report={modes:[],playback_wall_target_s:60};
const reusedLegacy=process.env.PYROCAST_REUSE_LEGACY?JSON.parse(fs.readFileSync(process.env.PYROCAST_REUSE_LEGACY,'utf8')).modes.find(m=>m.mode==='legacy'):null;
const save=()=>fs.writeFileSync(path.join(out,'regression.json'),JSON.stringify(report,null,2));
function probe(){
 const {S,R}=window.__cad;const nodes=new Set(),baseResources=new Set(),tracked=new Map();
 function resources(o){const r=[o.geometry];for(const m of Array.isArray(o.material)?o.material:o.material?[o.material]:[]){r.push(m);for(const x of Object.values(m))if(x?.isTexture)r.push(x);for(const x of Object.values(m.uniforms||{}))if(x.value?.isTexture)r.push(x.value);}return r.filter(Boolean);}
 S.traverse(o=>{nodes.add(o);for(const r of resources(o))baseResources.add(r);});
 const native=o=>{for(let n=o;n&&n!==S;n=n.parent)if(nodes.has(n))return true;return false;};
 const render=R.render;window.__before={nodes,baseResources,render,links:new Set(document.querySelectorAll('link'))};
 window.__collect=()=>{S.traverse(o=>{if(native(o))return;for(const r of resources(o))if(!baseResources.has(r)&&!tracked.has(r)){tracked.set(r,0);r.addEventListener('dispose',()=>tracked.set(r,tracked.get(r)+1));}});};
 window.__disposeStats=()=>{const remaining=[];S.traverse(o=>{if(!nodes.has(o)&&!native(o))remaining.push(o.name||o.type);});return {remaining_scene_objects:remaining,tracked_resources:tracked.size,undisposed_resources:[...tracked].filter(([r,n])=>!n).map(([r])=>r.type||r.constructor.name),subscriptions:window.__ui.store.diagnostics().subscriptions,layers:window.__ui.layers.map(l=>({id:l.constructor.id,state:l.state,resources:l.resources?.size??l.diagnostics?.().resources??0})),host:window.__ui.host.diagnostics(),render_restored:R.render===render,remaining_panels:document.querySelectorAll('#cfbtPanel,#pyroMenuReview,.cfbtSceneCaption,#cfMeaning,#cfPlumeLegend').length,extra_links:[...document.querySelectorAll('link')].filter(l=>!window.__before.links.has(l)).map(l=>l.href),active_intervals:[...window.__intervals.keys()],connected_listener_leaks:[...window.__listeners].filter(r=>!window.__listenersBefore.has(r)&&(r.target===window||r.target===document||r.target.isConnected)).map(r=>r.type)};};
 window.__listenersBefore=new Set(window.__listeners);
}
try{
 for(const mode of reusedLegacy?['modern']:['modern','legacy']){
  const page=await browser.newPage({viewport:{width:1440,height:1080},deviceScaleFactor:1,colorScheme:'dark'}),row={mode,errors:[],checks:[]};report.modes.push(row);page.setDefaultTimeout(120000);page.on('pageerror',e=>row.errors.push(e.message));
  await page.addInitScript(()=>{
   window.__fetches=[];const fetch0=window.fetch;window.fetch=async(...args)=>{const r={url:new URL(typeof args[0]==='string'?args[0]:args[0].url,location.href).pathname};window.__fetches.push(r);const res=await fetch0(...args);r.status=res.status;return res;};
   window.__intervals=new Map();const si=setInterval,ci=clearInterval;window.setInterval=(f,ms,...a)=>{const id=si(f,ms,...a);window.__intervals.set(id,ms);return id;};window.clearInterval=id=>{window.__intervals.delete(id);ci(id);};
   window.__listeners=new Set();const add=EventTarget.prototype.addEventListener,remove=EventTarget.prototype.removeEventListener;
   EventTarget.prototype.addEventListener=function(type,fn,opt){const capture=typeof opt==='boolean'?opt:!!opt?.capture;if(![...window.__listeners].some(r=>r.target===this&&r.type===type&&r.fn===fn&&r.capture===capture))window.__listeners.add({target:this,type,fn,capture});return add.call(this,type,fn,opt);};
   EventTarget.prototype.removeEventListener=function(type,fn,opt){const capture=typeof opt==='boolean'?opt:!!opt?.capture;for(const r of window.__listeners)if(r.target===this&&r.type===type&&r.fn===fn&&r.capture===capture)window.__listeners.delete(r);return remove.call(this,type,fn,opt);};
  });
  await page.route('**/*',async route=>{if(route.request().method()!=='GET')return route.fulfill({status:403,body:'Regression: no writes'});
   if(new URL(route.request().url()).pathname.endsWith('/model.html')){const r=await route.fetch();let html=await r.text(),hook='await (await import("/cfbt/overlay.js")).attach({',i=html.indexOf(hook),j=html.indexOf('\n</script>',i),old=html.slice(i,j),arg=old.slice(hook.length-1,old.lastIndexOf(');'));assert(i>=0);
    html=html.slice(0,i)+'window.__cad='+arg+';('+probe.toString()+')();window.__ui=await (await import("/cfbt/overlay.js")).attach(window.__cad);window.__ready=true;'+html.slice(j);return route.fulfill({response:r,body:html});}
   return route.continue();});
  await page.goto(url+(mode==='legacy'?'?ui=legacy':''));await page.waitForFunction(()=>window.__ready&&document.body.classList.contains('cfbtReady'));
  row.entry=await page.evaluate(()=>({ui:document.documentElement.dataset.pyrocastUi,canvas:document.querySelectorAll('#v canvas').length,legend:document.querySelectorAll('#cfMeaning').length,fetches:window.__fetches.length}));assert.equal(row.entry.ui,mode);assert.equal(row.entry.canvas,1);assert.equal(row.entry.legend,1);
  await page.evaluate(()=>document.getElementById('reviewClose').click());
  const settle=async()=>page.evaluate(async()=>{for(let i=0;i<3;i++)await new Promise(requestAnimationFrame);window.__collect();});
  const mark=async(name,action)=>{const start=await page.evaluate(()=>window.__fetches.length);const data=await action();await settle();const visibility_diff=await page.evaluate(()=>{const b=window.__ui?.layers?.find(l=>l.constructor.id==='building');if(!b)return null;const visible=o=>{for(let n=o;n;n=n.parent)if(!n.visible)return false;return true;};return [...b.sourceObjects].filter(([a,c])=>visible(a)!==visible(c)).length;});row.checks.push({name,fetches:await page.evaluate(()=>window.__fetches.length)-start,data,visibility_diff});save();};
  for(const id of ['S06','S09','S06','S09'])await mark('case '+id,()=>page.evaluate(async id=>{const e=document.getElementById('liteCase');e.value=id;await e.onchange();return {selected:e.value,rooms:document.getElementById('liteRoom').options.length};},id));
  await page.evaluate(()=>{const e=document.getElementById('liteTime');e.value=1800;e.oninput();});
  for(const name of await page.locator('#fbtn button').allTextContents())await mark('floor '+name,()=>page.evaluate(name=>{const {C,O}=window.__cad,before=[...C.position.toArray(),...O.target.toArray(),C.zoom];[...document.querySelector('#fbtn').children].find(x=>x.textContent===name).click();const after=[...C.position.toArray(),...O.target.toArray(),C.zoom];if(JSON.stringify(before)!==JSON.stringify(after))throw Error('Floor camera changed');return {floor:window.__cad.getFloor(),camera_unchanged:true};},name));
  await page.evaluate(()=>[...document.querySelector('#fbtn').children].find(x=>x.textContent==='3F').click());
  const cadToggles=await page.locator('#p input[type=checkbox]').evaluateAll(es=>es.filter(e=>e.id&&!['ddir','ramp_reverse'].includes(e.id)).map(e=>({id:e.id,checked:e.checked})));
  for(const {id,checked} of cadToggles){for(const on of [false,true])await mark(`CAD ${id} ${on}`,()=>page.evaluate(([id,on])=>{const e=document.getElementById(id);e.checked=on;e.dispatchEvent(new Event('change',{bubbles:true}));e.dispatchEvent(new Event('input',{bubbles:true}));return {checked:e.checked};},[id,on]));await page.evaluate(([id,checked])=>{const e=document.getElementById(id);e.checked=checked;e.dispatchEvent(new Event('change',{bubbles:true}));e.dispatchEvent(new Event('input',{bubbles:true}));},[id,checked]);}
  for(const id of await page.locator('#cfbtPanel input[type=checkbox]').evaluateAll(es=>es.map(e=>e.id)))for(const on of [false,true])await mark(`${id} ${on}`,()=>page.evaluate(([id,on])=>{const e=document.getElementById(id);e.checked=on;e.onchange();return {checked:e.checked,store:window.__ui?.store?.get('layers')};},[id,on]));
  for(let i=0;i<2;i++)await mark('real toggle',()=>page.evaluate(()=>{const e=document.getElementById('liteReal');e.click();return e.getAttribute('aria-pressed');}));
  for(const value of ['.15','.4','1'])await mark('opacity '+value,()=>page.evaluate(v=>{const e=document.getElementById('liteOpacity');e.value=v;e.onchange();return e.value;},value));
  for(const id of ['liteFocus','liteFireFocus','liteWhole','liteBuilding'])await mark(id,()=>page.evaluate(id=>{document.getElementById(id).click();return {position:window.__cad.C.position.toArray(),target:window.__cad.O.target.toArray()};},id));
  for(const size of [{width:1100,height:850},{width:1440,height:1080}])await mark('resize',async()=>{await page.setViewportSize(size);await settle();return page.evaluate(()=>({width:window.__cad.R.domElement.width,height:window.__cad.R.domElement.height,aspect:window.__cad.C.aspect}));});
  await page.evaluate(()=>{[...document.querySelector('#fbtn').children].find(x=>x.textContent==='3F').click();document.getElementById('liteWhole').click();});await settle();
  if(mode==='legacy')await page.screenshot({path:path.join(out,'legacy-live.png'),fullPage:true});else await page.screenshot({path:path.join(out,'modern-live.png'),fullPage:true});
  row.playback=[];
  for(const speed of [1,20]){
   await page.evaluate(speed=>{const t=document.getElementById('liteTime');t.value=0;t.oninput();const s=document.getElementById('liteSpeed');s.value=speed;s.onchange?.();document.getElementById('litePlay').click();},speed);
   const start=Date.now(),fetchStart=await page.evaluate(()=>window.__fetches.length);console.log(mode+' playback '+speed+'x started');
   await page.waitForTimeout(30000);console.log(mode+' playback '+speed+'x 30s');await page.waitForTimeout(30000);
   const state=await page.evaluate(()=>{document.getElementById('litePlay').click();return {t_s:+document.getElementById('liteTime').value,fetches:window.__fetches.length};});row.playback.push({speed,wall_s:(Date.now()-start)/1000,t_s:state.t_s,fetches:state.fetches-fetchStart});save();console.log(JSON.stringify(row.playback.at(-1)));
  }
  row.fetches=await page.evaluate(()=>window.__fetches);row.fetch_count=row.fetches.length;
  if(mode==='modern'){await page.evaluate(()=>{window.__collect();window.__ui.dispose();});await page.waitForTimeout(300);row.dispose=await page.evaluate(()=>window.__disposeStats());}
  save();await page.close();console.log(mode+' complete '+JSON.stringify({errors:row.errors,fetches:row.fetch_count,remaining:row.dispose?.remaining_scene_objects.length,resources:row.dispose?.undisposed_resources.length}));
 }
 if(reusedLegacy){report.modes.push(reusedLegacy);report.legacy_reused_from=process.env.PYROCAST_REUSE_LEGACY;}
 report.fetch_equal=JSON.stringify(report.modes[0].fetches)===JSON.stringify(report.modes[1].fetches);report.served_bundle_sha256=createHash('sha256').update(fs.readFileSync(path.join(root,'simulation/viewer/overlay.js'))).digest('hex');save();
 assert(report.modes.every(r=>r.errors.length===0),'Browser errors');assert(report.fetch_equal,'Fetch sequence mismatch');assert(report.modes[0].checks.every(c=>c.visibility_diff===0),'CAD visibility mismatch');
 for(const r of report.modes){assert(r.checks.every(c=>c.fetches===(c.name.startsWith('case ')?1:0)),'Unexpected control fetch');for(const p of r.playback){assert.equal(p.fetches,0);assert(Math.abs(p.t_s-60*p.speed)<=10,'Playback outside one saved sample');}}
 const d=report.modes[0].dispose;assert.equal(d.remaining_scene_objects.length,0);assert.equal(d.undisposed_resources.length,0);assert.equal(d.subscriptions,0);assert.equal(d.remaining_panels,0);assert.equal(d.extra_links.length,0);assert.equal(d.active_intervals.length,0);assert.equal(d.connected_listener_leaks.length,0);assert(d.render_restored);assert(d.layers.every(l=>l.resources===0));
 console.log('PASS');
}finally{save();await browser.close();}
