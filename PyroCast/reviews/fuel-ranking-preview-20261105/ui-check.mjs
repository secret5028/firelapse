import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),{chromium}=require('C:/Users/예방/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const file='simulation/config/fuel-quantities/c3f428a9a3bb007bd8d46dc34b8fa71eb29816e6e82b83ff47f448e881747b19.json',saved=fs.readFileSync(file);
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1050}}),errors=[],posts=[],observed=[];page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST')posts.push({url:r.url(),body:r.postData()});});
 await page.route('**/app/web/controller.js',async r=>{const response=await r.fetch();await r.fulfill({response,body:(await response.text()).replace('async function attachModern(viewer,initial,{clock={now:()=>performance.now()}}={}){','async function attachModern(viewer,initial,{clock={now:()=>performance.now()}}={}){window.__fuelCheckViewer=viewer;')});});
 await page.goto('http://127.0.0.1:8842/model.html');await page.locator('#shellTab-building').click();await page.locator('#exploreFloor').selectOption('5F');await page.waitForSelector('#exploreCandidates tr');await page.locator('#top').click();
 const original=await page.locator('#exploreCandidates').innerText();
 const xy=await page.evaluate(()=>{const v=window.__fuelCheckViewer,f=v.B.floors.find(f=>f.name==='5F'),r=f.rooms.find(r=>r.id==='R19');v.C.updateMatrixWorld();const p=new v.THREE.Vector3(r.c[0],r.c[1],f.z+.07).project(v.C),c=document.querySelector('canvas').getBoundingClientRect();return {x:c.x+(p.x+1)*c.width/2,y:c.y+(1-p.y)*c.height/2};});
 await page.mouse.click(xy.x,xy.y);await page.waitForSelector('#fuelSelectedRoom:not([hidden])');assert.match(await page.locator('#fuelRoomName').innerText(),/객실-5/);
 for(const amount of [150,200]){
  await page.locator('#fuelRoomAmount').evaluate((e,n)=>{e.value=n;e.dispatchEvent(new Event('input',{bubbles:true}));},amount);
  await page.waitForFunction(()=>document.getElementById('exploreFuelNotice').textContent==='미저장 변경 · 순위 미리보기');
  const rows=await page.locator('#exploreCandidates tr').allTextContents();const at=rows.findIndex(x=>x.includes('R19'));assert.equal(at,amount===150?4:0);observed.push({amount,rows});
 }
 await page.locator('#exploreCandidates').scrollIntoViewIfNeeded();await page.screenshot({path:'reviews/fuel-ranking-preview-20261105/room5-200-preview.png'});
 // Rapid changes: only the latest draft may be displayed.
 for(const amount of [300,150])await page.locator('#fuelRoomAmount').evaluate((e,n)=>{e.value=n;e.dispatchEvent(new Event('input',{bubbles:true}));},amount);
 await page.waitForFunction(()=>document.getElementById('exploreFuelNotice').textContent==='미저장 변경 · 순위 미리보기');assert.match((await page.locator('#exploreCandidates tr').allTextContents())[4],/R19/);
 await page.locator('#fuelReset').click();await page.waitForFunction(text=>document.getElementById('exploreCandidates').innerText===text,original);assert.deepEqual(fs.readFileSync(file),saved);
 assert(!posts.some(p=>/\/(run|mc)$/.test(p.url)));assert(posts.filter(p=>p.url.endsWith('/fuel-settings')).every(p=>JSON.parse(p.body).preview_floor==='5F'));assert.deepEqual(errors,[]);
 const report={observed,reset_restored:true,settings_unchanged:true,preview_requests:posts.filter(p=>p.url.endsWith('/fuel-settings')).length,simulation_requests:0,errors};fs.writeFileSync('reviews/fuel-ranking-preview-20261105/ui-check.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));
}finally{await browser.close();}
