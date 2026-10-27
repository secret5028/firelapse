import fs from 'node:fs';import path from 'node:path';import {fileURLToPath} from 'node:url';import {createRequire} from 'node:module';import {execFileSync} from 'node:child_process';
const require=createRequire(import.meta.url),{chromium}=require(process.env.PYROCAST_PLAYWRIGHT||'playwright');
const root=fileURLToPath(new URL('../../',import.meta.url)),out=path.join(root,'simulation/results/ui_refactor_stage3_switchover_20261027');
const origin='http://127.0.0.1:8780',url=origin+'/cad-result/d018b4bb75da4475b1fd75447603c1a0/model.html';
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const reports=[],pages=[];
try{
 for(const mode of ['legacy','modern']){
  const page=await browser.newPage({viewport:{width:1440,height:1080},deviceScaleFactor:1,colorScheme:'dark'}),errors=[];pages.push({mode,page,errors});page.setDefaultTimeout(120000);
  page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{performance.now=()=>180000;const raf=window.requestAnimationFrame.bind(window);window.requestAnimationFrame=cb=>raf(()=>cb(180000));});
  await page.route('**/*',async route=>{
   const req=route.request(),u=new URL(req.url());if(req.method()!=='GET'){await route.fulfill({status:403,body:'Read-only capture'});return;}
   if(u.pathname==='/cfbt/overlay.js')return route.fulfill({body:fs.readFileSync(path.join(out,'overlay.js')),contentType:'text/javascript'});
   if(u.pathname==='/cfbt/lite/active.json'){const r=await route.fetch({url:origin+'/cfbt/lite/result/S09'});return route.fulfill({response:r});}
   if(u.pathname.endsWith('/model.html')){const r=await route.fetch();let html=await r.text();html=html.replace('await (await import("/cfbt/overlay.js")).attach({','window.__ui = await (await import("/cfbt/overlay.js")).attach(window.__cad={');html=html.replace('}});\n</script>','}});window.__uiReady=true;\n</script>');return route.fulfill({response:r,body:html});}
   return route.continue();
  });
  await page.goto(url+(mode==='legacy'?'?ui=legacy':''));
  await page.waitForFunction(()=>document.body.classList.contains('cfbtReady'));
  if(errors.length)throw Error(mode+': '+errors.join('; '));
  await page.evaluate(()=>{document.querySelector('#reviewClose').click();});
 }
 const s06=JSON.parse(fs.readFileSync(path.join(root,'simulation/results/lite_v8_mc_R2_10_20261026/S06/playback.json')));
 const first=Math.min(...Object.values(s06.solvers).map(s=>s.display_v8.color.indexOf('#ef4444')).filter(i=>i>=0)),foTime=s06.time_s[first+1];
 const scenarios=[{name:'S09-1800',caseId:'S09',time:1800},{name:'S09-1420',caseId:'S09',time:1420},{name:'S06-FO',caseId:'S06',time:foTime},{name:'all-core',caseId:'S09',time:1800,all:true}];
 for(const scenario of scenarios){const row={...scenario};
  for(const {mode,page,errors} of pages){
   await page.evaluate(async s=>{
    const $=id=>document.getElementById(id);if($('liteCase').value!==s.caseId){$('liteCase').value=s.caseId;await $('liteCase').onchange();}
    const selected=[...$('liteRoom').options].find(x=>x.value==='CAD_3F_R2_C0')||[...$('liteRoom').options].find(x=>x.value==='CAD_3F_R2');$('liteRoom').value=selected.value;$('liteRoom').onchange();
    $('liteTime').value=s.time;$('liteTime').oninput();$('liteCores').checked=true;$('liteCores').onchange();
    if(s.all)$('liteBuilding').click();else{[...$('fbtn').children].find(b=>b.textContent==='3F').click();$('liteWhole').click();}
    await document.fonts.ready;for(let i=0;i<6;i++)await new Promise(requestAnimationFrame);
   },scenario);
   row[mode]=await page.evaluate(()=>({panel:document.querySelector('#cfbtPanel').innerHTML,caption:document.querySelector('.cfbtSceneCaption').textContent,canvas:document.querySelectorAll('#v canvas').length,legend:document.querySelectorAll('#cfMeaning').length,pose:{position:window.__cad.C.position.toArray(),target:window.__cad.O.target.toArray(),zoom:window.__cad.C.zoom},ui:document.documentElement.dataset.pyrocastUi,diagnostics:window.__ui?.diagnostics?.()}));
   if(errors.length)throw Error(mode+': '+errors.join('; '));
   await page.screenshot({path:path.join(out,`${scenario.name}-${mode}.png`),fullPage:true});
  }
  const diff=JSON.parse(execFileSync(process.env.PYROCAST_PYTHON||'python',['app/tests/compare_switchover.py',scenario.name],{cwd:root,encoding:'utf8'}));row.diff=diff;
  reports.push(row);fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify({reports},null,2));
  console.log(JSON.stringify({name:scenario.name,diff,panel_equal:row.legacy.panel===row.modern.panel,camera_equal:JSON.stringify(row.legacy.pose)===JSON.stringify(row.modern.pose)}));
  if(scenario.caseId==='S06'&&diff.changed_pixels)throw Error('S06 DIFFERENCE: stop; no fallback restoration');
 }
}finally{await browser.close();}
