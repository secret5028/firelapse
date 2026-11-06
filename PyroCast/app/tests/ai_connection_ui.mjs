import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)('C:/Users/<user>/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'}),out='reviews/ai-connection-20261105';fs.mkdirSync(out,{recursive:true});
try{
 const page=await browser.newPage({viewport:{width:560,height:720}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8866/models/ai');await page.locator('#url').fill('http://127.0.0.1:8867/v1');await page.locator('#model').fill('fixture-model');await page.locator('#key').fill('fixture-secret-not-real');await page.locator('#connect').click();await page.waitForFunction(()=>document.querySelector('#status').textContent==='연결됨 · fixture-model');assert.equal(await page.locator('#key').inputValue(),'');
 await page.reload();await page.waitForFunction(()=>document.querySelector('#status').textContent==='연결됨 · fixture-model');assert.equal(await page.locator('#key').inputValue(),'');
 assert.deepEqual(await page.evaluate(()=>({local:Object.keys(localStorage),session:Object.keys(sessionStorage)})),{local:[],session:[]});
 const response=await page.request.get('http://127.0.0.1:8866/models/ai/connection');assert(!(await response.text()).includes('fixture-secret'));await page.screenshot({path:out+'/connection-fixture.png'});
 await page.locator('#model').fill('reject');await page.locator('#key').fill('fixture-secret-not-real');await page.locator('#connect').click();await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('연결 실패'));assert.equal(await page.locator('#key').inputValue(),'');
 await page.locator('#disconnect').click();await page.waitForFunction(()=>document.querySelector('#status').textContent==='연결 안 됨');
 const cross=await page.request.post('http://127.0.0.1:8866/models/ai/connection',{headers:{Origin:'https://untrusted.invalid'},data:{action:'disconnect'}});assert.equal(cross.status(),403);assert.deepEqual(errors,[]);
 const report={provider:'test-only localhost mock; real API unverified',connect:'PASS',reload_preserves_connection:'PASS',no_browser_storage:'PASS',key_cleared:'PASS',failed_connection:'PASS',disconnect:'PASS',foreign_origin_blocked:'PASS',errors};fs.writeFileSync(out+'/ui.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));
}finally{await browser.close();}
