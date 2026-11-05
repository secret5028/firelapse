import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)('C:/Users/예방/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(60000);
 await page.goto('http://127.0.0.1:8842/model.html');await page.locator('#shellTab-building').click();await page.locator('#aiConnectButton').click();
 const frame=page.frameLocator('iframe[title="AI API 설정"]');await frame.locator('#key').waitFor();assert.equal(await frame.locator('#key').getAttribute('type'),'password');assert.equal(await frame.locator('#key').inputValue(),'');
 await page.screenshot({path:'reviews/ai-connection-20261105/operational.png'});await page.locator('dialog[aria-label="AI API 연결"] button').click();assert.deepEqual(errors,[]);
 fs.writeFileSync('reviews/ai-connection-20261105/operational.json',JSON.stringify({url:page.url(),settings_tab_button:'PASS',password_input:'PASS',errors,provider_calls:0,simulation_runs:0},null,2));
 console.log('operational dialog PASS; no key submitted');
}finally{await browser.close();}
