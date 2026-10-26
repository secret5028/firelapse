import fs from 'node:fs';import path from 'node:path';import {fileURLToPath} from 'node:url';import {createRequire} from 'node:module';import {createHash} from 'node:crypto';
const require=createRequire(import.meta.url),playwright=require(process.env.PYROCAST_PLAYWRIGHT||'playwright');
const root=fileURLToPath(new URL('../../',import.meta.url)),app=path.join(root,'app');
const baseline=JSON.parse(fs.readFileSync(path.join(root,'simulation/results/ui_refactor_stage0_20261026/baseline-hashes.json'),'utf8'));
const model=process.env.PYROCAST_MODEL||baseline.files.find(r=>r.path.endsWith('model.html')).path;
const cad=path.join(path.dirname(model),'building.json');
const three=process.env.PYROCAST_THREE||path.join(root,'simulation/results/github-publish-20261026/PyroCast/cad-project/work/cad-web/local-resources/cad-assets/three.module.js');
const sha=p=>createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const out=path.join(root,'simulation/results/ui_refactor_stage3_building_20261026');fs.mkdirSync(out,{recursive:true});
const shaderFiles=['legacy_real_view.js','legacy_real_bridge.js'].map(n=>path.join(root,'simulation/viewer',n));
const hashes=Object.fromEntries([cad,model,...shaderFiles].map(p=>[p,sha(p)]));
const browser=await playwright.chromium.launch({headless:true,executablePath:process.env.PYROCAST_BROWSER||'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try{
 const page=await browser.newPage({viewport:{width:1000,height:700},deviceScaleFactor:1});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',async route=>{const url=new URL(route.request().url());if(url.hostname!=='pyrocast-fixture.test')throw Error('External URL');
  const specials={'/vendor/three.module.js':three,'/legacy/building.json':cad,'/legacy/model.txt':model,'/legacy/viewer.txt':path.join(root,'simulation/viewer/lite_viewer.js')};
  if(url.pathname==='/legacy/hash.txt')return route.fulfill({body:sha(cad)});
  const file=specials[url.pathname]||path.resolve(app,'.'+url.pathname);if(!specials[url.pathname]&&!file.startsWith(app+path.sep))throw Error('Invalid path');
  await route.fulfill({body:fs.readFileSync(file),contentType:file.endsWith('.html')&&url.pathname!=='/legacy/model.txt'?'text/html; charset=utf-8':'text/javascript; charset=utf-8'});
 });
 await page.goto('http://pyrocast-fixture.test/tests/building.fixture.html');await page.evaluate(()=>window.ready);
 const captures=[];
 for(const [name,floor,top] of [['3F-iso','3F',false],['3F-top','3F',true],['all',null,false]]){
  for(const which of ['baseline','layer']){await page.evaluate(([w,f,t])=>window.capture(w,f,t),[which,floor,top]);await page.locator('canvas').screenshot({path:path.join(out,`${name}-${which}.png`)});}captures.push(name);
 }
 const report=await page.evaluate(()=>window.verify());if(errors.length)throw Error(errors.join('\n'));
 for(const [p,h] of Object.entries(hashes))if(sha(p)!==h)throw Error('Frozen file changed: '+p);
 fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify({...report,captures,page_errors:errors,hashes,browser:browser.version(),simulation_runs:0},null,2));console.log(JSON.stringify(report));
}finally{await browser.close();}
