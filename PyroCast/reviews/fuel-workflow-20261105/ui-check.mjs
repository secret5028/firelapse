import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),{chromium}=require('C:/Users/예방/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const out='reviews/fuel-workflow-20261105/';
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],posts=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST')posts.push(r.url());});
 await page.route('**/app/web/controller.js',async r=>{const response=await r.fetch();let text=await response.text();text=text.replace('async function attachModern(viewer,initial,{clock={now:()=>performance.now()}}={}){','async function attachModern(viewer,initial,{clock={now:()=>performance.now()}}={}){ window.__fuelCheckViewer=viewer;');await r.fulfill({response,body:text});});
 await page.route('**/app/web/layers/fuel_quantity.js',async r=>{const response=await r.fetch();await r.fulfill({response,body:(await response.text()).replace('setData(frame){super.setData(frame);','setData(frame){window.__fuelLayer=this;super.setData(frame);')});});
 await page.goto('http://127.0.0.1:8842/model.html');await page.waitForSelector('#shellTab-building');await page.locator('#shellTab-building').click();await page.locator('#exploreFloor').selectOption('5F');await page.waitForSelector('#fuelSettings:not([hidden])');await page.locator('#top').click();
 await page.waitForFunction(()=>window.__fuelLayer?.floors?.some(f=>f.floor==='5F'));
 const sizes=()=>page.evaluate(()=>{const layer=window.__fuelLayer,f=layer.floors.find(f=>f.floor==='5F'),out={};f.units.forEach((u,i)=>{out[u.id]=f.mesh.instanceMatrix.array[i*16];});return out;});
 const set=async(id,n)=>{await page.locator(id).evaluate((e,n)=>{e.value=n;e.dispatchEvent(new Event('input',{bubbles:true}));},n);await page.waitForTimeout(150);};
 const before=await sizes();await set('#fuelFloorAmount',200);const after=await sizes(),changed=Object.keys(before).filter(id=>Math.abs(before[id]-after[id])>1e-6);
 assert.equal(changed.length,Object.keys(before).length);assert.equal(await page.locator('#fuelFloorType').count(),0);assert.match(await page.locator('#exploreFuelNotice').innerText(),/변경 저장 후/);
 const xy=await page.evaluate(()=>{const v=window.__fuelCheckViewer,f=v.B.floors.find(f=>f.name==='5F'),r=f.rooms.find(r=>r.id==='R20');v.C.updateMatrixWorld();const p=new v.THREE.Vector3(r.c[0],r.c[1],f.z+.07).project(v.C),c=document.querySelector('canvas').getBoundingClientRect();return {x:c.x+(p.x+1)*c.width/2,y:c.y+(1-p.y)*c.height/2};});
 await page.mouse.click(xy.x,xy.y);await page.waitForSelector('#fuelSelectedRoom:not([hidden])');assert.match(await page.locator('#fuelRoomName').innerText(),/R20/);
 await set('#fuelRoomAmount',120);const explicit=(await sizes()).CAD_5F_R20;await set('#fuelFloorAmount',300);assert.equal((await sizes()).CAD_5F_R20,explicit);
 await page.locator('#fuelSearch').fill('객실');assert.equal(await page.locator('#fuelSearchResults button').count(),1);await page.locator('#fuelSearchResults button').click();
 await page.locator('#fuelSettings').scrollIntoViewIfNeeded();await page.screenshot({path:out+'hotel-floor-room.png'});
 const info={rooms:Object.keys(before).length,changed:changed.length,before,after,room_protected:'CAD_5F_R20',indent:await page.locator('#fuelSelectedRoom').evaluate(e=>getComputedStyle(e).paddingLeft),floor_output:await page.locator('#fuelFloorValue').innerText(),errors,posts};
 await page.locator('#fuelReset').click();await page.waitForTimeout(100);assert.deepEqual(await sizes(),before);console.log('POST requests:',posts);assert(!posts.some(u=>/fuel-settings|\/run$|\/mc$/.test(u)));assert.deepEqual(errors,[]);
 fs.writeFileSync(out+'ui-check.json',JSON.stringify(info,null,2));console.log(JSON.stringify({rooms:info.rooms,changed:info.changed,protected:info.room_protected,indent:info.indent,errors,posts}));
}finally{await browser.close();}
