import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
const require=createRequire(import.meta.url),{chromium}=require(process.env.PYROCAST_PLAYWRIGHT||'playwright');
const out=path.resolve('reviews/rollover-sliders-20261103/gains'),report=JSON.parse(fs.readFileSync(path.join(out,'review.json')));
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try{
 const page=await browser.newPage({viewport:{width:1280,height:720}}),errors=[],http=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))http.push(r.url());});
 await page.goto(pathToFileURL(path.join(out,'PyroCast-S09-gains.html')).href,{waitUntil:'domcontentloaded',timeout:180000});
 await page.waitForFunction(()=>document.documentElement.dataset.offlineReady==='true',{},{timeout:180000});
 assert.equal(await page.locator('#scenesmokeGain').inputValue(),'80');assert.equal(await page.locator('#sceneflameGain').inputValue(),'120');
 await page.locator('#scenesmokeGain').evaluate(e=>{e.value=150;e.dispatchEvent(new Event('input',{bubbles:true}));});
 assert.equal(await page.locator('#displaysmokeGain').inputValue(),'150');
 await page.locator('#sceneflameGain').evaluate(e=>{e.value=50;e.dispatchEvent(new Event('input',{bubbles:true}));});
 assert.equal(await page.locator('#displayflameGain').inputValue(),'50');
 await page.screenshot({path:path.join(out,'offline.png')});
 report.offline={protocol:'file:',httpRequests:http.length,errors,savedSmoke:80,savedFlame:120,liveSmoke:150,liveFlame:50};
 assert.equal(http.length,0);assert.deepEqual(errors,[]);
}finally{fs.writeFileSync(path.join(out,'review.json'),JSON.stringify(report,null,2));await browser.close();}
