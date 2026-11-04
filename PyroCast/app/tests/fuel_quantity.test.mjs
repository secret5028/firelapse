import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fuelPositions,symbolSize} from '../web/layers/fuel_quantity.js';
import {contains} from '../web/route/graph.js';
const poly=[{o:[[0,0],[8,0],[8,3],[3,3],[3,8],[0,8]],h:[[[.5,.5],[1.5,.5],[1.5,1.5],[.5,1.5]]]}];
for(const u of fuelPositions(poly)){const size=symbolSize(1500,u.clearance,3);for(const dx of [-size/2,size/2])for(const dy of [-size/2,size/2])assert(contains([u.p[0]+dx,u.p[1]+dy],poly));}
assert(symbolSize(1500,4,3)>symbolSize(500,4,3));assert(symbolSize(1500,.3,.5)<=.3);
const require=createRequire(import.meta.url),{chromium}=require(process.env.PYROCAST_PLAYWRIGHT||'playwright');
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
try{
 const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 const module=fs.readFileSync(new URL('../web/panels/fuel_settings.js',import.meta.url),'utf8');
 await page.route('http://fuel.test/**',r=>r.fulfill({contentType:r.request().url().endsWith('.js')?'text/javascript':'text/html',body:r.request().url().endsWith('.js')?module:'<div id="buildingContent"><section id="buildingFuelSection"></section><p id="buildingSettingsEmpty"></p></div>'}));
 await page.goto('http://fuel.test/');await page.evaluate(async()=>{
  const {createFuelSettingsPanel}=await import('/panel.js');window.state={floor:{floor_id:'5F'},realView:{fuelMarkers:false},fuelSettings:{message:''}};window.calls=[];window.fail=false;
  window.data={editable:true,building_sha256:'test',revision:'one',range:{min:.1,max:3,step:.1},rooms:[{id:'A',floor:'5F',name:'객실',usage:'숙박',area:20,base_load:500,multiplier:1,editable:true},{id:'B',floor:'5F',name:'객실',usage:'숙박',area:25,base_load:500,multiplier:1,editable:true},{id:'C',floor:'6F',name:'객실',usage:'숙박',area:20,base_load:500,multiplier:1,editable:true}]};
  window.fetch=async(url,opts)=>{if(opts?.method==='POST'){const body=JSON.parse(opts.body);calls.push({url,body});if(fail)return {ok:false,json:async()=>({error:'저장 실패 테스트'})};for(const r of body.rooms)data.rooms.find(v=>v.id===r.id).multiplier=r.multiplier;data.revision='two';}return {ok:true,json:async()=>structuredClone(data)};};
  window.ui=createFuelSettingsPanel({store:{subscribe:()=>()=>{},get:k=>state[k],dispatch:(k,v)=>state[k.split('/')[0]]={...state[k.split('/')[0]],...v}},onSaved:async()=>{window.saved=true;}});
 });
 await page.waitForSelector('#fuelSettings:not([hidden])');assert.equal(await page.locator('#fuelFloor').inputValue(),'5F');assert.equal(await page.locator('.fuelRoomAmount').count(),2);
 const set=async(selector,n)=>page.locator(selector).evaluate((e,n)=>{e.value=n;e.dispatchEvent(new Event('input'));},n);
 await set('#fuelFloorAmount',200);assert.deepEqual(await page.evaluate(()=>state.fuelSettings.draft),{A:2,B:2});
 await set('.fuelRoomAmount input >> nth=0',150);assert.deepEqual(await page.evaluate(()=>state.fuelSettings.draft),{A:1.5,B:2});
 await page.evaluate(()=>fail=true);await page.locator('#fuelSave').click();await page.waitForFunction(()=>!state.fuelSettings.saving);assert.match(await page.locator('#fuelSettingsStatus').innerText(),/실패/);
 await page.evaluate(()=>fail=false);await page.locator('#fuelSave').click();await page.waitForFunction(()=>window.saved);assert.deepEqual(await page.evaluate(()=>state.fuelSettings.draft),{});assert.match(await page.locator('#fuelSettingsStatus').innerText(),/재계산 필요/);
 await page.locator('#fuelFloor').selectOption('6F');await set('#fuelFloorAmount',300);await page.locator('#fuelReset').click();assert.deepEqual(await page.evaluate(()=>state.fuelSettings.draft),{});
 assert((await page.evaluate(()=>calls)).every(c=>c.url==='/cfbt/lite/fuel-settings'));await page.evaluate(()=>ui.dispose());assert.equal(await page.locator('#fuelSettings').count(),0);assert.deepEqual(errors,[]);
 console.log('PASS: containment / size / floor+room edit / failure retains draft / save / cancel / no execution request / dispose');
}finally{await browser.close();}
