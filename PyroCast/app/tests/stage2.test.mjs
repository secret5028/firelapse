// Browser fixture uses local files served through Playwright interception, no HTTP server.
import fs from 'node:fs';import path from 'node:path';import {fileURLToPath} from 'node:url';import {createRequire} from 'node:module';import {createHash} from 'node:crypto';
const require=createRequire(import.meta.url);let playwright;try{playwright=require('playwright');}catch(e){if(!process.env.PYROCAST_PLAYWRIGHT)throw e;playwright=require(process.env.PYROCAST_PLAYWRIGHT);}
const root=fileURLToPath(new URL('../../',import.meta.url)),app=path.join(root,'app');
const three=process.env.PYROCAST_THREE||path.join(root,'cad-project/work/cad-web/local-resources/cad-assets/three.module.js');
const output=path.join(root,'simulation/results/ui_refactor_stage2_20261026');fs.mkdirSync(output,{recursive:true});
const files=[];function walk(dir){for(const entry of fs.readdirSync(dir,{withFileTypes:true})){const p=path.join(dir,entry.name);if(entry.isDirectory())walk(p);else if(p.endsWith('.js'))files.push(p);}}
walk(path.join(app,'web/state'));walk(path.join(app,'web/scene'));walk(path.join(app,'web/layers'));
// Fail closed if a transport, engine import or DOM owner sneaks into pure layers/store.
for(const file of files){const src=fs.readFileSync(file,'utf8');if(/\b(fetch|XMLHttpRequest|WebSocket|EventSource)\s*\(|\bimport\s*\(/.test(src)||/pyrocast_(lite|cfbt)/.test(src))throw Error('Forbidden dependency: '+file);
 if(!file.endsWith('host.js')&&/\b(document|window)\s*[.\[(]/.test(src)){throw Error('DOM dependency outside host: '+file);}}
const browser=await playwright.chromium.launch({headless:true,executablePath:process.env.PYROCAST_BROWSER||'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try{
 const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',async route=>{const url=new URL(route.request().url());if(url.hostname!=='pyrocast-fixture.test')throw Error('External request blocked: '+url);
  const file=url.pathname==='/vendor/three.module.js'?three:path.resolve(app,'.'+decodeURIComponent(url.pathname));
  if(file!==three&&!file.startsWith(app+path.sep))throw Error('Invalid fixture path');
  await route.fulfill({status:200,contentType:file.endsWith('.html')?'text/html; charset=utf-8':'text/javascript; charset=utf-8',body:fs.readFileSync(file)});
 });
 await page.goto('http://pyrocast-fixture.test/tests/stage2.fixture.html');
 const result=await page.evaluate(()=>window.stage2Done);if(errors.length)throw Error(errors.join('\n'));
 result.browser=browser.version();result.created=new Date().toISOString();result.page_errors=errors;result.static_dependency_check=true;
 result.three_sha256=createHash('sha256').update(fs.readFileSync(three)).digest('hex');
 fs.writeFileSync(path.join(output,'verification.json'),JSON.stringify(result,null,2));await page.screenshot({path:path.join(output,'fixture.png'),fullPage:true});
 console.log(JSON.stringify({...result,rows:result.rows.length+' cycles; retained counts all zero'},null,2));
}finally{await browser.close();}
