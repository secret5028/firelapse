import fs from 'node:fs';import path from 'node:path';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)('C:/Users/예방/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const out=path.resolve('reviews/saved-view-20261105');fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const report={errors:[],blockedWrites:[],checks:[]};
try{const p=await browser.newPage({viewport:{width:1440,height:1000}});p.setDefaultTimeout(45000);
p.on('pageerror',e=>report.errors.push(e.message));await p.route('**/*',r=>{if(!['GET','HEAD'].includes(r.request().method())&&!r.request().url().endsWith('/cfbt/lite/ai/reports/list')){report.blockedWrites.push(r.request().url());return r.abort();}return r.continue();});
const ready=()=>p.waitForFunction(()=>document.body.classList.contains('cfbtReady'));
await p.goto('http://127.0.0.1:8842/model.html');await ready();
const id='modelmc-mc-1793837220766400600-be36c361-S08';
await p.locator(`#liteCase option[value="${id}"]`).waitFor({state:'attached'});
await p.evaluate(async id=>{const e=document.getElementById('liteCase');e.value=id;await e.onchange();},id);
await p.evaluate(()=>{const e=document.getElementById('liteRoom');e.value=[...e.options].find(o=>o.textContent.includes('5F R16')).value;e.onchange();});
await p.locator('#shellFloor').selectOption('5F');await p.locator('#shellTime').fill('1420');await p.locator('#shellTime').dispatchEvent('input');await p.locator('#shellTab-display').click();
const snapshot=()=>p.evaluate(()=>({case_id:document.getElementById('liteCase').value,floor:document.getElementById('shellFloor').value,time:document.getElementById('shellTime').value,room:document.getElementById('resultRoomTitle').textContent,tab:document.querySelector('#pyroShellTabs [aria-selected=true]').id,playing:document.getElementById('shellPlay').textContent}));
const before=await snapshot();await p.reload();await ready();const after=await snapshot();assert.deepEqual(after,before);assert.equal(after.case_id,id);assert.equal(after.time,'1420');report.checks.push({name:'reload MC S08 / 5F / R16 / 1420 / display',before,after});
await p.locator('#shellTab-result').click();await p.screenshot({path:path.join(out,'restored-MC-S08-1420.png')});
// Preserve a deliberately different selected floor; do not relabel the saved result.
await p.locator('#shellFloor').selectOption('2F');await p.reload();await ready();let state=await snapshot();assert.equal(state.floor,'2F');assert.equal(state.case_id,id);assert.equal(state.tab,'shellTab-result');assert((await p.locator('#resultScope').innerText()).includes('5F'));assert.equal((await p.locator('.resultValue').allTextContents()).join(','),'—,—,—');report.checks.push({name:'different selected floor remains unevaluated',state});
await p.route('**/cfbt/lite/result/'+id,r=>r.fulfill({status:404,contentType:'application/json',body:'{"error":"test: removed saved result"}'}));
await p.reload();await ready();state=await snapshot();assert.notEqual(state.case_id,id);assert.equal(state.time,'0');report.checks.push({name:'missing saved result safely falls back (injected HTTP 404)',state});
assert.deepEqual(report.errors,[]);assert.deepEqual(report.blockedWrites,[]);console.log(JSON.stringify(report));
}finally{fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify(report,null,2));await browser.close();}
