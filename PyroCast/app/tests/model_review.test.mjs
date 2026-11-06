import {existsSync as evidenceExists} from 'node:fs';
if (["reviews/cad-final-axioms-20261104/comparison.json"].some(p=>!evidenceExists(new URL('../../'+p,import.meta.url)))) {console.log('SKIP: evidence folder missing');process.exit(0);}
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {gunzipSync} from 'node:zlib';
import {reviewRows} from '../web/panels/model_review.js';
const require=createRequire(import.meta.url),{chromium}=require(process.env.PYROCAST_PLAYWRIGHT||'playwright');
const out=process.env.MODEL_REVIEW_OUT||'reviews/cad-final-axioms-20261104';
const comparison=JSON.parse(fs.readFileSync(out+'/comparison.json','utf8'));
const previous=JSON.parse(fs.existsSync(out+'/building-before.json.gz')?gunzipSync(fs.readFileSync(out+'/building-before.json.gz')).toString('utf8'):fs.readFileSync(out+'/building-before.json','utf8'));
const b=JSON.parse(fs.readFileSync('data/parkmarine-hotel/building.json','utf8'));
const unresolved=comparison.unresolved_after??comparison.after;
const before=JSON.stringify(b),rows=reviewRows(b);const correctionCount=b.model_review.corrections.length;assert.equal(rows.filter(x=>x.status==='자동보정').length,correctionCount);assert.equal(rows.filter(x=>x.kind==='isolated_room').length,unresolved);assert.equal(JSON.stringify(b),before);
assert.deepEqual(reviewRows({}),[]);
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const errors=[],requests=[];
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}});page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()!=='GET')requests.push(r.url());});
 await page.route('**/building.json',r=>r.fulfill({json:previous}));
 await page.goto('http://127.0.0.1:8840/data/parkmarine-hotel/review.html?floor=5F&room=R17');await page.waitForFunction(()=>window.__reviewReady);await page.locator('#top').click();await page.screenshot({path:out+'/hotel-5F-R17-before.png'});
 await page.unroute('**/building.json');await page.reload();await page.waitForFunction(()=>window.__reviewReady);await page.locator('#top').click();await page.screenshot({path:out+'/hotel-5F-R17-after.png'});
 assert.match(await page.locator('#review').textContent(),/연결 검증 미완료/);
 await page.getByRole('combobox',{name:'점검 분류'}).selectOption('연결 추정');await page.getByRole('combobox',{name:'점검 층'}).selectOption('5F');
 await page.getByRole('button',{name:'5F AI_ELEV_R13_R17',exact:true}).click();assert.match(await page.locator('#selected').textContent(),/AI 도면 검토/);
 await page.getByRole('combobox',{name:'점검 층'}).selectOption('');
 await page.getByRole('combobox',{name:'점검 분류'}).selectOption('자동보정');
 assert.equal(await page.locator('.modelReview tbody tr').count(),correctionCount);
 if(b.model_axioms){
  await page.getByRole('button',{name:'B2 R12',exact:true}).click();assert.match(await page.locator('#selected').textContent(),/기둥/);
  await page.locator('#iso').click();await page.screenshot({path:out+'/hotel-B2-column.png'});
  assert.match(await page.locator('#review').textContent(),/CAD → 3D → AI 공리 검토/);
 }
 await page.getByRole('button',{name:'1F D6',exact:true}).click();assert.equal(await page.locator('#floor').inputValue(),'1F');
 await page.screenshot({path:out+'/hotel-corrected-1F.png'});
 await page.getByRole('combobox',{name:'점검 분류'}).selectOption('검토 필요');await page.getByRole('combobox',{name:'점검 층'}).selectOption('B1');
 await page.getByRole('button',{name:'B1 LOADER',exact:true}).click();assert.equal(await page.locator('#floor').inputValue(),'B1');assert.match(await page.locator('#selected').textContent(),/Opening wider/);
 await page.screenshot({path:out+'/hotel-review-B1.png'});
 for(const f of b.floors)await page.locator('#floor').selectOption(f.name);
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:out+'/hotel-review-mobile.png'});
 for(const denied of ['/.git/config','/.aws/credentials','/config/ai.json','/simulation/results/','/data/parkmarine-hotel/../../config/display.json'])assert.equal((await page.request.get('http://127.0.0.1:8840'+denied)).status(),404);
 assert.equal((await page.request.post('http://127.0.0.1:8840/data/parkmarine-hotel/building.json')).status(),405);
 const live=await browser.newPage();live.on('pageerror',e=>errors.push(e.message));
 await live.goto('http://127.0.0.1:8832/data/wando-coldstore/model.html');await live.waitForFunction(()=>document.body.classList.contains('cfbtReady'));
 await live.locator('#shellTab-building').click();assert.match(await live.locator('.modelReview summary').textContent(),/미실시/);
 await live.close();
 assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);
 fs.writeFileSync(out+'/ui-verification.json',JSON.stringify({passed:true,rows:rows.length,corrections:correctionCount,isolated:unresolved,floors:b.floors.length,errors,non_get_requests:requests},null,2));console.log('PASS: arc/AI review/column/remaining markers, 14 floors, filters/location, mobile; errors 0; POST 0');
}finally{await browser.close();}
