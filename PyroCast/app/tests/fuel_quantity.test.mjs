import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fuelPositions,symbolSize,FuelQuantityLayer} from '../web/layers/fuel_quantity.js';
import {contains} from '../web/route/graph.js';
import {resolveFuel} from '../web/state/fuel_settings.js';
import {createStore} from '../web/state/store.js';
import {pathToFileURL} from 'node:url';
const poly=[{o:[[0,0],[8,0],[8,3],[3,3],[3,8],[0,8]],h:[[[.5,.5],[1.5,.5],[1.5,1.5],[.5,1.5]]]}];
for(const u of fuelPositions(poly)){const size=symbolSize(1500,u.clearance,3);for(const dx of [-size/2,size/2])for(const dy of [-size/2,size/2])assert(contains([u.p[0]+dx,u.p[1]+dy],poly));}
const T=await import(pathToFileURL(process.cwd()+'/cad-project/work/cad-web/local-resources/cad-assets/three.module.js'));
const data={revision:'1',classes:{hotel_room:{mean:500,rhrf:250},office:{mean:600,rhrf:300}},quantity_settings:{rooms:{CAD_5F_A:{usage_class:'office',multiplier:1}}},rooms:[{id:'CAD_5F_A',floor:'5F',editable:true,baseline_class:'hotel_room',baseline_load:500}],ai_pending:[]};
assert.equal(resolveFuel(data,{floors:{'5F':{usage_class:'hotel_room',multiplier:3}}},data.rooms[0]).load,600);
const layer=new FuelQuantityLayer(T,{floors:[{name:'5F',z:12,h:3,rooms:[{id:'A',polys:poly}]}]}),store=createStore();layer.mount(new T.Scene(),store);
const frame={building:{floors:[]},fuelSettings:{data,draft:{}},floor:{floor_id:'5F'},realView:{fuelMarkers:true},layers:{selection:true},selection:{room_id:'CAD_5F_A'}};layer.setData(frame);
assert.equal(layer.getPickPlanes().length,1);assert.equal(layer.getPickPlanes()[0].layers.mask,2**31);assert.equal(layer.picks[0].line.visible,true);
const ray=new T.Raycaster(new T.Vector3(2,2,20),new T.Vector3(0,0,-1));ray.layers.set(31);layer.group.updateMatrixWorld(true);assert.equal(ray.intersectObjects(layer.getPickPlanes(),false)[0].object.userData.roomId,'CAD_5F_A');
layer.setData({...frame,floor:{floor_id:'6F'}});assert.equal(layer.getPickPlanes().length,0);layer.dispose();assert.equal(layer.resources.size,0);
const require=createRequire(import.meta.url),{chromium}=require(process.env.PYROCAST_PLAYWRIGHT||'playwright');
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
try{
 const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('http://fuel.test/**',r=>{const path=new URL(r.request().url()).pathname;return r.fulfill({contentType:path.endsWith('.js')?'text/javascript':'text/html',body:path.endsWith('.js')?fs.readFileSync(process.cwd()+path,'utf8'):'<button id="shellTab-building">설정</button><div id="buildingContent"><section id="buildingFuelSection"></section><p id="buildingSettingsEmpty"></p></div>'});});
 await page.goto('http://fuel.test/');await page.evaluate(async()=>{
  const {createFuelSettingsPanel}=await import('/app/web/panels/fuel_settings.js'),{createStore}=await import('/app/web/state/store.js');window.store=createStore();store.dispatch('floor/set',{floor_id:'5F'});window.calls=[];window.fail=false;
  window.data={editable:true,building_sha256:'test',revision:'one',range:{min:.1,max:3,step:.1},classes:{hotel_room:{label:'숙박',mean:500,rhrf:250},office:{label:'사무실',mean:600,rhrf:300}},quantity_settings:{},ai_available:false,ai_pending:['A','B','C'],default_status:'AI 초기 배치 대기 · API 미설정',rooms:['A','B','C'].map((id,i)=>({id,floor:i===2?'6F':'5F',name:'객실',area:20,baseline_class:'hotel_room',baseline_load:500,editable:true}))};
  window.fetch=async(url,opts)=>{if(opts?.method==='POST'){const body=JSON.parse(opts.body);calls.push({url,body});if(body.search)return {ok:true,json:async()=>({suggestions:[{usage_class:'office',reason:'유사 용도 기준 · 추정'}]})};if(fail)return {ok:false,json:async()=>({error:'저장 실패 테스트'})};for(const scope of ['rooms','floors']){const rows=data.quantity_settings[scope]||={};for(const r of body[scope]||[]){if(r.inherit)delete rows[r.id];else rows[r.id]={usage_class:r.usage_class,multiplier:r.multiplier};}}if(body.initialize_defaults){data.quantity_settings.defaults=Object.fromEntries(data.rooms.map(r=>[r.id,{usage_class:'hotel_room',source:'ai'}]));data.ai_pending=[];data.default_status='AI 기본값';}data.revision='two';}return {ok:true,json:async()=>structuredClone(data)};};
  window.ui=createFuelSettingsPanel({store,onSaved:async()=>{window.saved=true;}});
 });
 await page.waitForSelector('#fuelSettings:not([hidden])');assert.equal(await page.locator('#fuelSelectedRoom').isVisible(),false);assert.equal(await page.locator('input[type=range]:visible').count(),1);assert.match(await page.locator('#fuelDefaultsStatus').innerText(),/AI 연결 대기/);assert.equal(await page.locator('#fuelAI').isDisabled(),true);
 const set=async(selector,n)=>page.locator(selector).evaluate((e,n)=>{e.value=n;e.dispatchEvent(new Event('input'));},n);
 await page.evaluate(()=>store.dispatch('selection/set',{room_id:'A',cell_id:'A',source:'click'}));assert.equal(await page.locator('#fuelSelectedRoom').isVisible(),true);
 await page.locator('#fuelSearch').fill('사무실');await page.locator('#fuelSearchResults button').click();await set('#fuelRoomAmount',100);await set('#fuelFloorAmount',200);assert.equal(await page.locator('#fuelFloorType').count(),0);
 assert.deepEqual(await page.evaluate(()=>store.get('fuelSettings').draft),{rooms:{A:{usage_class:'office',multiplier:1}},floors:{'5F':{multiplier:2}}});assert.match(await page.locator('#fuelRoomValue').innerText(),/600 MJ/);
 await page.evaluate(()=>fail=true);await page.locator('#fuelSave').click();await page.waitForFunction(()=>!store.get('fuelSettings').saving);assert.match(await page.locator('#fuelSettingsStatus').innerText(),/실패/);
 await page.evaluate(()=>fail=false);await page.locator('#fuelSave').click();await page.waitForFunction(()=>window.saved);assert.deepEqual(await page.evaluate(()=>store.get('fuelSettings').draft),{});
 await page.locator('#fuelInherit').click();assert.match(await page.locator('#fuelRoomValue').innerText(),/1000 MJ/);await page.locator('#fuelSave').click();await page.waitForFunction(()=>!store.get('fuelSettings').saving);assert.equal(await page.evaluate(()=>!!data.quantity_settings.rooms.A),false);
 await page.evaluate(()=>store.dispatch('floor/set',{floor_id:'6F'}));assert.equal(await page.locator('#fuelSelectedRoom').isVisible(),false);await set('#fuelFloorAmount',300);await page.locator('#fuelReset').click();assert.deepEqual(await page.evaluate(()=>store.get('fuelSettings').draft),{});
 await page.evaluate(async()=>{data.ai_pending=[];data.ai_available=true;await ui.refresh();window.dispatchEvent(new CustomEvent('pyrocast:ai-connection',{detail:{connected:true}}));store.dispatch('selection/set',{room_id:'C',cell_id:'C',source:'click'});});await page.locator('#fuelSearch').fill('목재 가구');await page.locator('#fuelSearchAI').click();await page.waitForSelector('#fuelSearchResults button');assert.deepEqual(await page.evaluate(()=>store.get('fuelSettings').draft),{});await page.locator('#fuelSearchResults button').click();assert.equal(await page.evaluate(()=>store.get('fuelSettings').draft.rooms.C.usage_class),'office');await page.locator('#fuelReset').click();
 assert((await page.evaluate(()=>calls)).every(c=>c.url==='/cfbt/lite/fuel-settings'));await page.evaluate(()=>ui.dispose());assert.equal(await page.locator('#fuelSettings').count(),0);
 await page.evaluate(async()=>{store.dispatch('floor/set',{floor_id:null});data.quantity_settings={};data.ai_available=true;data.ai_pending=['A','B','C'];calls=[];const {createFuelSettingsPanel}=await import('/app/web/panels/fuel_settings.js');window.ui=createFuelSettingsPanel({store});});
 await page.waitForFunction(()=>data.ai_pending.length===0&&!store.get('fuelSettings').saving);await page.evaluate(()=>ui.refresh());assert.equal(await page.evaluate(()=>calls.length),1);assert.equal(await page.locator('#fuelSettings').evaluate(e=>e.disabled),true);assert.equal(await page.evaluate(()=>store.get('realView').fuelMarkers),true);await page.evaluate(()=>ui.dispose());assert.deepEqual(errors,[]);
 console.log('PASS: containment, inherited quantities, hidden CAD pick planes, floor filtering, dispose, click-only room UI, explicit 100% protection, reset inheritance, no solver requests');
}finally{await browser.close();}
