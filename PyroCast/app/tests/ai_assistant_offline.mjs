import fs from 'node:fs';import path from 'node:path';import assert from 'node:assert/strict';import {createRequire} from 'node:module';import {pathToFileURL} from 'node:url';
const require=createRequire(import.meta.url),{chromium}=require(process.env.PYROCAST_PLAYWRIGHT||'playwright');
const out=path.resolve('simulation/results/ui_D4_20261103'),browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const report={errors:[],network:[]};
try{const p=await browser.newPage({viewport:{width:1440,height:1000}});p.on('pageerror',e=>report.errors.push(e.message));p.on('request',r=>{if(/^https?:/.test(r.url()))report.network.push(r.url());});
 await p.goto(pathToFileURL(path.join(out,'PyroCast-S09-assistant.html')).href);await p.waitForFunction(()=>document.documentElement.dataset.offlineReady==='true',{timeout:90000});
 await p.waitForFunction(()=>document.querySelectorAll('#aiSavedReports pre').length>0);report.reports=await p.locator('#aiSavedReports pre').count();
 assert(await p.locator('#aiBrief').isDisabled());assert(await p.locator('#aiSend').isDisabled());assert.equal(report.network.length,0);
 await p.evaluate(()=>{document.getElementById('aiSavedReports').open=true;document.querySelector('#aiSavedReports details').open=true;});await p.screenshot({path:path.join(out,'assistant-offline.png')});assert.equal(report.errors.length,0);
}finally{fs.writeFileSync(path.join(out,'offline-verification.json'),JSON.stringify(report,null,2));await browser.close();}
