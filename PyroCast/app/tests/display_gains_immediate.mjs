import fs from 'node:fs';import path from 'node:path';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),{chromium}=require(process.env.PYROCAST_PLAYWRIGHT||'playwright');
const phase=process.argv[2]||'before',out=path.resolve('reviews/slider-fix-20261103',phase);fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const report={errors:[],samples:[]};
try{
 const p=await browser.newPage({viewport:{width:1280,height:720},deviceScaleFactor:1});p.setDefaultTimeout(120000);
 p.on('pageerror',e=>report.errors.push(e.message));
 await p.addInitScript(()=>{performance.now=()=>180000;const raf=requestAnimationFrame;window.requestAnimationFrame=cb=>raf(()=>{if(!window.__holdFrames)cb(180000);});});
 await p.route('**/operating.js',async route=>{const r=await route.fetch();await route.fulfill({response:r,body:(await r.text()).replace('const app=await attach(viewer);','const app=await attach(viewer);window.__ui=app;window.__ready=true;')});});
 await p.goto('http://127.0.0.1:8832/data/wando-coldstore/model.html');await p.waitForFunction(()=>window.__ready);
 await p.evaluate(()=>{const t=document.getElementById('liteTime');t.value=1400;t.oninput();const r=document.getElementById('liteRoom');r.value='CAD_1F_R5';r.onchange();document.getElementById('liteFocus').click();window.__holdFrames=true;});
 const inspect=()=>p.evaluate(()=>{const a=window.__ui,smoke=[],jets=[],walls=[];a.host.scene.traverse(o=>{const u=o.material?.uniforms;if(o.visible&&u?.uFire?.value===0&&u?.uGas?.value===0)smoke.push(u.uOpacity.value);if(o.visible&&o.userData.doorJet)jets.push(u.uFlameGain.value);if(o.visible&&o.name.startsWith('cavity-wall-glow:'))walls.push(o.material.emissiveIntensity);});return {settings:a.store.get('realView'),smoke,jets,walls,panel:[document.getElementById('displaysmokeGain').value,document.getElementById('displayflameGain').value]};});
 // DOM input events; no render()/tick call after changing a slider. The panel
 // additionally exercises real Home/End keyboard events below.
 for(const [name,smoke,flame] of [['default',100,100],['smoke-low',30,100],['smoke-high',150,100],['flame-low',100,50],['flame-high',100,200],['roundtrip',100,100]]){
  for(const [id,value] of [['scenesmokeGain',smoke],['sceneflameGain',flame]])await p.locator('#'+id).evaluate((el,value)=>{el.value=value;el.dispatchEvent(new Event('input',{bubbles:true}));},value);
  const sample={name,...await inspect()};report.samples.push(sample);await p.locator('#v canvas').screenshot({path:path.join(out,name+'.png')});
  if(phase==='after'){assert(sample.smoke.length&&sample.smoke.every(v=>Math.abs(v-.7*smoke/100)<1e-10));assert(sample.jets.length&&sample.jets.every(v=>v===flame/100));}
 }
 await p.click('#shellTab-display');await p.locator('#displaysmokeGain').focus();await p.keyboard.press('Home');await p.locator('#displayflameGain').focus();await p.keyboard.press('End');
 report.panelKeyboard=await inspect();if(phase==='after'){assert(report.panelKeyboard.smoke.every(v=>Math.abs(v-.21)<1e-10));assert(report.panelKeyboard.jets.every(v=>v===2));}
 await p.evaluate(()=>{window.__ui.dispose();window.dispatchEvent(new PageTransitionEvent('pagehide'));});report.subscriptionsAfterDispose=await p.evaluate(()=>window.__ui.store.diagnostics().subscriptions);assert.equal(report.subscriptionsAfterDispose,0);assert.deepEqual(report.errors,[]);
}finally{fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify(report,null,2));await browser.close();}
