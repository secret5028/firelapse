// Read-only operational UI check. No upload, model creation, or simulation.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)('C:/Users/예방/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try {
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(60000);
 await page.goto('http://127.0.0.1:8842/model.html');
 await page.locator('#shellNewBuilding').waitFor();
 assert.equal(await page.locator('#shellNewBuilding').isEnabled(),true);
 await page.locator('#shellNewBuilding').click();
 const frame=page.frameLocator('iframe[title="새 건물 도면 업로드"]');
 await frame.locator('#drop').waitFor();
 assert(await frame.locator('#filesButton').isVisible());
 assert(await frame.locator('#folderButton').isVisible());
 assert(await frame.locator('#nameSource').isVisible());
 await page.screenshot({path:'reviews/new-building-20261105/operational-dialog.png'});
 await page.getByRole('button',{name:'새 건물 생성 창 닫기'}).click();
 assert.equal(await page.locator('dialog[aria-label="새 건물 생성하기"]').isVisible(),false);
 assert.deepEqual(errors,[]);
 const result={url:page.url(),dialog:'PASS',file_and_folder_inputs:'PASS',name_input_and_drawing_choice:'PASS',close:'PASS',errors,uploads:0,simulations:0};
 fs.writeFileSync('reviews/new-building-20261105/operational-verification.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
} finally {await browser.close();}
