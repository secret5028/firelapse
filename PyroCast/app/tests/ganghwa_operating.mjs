import fs from 'node:fs';import path from 'node:path';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PYROCAST_PLAYWRIGHT||'playwright'),out=path.resolve('reviews/ganghwa-operating-20261104');fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const report={errors:[],posts:[],captures:[]};
let p;
try{
 p=await browser.newPage({viewport:{width:1440,height:1000}});p.setDefaultTimeout(30000);p.setDefaultNavigationTimeout(30000);p.on('pageerror',e=>(report.errors.push(e.message),console.log('PAGE ERROR',e.message)));p.on('request',r=>{if(r.method()==='POST')report.posts.push(r.url());});
 await p.addInitScript(()=>{performance.now=()=>180000;const raf=requestAnimationFrame;window.requestAnimationFrame=cb=>raf(()=>{if(!window.__holdFrames)cb(180000);});});
 await p.route('**/cad-result/*/model.html',async route=>{const r=await route.fetch();let h=await r.text(),hook='await (await import("/cfbt/overlay.js")).attach({',i=h.indexOf(hook),j=h.indexOf('\n</script>',i);assert(i>=0);const old=h.slice(i,j),arg=old.slice(hook.length-1,old.lastIndexOf(');'));h=h.slice(0,i)+'window.__cad='+arg+';window.__ui=await (await import("/cfbt/overlay.js")).attach(window.__cad);window.__ready=true;'+h.slice(j);await route.fulfill({response:r,body:h});});
 console.log('loading wando');await p.goto('http://127.0.0.1:8832/data/wando-coldstore/model.html');await p.locator('#shellBuilding').waitFor();
 console.log('selecting ganghwa');await p.locator('#shellBuilding').selectOption({label:'강화 공장'});await p.locator('#liteCase option[value="S09"]').waitFor({state:'attached'});await p.reload();await p.waitForFunction(()=>window.__ready);
 console.log('ganghwa ready');report.url=p.url();assert(report.url.includes(':8780/cad-result/'));
 console.log('loading S09');await p.selectOption('#liteCase','S09');await p.waitForFunction(()=>window.__ui?.store.get('result')?.result_id==='S09');
 await p.locator('#fbtn button').filter({hasText:/^3F$/}).click();
 await p.evaluate(()=>{document.getElementById('liteTime').value=1420;document.getElementById('liteTime').oninput();window.__ui.store.dispatch('openings/set',{interior:true,exterior:true});window.__ui.render();});
 await p.screenshot({path:path.join(out,'S09-1420-operating.png')});report.captures.push('S09-1420-operating.png');
 report.scene=await p.evaluate(()=>({building:document.getElementById('shellBuilding').selectedOptions[0].textContent,case:document.getElementById('liteCase').value,time:window.__ui.store.get('playback').t_s,diagnostics:window.__ui.layers.find(l=>l.constructor.id==='building').diagnostics()}));
 await p.evaluate(()=>{window.__holdFrames=true;window.__ui.store.dispatch('realView/set',{enabled:false});window.__ui.store.dispatch('layers/toggle',{id:'risk',visible:false});});
 for(const id of ['D1','W2']){
  const values=await p.evaluate(id=>{const {THREE:T,B,C,O}=window.__cad,ui=window.__ui,layer=ui.layers.find(l=>l.constructor.id==='building'),floor=B.floors.find(f=>f.name==='3F'),o=floor.openings.find(o=>o.id===id),points=(o.polys||[]).flat(),cx=points.reduce((s,p)=>s+p[0],0)/points.length,cy=points.reduce((s,p)=>s+p[1],0)/points.length,top=o.kind==='door'?(o.door_h||floor.door_h||2.1):floor.head;
   O.target.set(cx,cy,floor.z+top*.65);C.position.copy(O.target).add(new T.Vector3(-7,-1.5,2));O.update();ui.render();
   let clippedLines=0,clippedMeshes=0;for(const [source,object] of layer.sourceObjects)if(source.geometry!==object.geometry){if(source.isLineSegments)clippedLines++;if(source.isMesh)clippedMeshes++;}
   return {id,kind:o.kind,top,clippedLines,clippedMeshes};
  },id);assert(values.clippedLines>0&&values.clippedMeshes>0);report[id]=values;
  await p.screenshot({path:path.join(out,`${id}-operating.png`)});report.captures.push(`${id}-operating.png`);
 }
 await p.locator('#shellBuilding').selectOption({label:'완도 저온창고'});await p.waitForFunction(()=>document.getElementById('wandoExterior'));assert(p.url().includes(':8832/data/wando-coldstore/'));report.returnToWando=true;
 assert.deepEqual(report.errors,[]);assert(report.posts.every(url=>url.endsWith('/cfbt/lite/ai/reports/list')));report.simulationRequests=report.posts.filter(url=>!url.endsWith('/cfbt/lite/ai/reports/list')).length;
}catch(e){report.failure=e.message;console.log(e.message);if(p){report.url=p.url();await p.screenshot({path:path.join(out,'failure.png'),timeout:10000}).catch(()=>{});report.body=await p.locator('body').innerText({timeout:10000}).catch(()=>null);}throw e;}finally{fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify(report,null,2));await browser.close();}
