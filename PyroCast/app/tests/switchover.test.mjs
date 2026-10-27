import fs from 'node:fs';import path from 'node:path';import {fileURLToPath} from 'node:url';import {createRequire} from 'node:module';import {execFileSync} from 'node:child_process';
const require=createRequire(import.meta.url),{chromium}=require(process.env.PYROCAST_PLAYWRIGHT||'playwright');
const root=fileURLToPath(new URL('../../',import.meta.url)),out=process.env.PYROCAST_UI_COMPARISON_OUT||path.join(root,'simulation/results/ui_refactor_stage3_switchover_20261027');
const origin='http://127.0.0.1:8780',url=origin+'/cad-result/d018b4bb75da4475b1fd75447603c1a0/model.html';
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const reports=[],pages=[];
async function installScopeProbe(){
 const {B,groups,R}=window.__cad,source=await (await fetch('/cfbt/lite_viewer.js')).text(),start=source.indexOf('for(const f of B.floors)groups.find'),end=source.indexOf('for(const room of data.rooms)',start);
 const touched=new Map(),colors=new Map(),objects=[];let current;
 const shadow=groups.map(group=>({name:group.name,traverse(fn){group.traverse(object=>{current=object;objects.push(object);const color=object.material?.color;
  if(color&&!colors.has(object.material))colors.set(object.material,color.getHex());
  const fake={name:object.name,isLineSegments:object.isLineSegments,userData:object.userData,material:color?{color:{getHex:()=>colors.get(object.material),set:value=>{colors.set(object.material,parseInt(value.slice(1),16));touched.set(current,{color:value,opacity:null});}},set opacity(value){touched.get(current).opacity=value;}}:null};fn(fake);
 });}}));
 if(start<0||end<start)throw Error('Missing original install block');new Function('B','groups',source.slice(start,end))(B,shadow);
 window.__installTargets=touched;
 const draw=R.renderBufferDirect,render=R.render;window.__drawn=[];
 R.renderBufferDirect=function(...args){window.__drawn.push(args[4]);return draw.apply(this,args);};
 R.render=function(...args){window.__drawn=[];return render.apply(this,args);};
 window.__scopeReport=()=>{
  const building=window.__ui?.layers.find(l=>l.constructor.id==='building');
  const visible=object=>{for(let n=object;n;n=n.parent)if(!n.visible)return false;return true;};
  const rows=[...touched].map(([object,style])=>{let n=object;while(n&&!groups.includes(n))n=n.parent;const clone=building?.sourceObjects.get(object);return {name:object.name||'(unnamed)',type:object.type,floor:n?.name,parent:object.parent?.name||object.parent?.type,style,visible:visible(object),clone:!!clone,clone_color:clone?.material.color.getHexString(),clone_opacity:clone?.material.opacity,original_draws:window.__drawn.filter(x=>x===object).length,clone_draws:window.__drawn.filter(x=>x===clone).length};});
  const extras=building?[...building.sourceObjects].filter(([source])=>!touched.has(source)).map(([o])=>o.name):[];
  return {original_install_count:touched.size,clone_count:building?.sourceObjects.size??0,extra_clones:extras,rows,render_info:{...R.info.render},pick_draw_calls:window.__drawn.filter(o=>o.material?.opacity===0&&o.userData.liteRoom).length};
 };
 window.__bboxHits=points=>{const {THREE:T,C}=window.__cad,rect=R.domElement.getBoundingClientRect(),ray=new T.Raycaster();ray.params.Line.threshold=.05;
  return points.map(p=>{ray.setFromCamera(new T.Vector2((p.x-rect.x)/rect.width*2-1,-(p.y-rect.y)/rect.height*2+1),C);return {...p,hits:ray.intersectObjects([...new Set(window.__drawn)],false).slice(0,8).map(h=>({name:h.object.name||'(unnamed)',type:h.object.type,parent:h.object.parent?.name||h.object.parent?.type,distance:h.distance,color:h.object.material?.color?.getHexString(),opacity:h.object.material?.opacity}))};});};
}
try{
 for(const mode of ['legacy','modern']){
  const page=await browser.newPage({viewport:{width:1440,height:1080},deviceScaleFactor:1,colorScheme:'dark'}),errors=[];pages.push({mode,page,errors});page.setDefaultTimeout(120000);
  page.on('pageerror',e=>{errors.push(e.message);console.error(mode+': '+e.stack);});
  await page.addInitScript(()=>{performance.now=()=>180000;const raf=window.requestAnimationFrame.bind(window);window.requestAnimationFrame=cb=>raf(()=>cb(180000));});
  await page.route('**/*',async route=>{
   const req=route.request(),u=new URL(req.url());if(req.method()!=='GET'){await route.fulfill({status:403,body:'Read-only capture'});return;}
   if(u.pathname==='/cfbt/overlay.js')return route.fulfill({body:fs.readFileSync(path.join(out,'overlay.js')),contentType:'text/javascript'});
   if(u.pathname==='/cfbt/lite/active.json'){const r=await route.fetch({url:origin+'/cfbt/lite/result/S09'});return route.fulfill({response:r});}
   if(u.pathname.endsWith('/model.html')){const r=await route.fetch();let html=await r.text();const hook='await (await import("/cfbt/overlay.js")).attach({',start=html.indexOf(hook),end=html.indexOf('\n</script>',start),old=html.slice(start,end),object=old.slice(hook.length-1,old.lastIndexOf(');'));
    if(start<0)throw Error('Missing attach hook');html=html.slice(0,start)+'window.__cad='+object+';await ('+installScopeProbe.toString()+')();window.__ui=await (await import("/cfbt/overlay.js")).attach(window.__cad);window.__uiReady=true;'+html.slice(end);return route.fulfill({response:r,body:html});}
   return route.continue();
  });
  await page.goto(url+(mode==='legacy'?'?ui=legacy':''));
  await page.waitForFunction(()=>window.__uiReady&&document.body.classList.contains('cfbtReady'));
  if(errors.length)throw Error(mode+': '+errors.join('; '));
  await page.evaluate(()=>{document.querySelector('#reviewClose').click();});
 }
 const s06=JSON.parse(fs.readFileSync(path.join(root,'simulation/results/lite_v8_mc_R2_10_20261026/S06/playback.json')));
 const first=Math.min(...Object.values(s06.solvers).map(s=>s.display_v8.color.indexOf('#ef4444')).filter(i=>i>=0)),foTime=s06.time_s[first+1];
 const scenarios=[{name:'S09-1800',caseId:'S09',time:1800},{name:'S09-1420',caseId:'S09',time:1420},{name:'S06-FO',caseId:'S06',time:foTime},{name:'all-core',caseId:'S09',time:1800,all:true}];
 for(const scenario of scenarios){const row={...scenario};
  for(const {mode,page,errors} of pages){
   await page.evaluate(async s=>{
    const $=id=>document.getElementById(id);if($('liteCase').value!==s.caseId){$('liteCase').value=s.caseId;await $('liteCase').onchange();}
    const selected=[...$('liteRoom').options].find(x=>x.value==='CAD_3F_R2_C0')||[...$('liteRoom').options].find(x=>x.value==='CAD_3F_R2');$('liteRoom').value=selected.value;$('liteRoom').onchange();
    $('liteTime').value=s.time;$('liteTime').oninput();$('liteCores').checked=true;$('liteCores').onchange();
    if(s.all)$('liteBuilding').click();else{[...$('fbtn').children].find(b=>b.textContent==='3F').click();$('liteWhole').click();}
    await document.fonts.ready;for(let i=0;i<6;i++)await new Promise(requestAnimationFrame);
   },scenario);
   row[mode]=await page.evaluate(()=>({panel:document.querySelector('#cfbtPanel').innerHTML,caption:document.querySelector('.cfbtSceneCaption').textContent,canvas:document.querySelectorAll('#v canvas').length,legend:document.querySelectorAll('#cfMeaning').length,pose:{position:window.__cad.C.position.toArray(),target:window.__cad.O.target.toArray(),zoom:window.__cad.C.zoom},ui:document.documentElement.dataset.pyrocastUi,diagnostics:window.__ui?.diagnostics?.(),scope:window.__scopeReport()}));
   if(mode==='modern'){const s=row.modern.scope;if(s.extra_clones.length||s.clone_count!==s.original_install_count||s.rows.some(x=>!x.clone||x.clone_color!==x.style.color.slice(1)||x.style.opacity!==null&&x.clone_opacity!==x.style.opacity))throw Error('Install target/colour mismatch');}
   if(errors.length)throw Error(mode+': '+errors.join('; '));
   await page.screenshot({path:path.join(out,`${scenario.name}-${mode}.png`),fullPage:true});
  }
  const diff=JSON.parse(execFileSync(process.env.PYROCAST_PYTHON||'python',['app/tests/compare_switchover.py',scenario.name,out],{cwd:root,encoding:'utf8'}));row.diff=diff;
  if(diff.changed_pixels){const [x0,y0,x1,y1]=diff.bbox_inclusive,points=[.25,.5,.75].map(f=>({x:x0+(x1-x0)*f,y:(y0+y1)/2}));for(const {mode,page} of pages)row[mode].hits=await page.evaluate(p=>window.__bboxHits(p),points);}
  reports.push(row);fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify({reports},null,2));
  console.log(JSON.stringify({name:scenario.name,diff,panel_equal:row.legacy.panel===row.modern.panel,camera_equal:JSON.stringify(row.legacy.pose)===JSON.stringify(row.modern.pose)}));
  if(diff.changed_pixels)throw Error('VISUAL DIFFERENCE: stop; bbox/hits saved; no further correction');
 }
}finally{await browser.close();}
