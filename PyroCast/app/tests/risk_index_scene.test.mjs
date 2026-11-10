// Self-contained current renderer check; no development server or old screenshot.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),{chromium}=require(process.env.PYROCAST_PLAYWRIGHT||'playwright');
const root=path.resolve(fileURLToPath(new URL('../../',import.meta.url)));
const vendor=process.env.PYROCAST_THREE||path.join(root,'cad-project/work/cad-web/local-resources/cad-assets/three.module.js');
const source=path.join(root,'simulation/results/lite_v8_mc_R2_10_20261026/S09');
const browser=await chromium.launch({headless:true,executablePath:process.env.PYROCAST_BROWSER||'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try{
 const page=await browser.newPage({viewport:{width:800,height:600}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',async route=>{
  const u=new URL(route.request().url());assert.equal(u.hostname,'risk.test');
  if(u.pathname==='/')return route.fulfill({contentType:'text/html',body:'<!doctype html><canvas id="scene"></canvas>'});
  const file=u.pathname==='/three.js'?vendor:u.pathname==='/playback.json'?path.join(source,'playback.json'):u.pathname==='/sample.json'?path.join(source,'sample.json'):path.resolve(root,'.'+u.pathname);
  assert(file===vendor||file.startsWith(root+path.sep));
  return route.fulfill({contentType:file.endsWith('.json')?'application/json':'text/javascript',body:fs.readFileSync(file)});
 });
 await page.goto('https://risk.test/');
 const report=await page.evaluate(async()=>{
  const T=await import('/three.js'),{RiskLayer}=await import('/app/web/layers/risk.js'),{createStore}=await import('/app/web/state/store.js');
  const {adaptBuilding,adaptResult}=await import('/app/web/adapters/read.js');
  const {createCouplingTexture}=await import('/app/web/scene/host.js');
  const playback=await (await fetch('/playback.json')).json(),{scenario}=await (await fetch('/sample.json')).json();
  const building=adaptBuilding({scenario,playback,sourceHash:playback.building_sha256}),result=await adaptResult({playback,scenario,building,resultId:'S09'});
  const store=createStore(),scene=new T.Scene(),layer=new RiskLayer(T);
  store.dispatch('risk/history',{enabled:false});layer.mount(scene,store);
  layer.setData({building,resultMeta:result,series:{cells:result.cells},t_s:1420,floor:{floor_id:'3F'},risk:store.get('risk'),layers:store.get('layers'),selection:store.get('selection')});layer.tick();
  const renderer=new T.WebGLRenderer({canvas:document.querySelector('canvas'),preserveDrawingBuffer:true});renderer.setSize(800,600);
  const box=new T.Box3().setFromObject(layer.group),center=box.getCenter(new T.Vector3()),size=box.getSize(new T.Vector3());
  const camera=new T.PerspectiveCamera(45,800/600,.1,10000);camera.up.set(0,0,1);camera.position.copy(center).add(new T.Vector3(0,-size.y,Math.max(size.x,size.y)*2));camera.lookAt(center);
  renderer.render(scene,camera);
  const gl=renderer.getContext(),pixels=new Uint8Array(800*600*4);gl.readPixels(0,0,800,600,gl.RGBA,gl.UNSIGNED_BYTE,pixels);
  let colored=0;for(let i=0;i<pixels.length;i+=4)if(pixels[i]||pixels[i+1]||pixels[i+2])colored++;
  const texture=createCouplingTexture(T,7),coupling={width:texture.image.width,height:texture.image.height};texture.dispose();
  const diagnostics=layer.diagnostics();layer.dispose();renderer.dispose();
  return {diagnostics,colored,coupling,resources:layer.resources.size,subscriptions:store.diagnostics().subscriptions};
 });
 assert.equal(report.diagnostics.counts.FO,1);assert(report.colored>0);assert.deepEqual(report.coupling,{width:64,height:64});
 assert.equal(report.resources,0);assert.equal(report.subscriptions,0);assert.deepEqual(errors,[]);
 console.log(JSON.stringify({passed:true,...report,errors}));
}finally{await browser.close();}
