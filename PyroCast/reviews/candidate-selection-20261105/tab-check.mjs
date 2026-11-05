import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),{chromium}=require('C:/Users/예방/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1050},hasTouch:true}),errors=[],mcRequests=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/app/web/controller.js',async r=>{const response=await r.fetch();await r.fulfill({response,body:(await response.text()).replace('const display=createDisplayPanel(', 'window.__candidateStore=store;const display=createDisplayPanel(').replace('const cleanup=[],originalRender=', 'window.__candidateSelection=selection;const cleanup=[],originalRender=')});});
 await page.route('**/cfbt/lite/mc',r=>{if(r.request().method()==='POST'){mcRequests.push(r.request().postDataJSON());return r.fulfill({status:400,contentType:'application/json',body:JSON.stringify({error:'test intercepted: no calculation'})});}return r.continue();});
 await page.goto('http://127.0.0.1:8842/model.html');await page.locator('#shellTab-building').click();await page.locator('#exploreFloor').selectOption('5F');await page.waitForFunction(()=>document.querySelectorAll('#exploreCandidates tr').length===5);await page.locator('#top').click();
 const third=page.locator('#exploreCandidates tr').nth(2),thirdId=await third.getAttribute('data-room');await third.click();
 const selection=await page.evaluate(()=>({origin:__candidateStore.get('exploration'),selected:__candidateStore.get('selection')}));assert.equal(selection.origin.origin_room_id,thirdId);assert.equal(selection.selected.room_id,thirdId);assert.equal(await third.getAttribute('aria-selected'),'true');
 await page.locator('#exploreFloor').selectOption('5F');await page.waitForTimeout(1000);assert.equal(await page.evaluate(()=>__candidateStore.get('exploration').origin_room_id),thirdId);
 await page.locator('#exploreCandidates tr').nth(1).focus();await page.keyboard.press('Enter');const secondId=await page.locator('#exploreCandidates tr').nth(1).getAttribute('data-room');assert.equal(await page.evaluate(()=>__candidateStore.get('selection').room_id),secondId);
 await page.locator('#exploreMC').click();await page.waitForFunction(()=>document.getElementById('exploreMCStatus').textContent.includes('실패'));assert.equal(mcRequests.length,1);assert.equal(mcRequests[0].room,secondId);assert.equal(mcRequests[0].selection_mode,'candidate');
 await third.click();await page.waitForFunction(()=>window.__candidateSelection.views.some(v=>v.roomId===window.__candidateStore.get('selection').room_id&&v.ribbon.visible&&v.group.visible)&&window.__candidateSelection.group.visible);await third.scrollIntoViewIfNeeded();await page.screenshot({path:'reviews/candidate-selection-20261105/selected-candidate.png'});
 await page.locator('#exploreCandidates tr').first().tap();await page.waitForFunction(()=>!document.getElementById('exploreResults').disabled);
 let applied=false;const catalog=await (await page.request.get('http://127.0.0.1:8842/cfbt/lite/catalog.json?mc_room=CAD_5F_R16')).json();const worst=catalog.mc_summary.worst;assert(worst.case_id);
 await page.route('**/cfbt/lite/fixed-openings',async r=>{assert.equal(r.request().method(),'POST');applied=true;await r.fulfill({contentType:'application/json',body:JSON.stringify({rows:[],fixed_state:{sample_id:worst.sample_id||'S08',states:{}},case_id:worst.case_id})});});
 await page.locator('#exploreApplyWorst').click();await page.waitForFunction(id=>window.__candidateStore.get('result')?.result_id===id,worst.case_id,{timeout:60000}).catch(async()=>{await page.waitForFunction(()=>document.getElementById('resultMCStatus').textContent.includes('적용 완료'),{},{timeout:60000});});
 assert(applied);assert.equal(await page.locator('#shellTab-building').getAttribute('aria-selected'),'true');await page.screenshot({path:'reviews/candidate-selection-20261105/apply-keeps-tab.png'});
 await page.locator('#exploreResults').click();assert.equal(await page.locator('#shellTab-result').getAttribute('aria-selected'),'true');assert.deepEqual(errors,[]);
 console.log(JSON.stringify({apply_keeps_setup_tab:true,view_results_opens_result_tab:true,fixed_openings_post_mocked:true,solver_executions:0,errors}));

}finally{await browser.close();}
