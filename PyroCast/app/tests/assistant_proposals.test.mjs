import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),{chromium}=require(process.env.PYROCAST_PLAYWRIGHT||'playwright');
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
try{
 const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 const module=fs.readFileSync(new URL('../web/panels/assistant.js',import.meta.url),'utf8');
 await page.route('http://assistant.test/**',r=>r.fulfill({contentType:r.request().url().endsWith('.js')?'text/javascript':'text/html',body:r.request().url().endsWith('/resize_handle.js')?fs.readFileSync(new URL('../web/panels/resize_handle.js',import.meta.url),'utf8'):r.request().url().endsWith('/assistant.js')?module:'<div id="pyroShellTabs"></div><div id="pyroShellSidebar"><div id="resultCase"></div></div><div id="displayViewSettings"></div>'}));
 await page.goto('http://assistant.test/');
 await page.evaluate(async()=>{
  const {createAssistantPanel}=await import('/assistant.js');window.ctx={building:'test',case:'S09'};window.applied=[];window.nextProposals=[];window.failApply=false;
  window.fetch=async()=>({ok:true,json:async()=>({text:'제안 확인',case:ctx.case,building:ctx.building,proposals:nextProposals,calls:[]})});
  window.ui=createAssistantPanel({store:{subscribe:(key,fn)=>{window.changeResult=fn;return ()=>{};},get:()=>null},getContext:()=>ctx,onNavigate:()=>{},onSaved:()=>{},onProposal:async(p,rooms)=>{if(failApply)throw Error('적용 실패');applied.push({id:p.proposal_id,rooms});}});
 });
 await page.locator('#aiAssistant>summary').click();
 assert(await page.locator('#aiPending').isHidden());assert.equal(await page.locator('#aiLegacyFuel,#aiFuel').count(),0);
 const ask=async()=>{await page.locator('#aiMessage').fill('용도 변경');await page.locator('#aiSend').click();await page.waitForFunction(()=>!document.getElementById('aiSend').disabled);};
 await ask();assert(await page.locator('#aiPending').isHidden());
 await page.evaluate(()=>{nextProposals=[{kind:'fuel',proposal_id:'fuel-test',rows:[{room_id:'CAD_1F_R3',current_usage:'사무실',proposed_usage:'창고',load:500,reason:'테스트 전용'}]},{kind:'openings',proposal_id:'door-test'}];});
 await ask();assert(await page.locator('#aiPending').isVisible());assert.equal(await page.locator('.aiFuelProposal tbody tr').count(),1);
 const apply=page.getByRole('button',{name:'선택 적용',exact:true});assert(await apply.nth(0).isDisabled());
 await page.getByRole('checkbox',{name:'1F R3 적용 선택'}).check();assert(await apply.nth(0).isEnabled());
 await page.evaluate(()=>failApply=true);await apply.nth(0).click();assert(await page.locator('#aiPending').isVisible());assert.equal(await page.locator('#aiProposals>div').count(),2);
 await page.evaluate(()=>failApply=false);await apply.nth(0).click();assert.equal(await page.locator('#aiProposals>div').count(),1);assert(await page.locator('#aiPending').isVisible());
 await apply.click();assert(await page.locator('#aiPending').isHidden());assert.deepEqual(await page.evaluate(()=>applied),[{id:'fuel-test',rooms:['CAD_1F_R3']},{id:'door-test',rooms:[]}]);
 await ask();assert(await page.locator('#aiPending').isVisible());await page.evaluate(()=>{ctx.case='S06';changeResult();});assert(await page.locator('#aiPending').isHidden());
 await page.evaluate(()=>ui.dispose());assert.equal(await page.locator('#aiAssistant').count(),0);assert.deepEqual(errors,[]);
 console.log('PASS: empty / ordinary reply / proposals / selection gate / apply failure / partial apply / complete apply / case change / dispose; no real API or saved input writes');
}finally{await browser.close();}
