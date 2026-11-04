import {createRequire} from 'node:module';
import fs from 'node:fs';import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.PYROCAST_PLAYWRIGHT);
const out='reviews/model-library-dedup-20261104';fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true,args:['--disable-gpu-sandbox']});
const errors=[],rows=[];
try{
 const page=await browser.newPage({viewport:{width:1440,height:960}});page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8841/models/?id=parkmarine');
 const c=await(await page.request.get('http://127.0.0.1:8841/models/catalog.json')).json();assert.equal(c.models.length,6);
 for(const e of c.models){
  await page.locator('#model').selectOption(e.id);
  await page.waitForFunction(id=>window.__modelLibrary?.ready&&window.__modelLibrary.id===id,e.id,{timeout:60000});
  assert.equal(await page.locator('#error').textContent(),'');assert.equal(await page.locator('canvas').count(),1);
  assert.equal(await page.locator('#floor option').count(),e.floor_count+1);
  if(e.execution_mode==='library_lite')await page.waitForFunction(()=>!document.querySelector('#run').disabled,null,{timeout:60000});
  assert.equal(await page.locator('#run').isEnabled(),e.simulation_enabled);
  if(e.source_kind==='scan')assert.match(await page.locator('#reason').textContent(),/시뮬레이션 금지/);
  const first=await page.locator('#floor option').nth(1).getAttribute('value');await page.locator('#floor').selectOption(first);await page.locator('#top').click();
  await page.locator('#floor').selectOption('all');await page.locator('#iso').click();
  if(['parkmarine','apartment-scan','modori-scan','ganghwa'].includes(e.id))await page.screenshot({path:`${out}/${e.id}.png`});
  rows.push({id:e.id,floors:e.floor_count,simulation_enabled:await page.locator('#run').isEnabled(),loaded:true});
 }
 for(const path of ['/cfbt/run','/cfbt/ignite','/cfbt/r8/run','/cfbt/lite/screening','/cfbt/lite/mc']){
  const r=await page.request.post('http://127.0.0.1:8841'+path,{data:{building:'apartment-scan',run:true}});assert.equal(r.status(),403);assert.equal((await r.json()).simulation_started,false);
 }
 for(const path of ['/.git/config','/config/ai.json','/data/','/models/../../../config/ai.json','/models/unknown/building.json'])assert.equal((await page.request.get('http://127.0.0.1:8841'+path)).status(),404);
 const operating=[];
 for(const url of ['http://127.0.0.1:8780/model.html','http://127.0.0.1:8832/data/wando-coldstore/model.html']){
  const p=await browser.newPage();p.on('pageerror',e=>errors.push(e.message));await p.goto(url);await p.waitForFunction(()=>document.querySelector('#shellBuilding')?.options.length===6,null,{timeout:60000});
  operating.push({url,models:await p.locator('#shellBuilding option').count()});await p.close();
 }
 await page.locator('#model').selectOption('parkmarine');await page.waitForFunction(()=>window.__modelLibrary?.id==='parkmarine'&&window.__modelLibrary.ready);await page.setViewportSize({width:390,height:844});await page.screenshot({path:out+'/mobile.png'});
 assert.deepEqual(errors,[]);fs.writeFileSync(out+'/verification.json',JSON.stringify({rows,operating,blocked_run_routes:5,errors,simulation_runs:0},null,2));console.log('PASS 6 models, scan POST blocked, operating selectors 6, JS errors 0');
}finally{await browser.close()}
