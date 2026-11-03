import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),{chromium}=require(process.env.PYROCAST_PLAYWRIGHT||'playwright');
const base=process.env.D4_BASE||'http://127.0.0.1:8840';
const out=path.resolve('simulation/results/ui_D4_20261103');fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const report={errors:[],checks:[],requests:[]};
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}});page.setDefaultTimeout(90000);page.on('pageerror',e=>report.errors.push(e.message));
 page.on('request',r=>{if(r.method()==='POST')report.requests.push(new URL(r.url()).pathname);});
 await page.route('**/model.html',async route=>{const r=await route.fetch();let h=await r.text(),hook='await (await import("/cfbt/overlay.js")).attach({',i=h.indexOf(hook),j=h.indexOf('\n</script>',i),old=h.slice(i,j),arg=old.slice(hook.length-1,old.lastIndexOf(');'));assert(i>=0);h=h.slice(0,i)+'window.__cad='+arg+';window.__ui=await (await import("/cfbt/overlay.js")).attach(window.__cad);window.__ready=true;'+h.slice(j);await route.fulfill({response:r,body:h});});
 await page.goto(base+'/cad-result/90d3c325f238a3c4/model.html');await page.waitForFunction(()=>window.__ready);
 await page.evaluate(async()=>{const s=document.getElementById('liteCase');s.value='S09';await s.onchange();const t=document.getElementById('liteTime');t.value=1420;t.oninput();document.getElementById('aiAssistant').open=true;});
 await page.locator('#aiBrief').click();await page.waitForFunction(()=>document.querySelectorAll('#aiConversation .aiFact').length>3);
 const evidence=await page.locator('.aiEvidence').last().textContent();assert(evidence.includes('8회'));report.checks.push({briefing:evidence});
 const f=page.locator('.aiFact').filter({hasText:'FO 최고'}).first();await f.click();
 const nav=await page.evaluate(()=>({selection:window.__ui.store.get('selection'),time:window.__ui.store.get('playback').t_s}));assert.equal(nav.time,1250);assert.equal(nav.selection.room_id,'CAD_3F_R2');report.checks.push({navigation:nav});
 await page.screenshot({path:path.join(out,'assistant-right.png')});
 await page.locator('#shellTab-display').click();await page.selectOption('#assistantPosition','left');await page.screenshot({path:path.join(out,'assistant-left.png')});
 await page.selectOption('#assistantPosition','floating');await page.screenshot({path:path.join(out,'assistant-floating.png')});
 await page.selectOption('#assistantPosition','right');await page.fill('#aiMessage','3층에서 가장 위험한 실');await page.locator('#aiSend').click();await page.waitForFunction(()=>document.getElementById('aiStatus').textContent.includes('API 미설정'));report.checks.push('missing API does not affect briefing');await page.screenshot({path:path.join(out,'assistant-api-unconfigured.png')});
 // Save is a real explicit user click; attaches this verified S09 briefing only.
 await page.getByRole('button',{name:'보고서로 저장',exact:true}).click();await page.waitForFunction(()=>document.getElementById('aiStatus').textContent.includes('저장 완료'));assert(await page.locator('#aiSavedReports pre').count()>0);report.checks.push('explicit report saved and listed');
 const dispose=await page.evaluate(()=>{window.__ui.dispose();return {assistant:document.querySelectorAll('#aiAssistant').length,settings:document.querySelectorAll('#assistantPosition').length};});assert.deepEqual(dispose,{assistant:0,settings:0});report.checks.push({dispose});
 assert.equal(report.errors.length,0);assert(!report.requests.some(p=>['/cfbt/lite/mc','/cfbt/lite/screening','/cfbt/run'].includes(p)));
}finally{fs.writeFileSync(path.join(out,'ui-verification.json'),JSON.stringify(report,null,2));await browser.close();}
