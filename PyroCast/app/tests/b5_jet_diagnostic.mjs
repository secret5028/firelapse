import fs from 'node:fs';import path from 'node:path';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),{chromium}=require(process.env.PYROCAST_PLAYWRIGHT||'playwright');
const phase=process.argv[2]||'before',out=path.resolve('reviews/B5-followup-20261103',phase);fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const report={errors:[]};
try{
 const p=await browser.newPage({viewport:{width:1280,height:720},deviceScaleFactor:1});p.setDefaultTimeout(120000);
 p.on('pageerror',e=>report.errors.push(e.message));p.on('console',m=>{if(m.type()==='error')report.errors.push(m.text());});
 await p.addInitScript(()=>{performance.now=()=>180000;const raf=requestAnimationFrame;window.requestAnimationFrame=cb=>raf(()=>cb(180000));});
 await p.route('**/operating.js',async route=>{const r=await route.fetch();await route.fulfill({response:r,body:(await r.text()).replace('const app=await attach(viewer);','const app=await attach(viewer);window.__ui=app;window.__cad=viewer;window.__ready=true;')});});
 await p.goto('http://127.0.0.1:8832/data/wando-coldstore/model.html');await p.waitForFunction(()=>window.__ready);
 await p.evaluate(()=>{const a=window.__ui;a.store.dispatch('realView/set',{smokeMode:'soot',flameStyle:'four_stage'});const r=document.getElementById('liteRoom');r.value='CAD_1F_R5';r.onchange();const t=document.getElementById('liteTime');t.value=1400;t.oninput();document.getElementById('iso').click();document.getElementById('liteFocus').click();});
 const settle=()=>p.evaluate(async()=>{window.__ui.render();for(let i=0;i<4;i++)await new Promise(requestAnimationFrame);});await settle();
 report.geometry=await p.evaluate(()=>{const v=window.__cad,result=[];v.S.traverse(o=>{if(o.userData.doorJet){const u=o.material.uniforms,mask=u.uMask.value.image,im=mask.getContext('2d').getImageData(0,0,mask.width,mask.height);let inside=0,total=0;for(let x=0;x<16;x++)for(let z=0;z<16;z++){const point=new v.THREE.Vector3((x+.5)/16,.5,(z+.5)/16),uv=[u.uMaskOffset.value.x+point.dot(u.uJetMaskX.value),u.uMaskOffset.value.y+point.dot(u.uJetMaskY.value)];total++;if(uv.every(a=>a>=0&&a<1)&&im.data[(Math.floor(uv[1]*mask.height)*mask.width+Math.floor(uv[0]*mask.width))*4]===255)inside++;}result.push({name:o.name,visible:o.visible,position:o.position.toArray(),scale:o.scale.toArray(),renderOrder:o.renderOrder,maskPass:inside/total,values:o.userData.values});}});return result;});
 await p.evaluate(()=>{const v=window.__cad,renderer=window.__ui.host.renderer,render=renderer.render.bind(renderer);renderer.render=(...args)=>{v.S.traverse(o=>{if(window.__hideWall&&o.name.startsWith('cavity-wall-glow:'))o.visible=false;if(window.__hideJets&&o.userData.doorJet)o.visible=false;});render(...args);};});
 for(const [name,hideWall,hideJets] of [['normal',false,false],['no-wall',true,false],['no-jets',true,true]]){
  await p.evaluate(({hideWall,hideJets})=>{window.__hideWall=hideWall;window.__hideJets=hideJets;},{hideWall,hideJets});await settle();
  await p.locator('#v canvas').screenshot({path:path.join(out,'jet-'+name+'.png')});
 }
}finally{fs.writeFileSync(path.join(out,'jet-diagnostic.json'),JSON.stringify(report,null,2));await browser.close();}
