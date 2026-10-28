import {explanatoryText} from '../web/panels/explanations.js';
import fs from 'node:fs';import path from 'node:path';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),{chromium}=require(process.env.PYROCAST_PLAYWRIGHT||'playwright');
const out=path.resolve('simulation/results/ui_refactor_stage4_item6_20261028');fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const report={scenes:[],errors:[],posts:[]},poses={};let modern,mockScreeningFailure=false,mockDoorFailure=false;const doorFixture=JSON.parse(fs.readFileSync(path.join(out,'doors-fixture.json')));
if(process.env.PYROCAST_REUSE_STAGE3){const old=JSON.parse(fs.readFileSync(path.join(out,'verification.json')));report.stage3Text=old.stage3Text;report.legacy=old.legacy;report.scenes=old.scenes.filter(r=>process.env.PYROCAST_REUSE_VISUALS||r.mode==='stage3');for(const r of report.scenes)poses[r.name]=r.pose;}
const save=()=>fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify(report,null,2));
try{
 for(const mode of process.env.PYROCAST_REUSE_STAGE3?['modern','legacy']:['stage3','modern','legacy']){
  const page=await browser.newPage({viewport:{width:1440,height:1080},deviceScaleFactor:1,colorScheme:'dark',hasTouch:true});page.setDefaultTimeout(120000);page.on('pageerror',e=>report.errors.push({mode,error:e.message}));
  await page.addInitScript(()=>{window.__clock=180000;performance.now=()=>window.__clock;const raf=requestAnimationFrame;window.requestAnimationFrame=cb=>raf(()=>cb(window.__clock));window.__fetches=0;const f=fetch;window.fetch=(...a)=>{window.__fetches++;return f(...a);};});
  await page.route('**/*',async route=>{const req=route.request(),url=new URL(req.url());if(req.method()!=='GET'&&url.pathname==='/cfbt/lite/doors'){const body=req.postDataJSON();report.posts.push({path:url.pathname,body});if(mockDoorFailure)return route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({error:'save fixture error'})});const r=doorFixture.rows.find(r=>r.id===body.id);r.door_class=body.door_class;r.confidence='user';r.reason='사용자 저장값 우선';return route.fulfill({contentType:'application/json',body:JSON.stringify(doorFixture)});}
   if(req.method()!=='GET'){report.posts.push({path:url.pathname,body:req.postDataJSON()});if(mockScreeningFailure&&url.pathname==='/cfbt/lite/screening')return route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({error:'busy fixture'})});return route.fulfill({status:202,contentType:'application/json',body:JSON.stringify({started:true,workers:1,MC_started:false})});}
   if(mode==='modern'&&url.pathname==='/cfbt/lite/doors')return route.fulfill({contentType:'application/json',body:JSON.stringify(doorFixture)});
   if(mode==='stage3'&&url.pathname==='/cfbt/overlay.js')return route.fulfill({body:fs.readFileSync(path.join(out,'previous-overlay.js')),contentType:'text/javascript'});
   if(url.pathname==='/cfbt/lite/active.json'){const r=await route.fetch({url:'http://127.0.0.1:8780/cfbt/lite/result/S09'});return route.fulfill({response:r});}
   if(url.pathname.endsWith('/model.html')){const r=await route.fetch();let h=await r.text(),hook='await (await import("/cfbt/overlay.js")).attach({',i=h.indexOf(hook),j=h.indexOf('\n</script>',i),old=h.slice(i,j),arg=old.slice(hook.length-1,old.lastIndexOf(');'));assert(i>=0);h=h.slice(0,i)+'window.__cad='+arg+';window.__ui=await (await import("/cfbt/overlay.js")).attach(window.__cad);window.__ready=true;'+h.slice(j);return route.fulfill({response:r,body:h});}return route.continue();});
  await page.goto('http://127.0.0.1:8780/cad-result/d018b4bb75da4475b1fd75447603c1a0/model.html'+(mode==='legacy'?'?ui=legacy':''));await page.waitForFunction(()=>window.__ready);await page.evaluate(()=>$('reviewClose').click()).catch(()=>page.evaluate(()=>document.getElementById('reviewClose').click()));
  const settle=()=>page.evaluate(async()=>{await document.fonts.ready;for(let i=0;i<5;i++)await new Promise(requestAnimationFrame);});await settle();
  if(mode==='legacy'){
   report.legacy=await page.evaluate(()=>({shell:!!document.getElementById('pyroShellSidebar'),canvas:document.querySelectorAll('#v canvas').length,legend:document.querySelectorAll('#cfMeaning').length,panel:!!document.getElementById('liteCase')}));
   assert.deepEqual(report.legacy,{shell:false,canvas:1,legend:1,panel:true});
   await page.evaluate(()=>{document.getElementById('liteTime').value=1420;document.getElementById('liteTime').oninput();});await settle();await page.screenshot({path:path.join(out,'legacy.png')});await page.close();continue;
  }
  report[mode+'Text']=await page.evaluate(()=>{
   const entries=[];for(const root of document.querySelectorAll('#pyroShellSidebar,.compactHUD,#cfMeaning,#pyroShellTimeline,.viewHint')){
    const walk=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);while(walk.nextNode()){const n=walk.currentNode,p=n.parentElement,t=n.textContent.trim();if(!t||p.closest('[data-tip],#resultLimits,#cfbtPanel,style,script,option')||p.closest('#displayLegend small,#cfPlumeNumbers'))continue;entries.push({id:p.id||p.closest('[id]')?.id,tag:p.tagName,text:t});}
   }return entries;
  });save();
  if(mode==='modern'){modern=page;report.initial=await page.evaluate(()=>({operations:window.__ui.store.get('layers').operations,toggle:document.getElementById('displayOperations').checked,risks:[...document.querySelectorAll('#displayRisks input')].map(e=>e.id)}));assert.equal(report.initial.operations,false);assert.equal(report.initial.toggle,false);assert.equal(report.initial.risks.length,5);}

  for(const s of process.env.PYROCAST_REUSE_VISUALS?[]:[{name:'S09-1800',id:'S09',time:1800},{name:'S09-1420',id:'S09',time:1420},{name:'S06-890',id:'S06',time:890},{name:'all-core',id:'S09',time:1800,all:true}]){
   await page.evaluate(async s=>{const $=id=>document.getElementById(id);if($('liteCase').value!==s.id){$('liteCase').value=s.id;await $('liteCase').onchange();}$('liteRoom').value='CAD_3F_R2_C0';$('liteRoom').onchange();$('liteTime').value=s.time;$('liteTime').oninput();$('liteCores').checked=true;$('liteCores').onchange();if(s.all)$('liteBuilding').click();else{[...$('fbtn').children].find(b=>b.textContent==='3F').click();$('liteWhole').click();}},s);await settle();
   const counts=await page.evaluate(()=>{const ui=window.__ui,sel=ui.layers.find(l=>l.constructor.id==='selection'),planes=sel.getPickPlanes();ui.render();const normal=window.__cad.R.info.render.calls;const masks=planes.map(p=>p.layers.mask);planes.forEach(p=>p.layers.set(0));ui.render();const unmasked=window.__cad.R.info.render.calls;planes.forEach(p=>p.layers.set(31));ui.render();const masked=window.__cad.R.info.render.calls;planes.forEach((p,i)=>p.layers.mask=masks[i]);return {normal,unmasked,masked,removed:unmasked-masked,planes:planes.length,cameraMask:window.__cad.C.layers.mask};});assert.equal(counts.removed,76);if(mode==='modern')assert.equal(counts.normal,counts.masked);
   // Compare renderer pixels at equal dimensions/pose. The shell intentionally changes viewport geometry.
   await page.evaluate(()=>{let st=document.getElementById('comparisonViewport');if(!st){st=document.createElement('style');st.id='comparisonViewport';document.head.append(st);}st.textContent='body #v,body.pyroShell #v{position:fixed!important;left:0!important;top:0!important;right:auto!important;bottom:auto!important;width:1000px!important;height:600px!important}';});await settle();
   if(mode==='stage3'){await page.evaluate(s=>document.getElementById(s.all?'liteBuilding':'liteWhole').click(),s);await settle();poses[s.name]=await page.evaluate(()=>({p:window.__cad.C.position.toArray().map(v=>+v.toFixed(10)),q:window.__cad.C.quaternion.toArray().map(v=>+v.toFixed(10)),target:window.__cad.O.target.toArray().map(v=>+v.toFixed(10)),zoom:window.__cad.C.zoom}));}
   const snap=await page.evaluate(pose=>{const ref=document.getElementById('layer_reference');ref.checked=false;ref.onchange?.();const {C,O,R}=window.__cad,ui=window.__ui;C.position.fromArray(pose.p);C.quaternion.fromArray(pose.q);C.zoom=pose.zoom;O.target.fromArray(pose.target);O.update();C.updateProjectionMatrix();ui.store.dispatch('layers/toggle',{id:'risk',visible:true});ui.render();return R.domElement.toDataURL('image/png');},poses[s.name]);fs.writeFileSync(path.join(out,`${s.name}-${mode}-3d.png`),Buffer.from(snap.split(',')[1],'base64'));
   report.scenes.push({mode,name:s.name,counts,pose:poses[s.name]});save();await page.evaluate(()=>{document.getElementById('comparisonViewport').remove();window.__ui.store.dispatch('layers/toggle',{id:'risk',visible:true});});await settle();
  }
  if(mode==='stage3')await page.close();
 }

 await modern.evaluate(async()=>{const $=id=>document.getElementById(id);$('liteCase').value='S09';await $('liteCase').onchange();[...$('fbtn').children].find(b=>b.textContent==='3F').click();$('liteRoom').value='CAD_3F_R2_C0';$('liteRoom').onchange();$('liteTime').value=1420;$('liteTime').oninput();$('liteWhole').click();$('shellTab-display').click();window.__ui.render();});


 report.remainingExplanations=report.modernText.filter(e=>explanatoryText(e.text)&&e.id!=='reviewCopy2_ck'&&e.tag!=='BUTTON');assert.deepEqual(report.remainingExplanations,[]);
 // All four tabs at desktop and a phone-sized viewport; no rendering settings change.
 for(const [size,width,height] of [['desktop',1440,1080],['mobile',390,844]]){
  await modern.setViewportSize({width,height});if(size==='mobile')await modern.click('#shellMobileToggle');
  for(const tab of ['building','explore','result','display']){
   await modern.click('#shellTab-'+tab);await modern.evaluate(tab=>{document.getElementById('shellPane-'+tab).scrollTop=0;document.querySelectorAll('#pyroShellSidebar details').forEach(e=>e.open=false);},tab);
   await modern.screenshot({path:path.join(out,tab+'-'+size+'.png')});
  }
 }
 await modern.setViewportSize({width:1440,height:1080});await modern.click('#shellTab-display');
 const state=await modern.evaluate(()=>window.__ui.store.get('risk').show);
 for(const id of report.initial.risks){await modern.locator('#'+id).click();await modern.locator('#'+id).click();}
 assert.deepEqual(await modern.evaluate(()=>window.__ui.store.get('risk').show),state);report.riskRoundtrip=true;
 // Error feedback is intentionally retained outside help.
 await modern.fill('#displayCaution','200');await modern.locator('#displayCaution').dispatchEvent('change');assert.equal(await modern.locator('#displayError').textContent(),'0 이상이며 주의 ≤ 테두리로 입력하세요.');
 await modern.fill('#displayCaution','70');await modern.locator('#displayCaution').dispatchEvent('change');
 const tip=modern.locator('#shellPane-display [data-tip]').first();await tip.focus();assert(await modern.locator('#panelTipPopover').isVisible());await modern.keyboard.press('Escape');assert(!(await modern.locator('#panelTipPopover').isVisible()));report.tipKeyboard=true;
 // A refreshed frozen module must get the same migration without touching its source.
 await modern.evaluate(()=>{const p=document.createElement('p');p.id='auditRefresh';p.textContent='동적 갱신 설명입니다.';document.getElementById('exploreRuleMount').append(p);});await modern.waitForFunction(()=>!!document.querySelector('#auditRefresh [data-tip]'));await modern.evaluate(()=>document.getElementById('auditRefresh').remove());report.dynamicMigration=true;
 report.tips=await modern.locator('#pyroShellSidebar [data-tip]').evaluateAll(rows=>rows.map(e=>({id:e.parentElement.id,text:e.dataset.tip})));
 await modern.evaluate(()=>window.__ui.dispose());report.dispose=await modern.evaluate(()=>({dom:document.querySelectorAll('#panelTipPopover,style[data-pyrocast-explanations]').length,subscriptions:window.__ui.store.diagnostics().subscriptions,resources:window.__ui.layers.reduce((n,l)=>n+(l.resources?.size||0),0)}));assert.deepEqual(report.dispose,{dom:0,subscriptions:0,resources:0});assert.deepEqual(report.errors,[]);assert.equal(report.posts.length,0);save();console.log(JSON.stringify({scenes:report.scenes.length,initial:report.initial,legacy:report.legacy,dispose:report.dispose,errors:report.errors}));
}finally{save();await browser.close();}
