import fs from 'node:fs';import path from 'node:path';import {createRequire} from 'node:module';import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.PYROCAST_PLAYWRIGHT||'playwright'),out=path.resolve('reviews/wall-opening-lines-20261103/other-building');fs.mkdirSync(out,{recursive:true});
const dir='cad-project/',B=JSON.parse(fs.readFileSync(dir+'building.json','utf8')),model=fs.readFileSync(dir+'model.html','utf8'),code=model.slice(model.indexOf('const mat='),model.indexOf('// ---- 문짝'));
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});const errors=[];
try{const p=await browser.newPage({viewport:{width:1100,height:800}});p.on('pageerror',e=>errors.push(e.message));
await p.route('**/wall-lines-test.html',r=>r.fulfill({contentType:'text/html',body:'<html><body style="margin:0"><div id="fl" hidden></div><div id="ck" hidden></div></body></html>'}));
await p.goto('http://127.0.0.1:8832/data/wando-coldstore/wall-lines-test.html');
const stats=await p.evaluate(async({B,code})=>{const T=await import('/vendor/three.module.js'),{BuildingLayer}=await import('/app/web/layers/building.js'),{readLegacyBuildingSource}=await import('/app/web/adapters/legacy_building.js');
const old=new T.Scene();class Label extends T.Object3D{};
const source=new Function('THREE','B','S','CSS2DObject','dark','ceilStateDefault','applyCeil',code+';return {groups,mat,ceilState};')(T,B,old,Label,true,f=>Math.min(f.h-.3,Math.max(f.ceil_rule?.min_h||2.4,f.h-(f.ceil_rule?.plenum||1))),()=>{});
for(const k of ['wall','door_head','win_low','win_head','beam'])Object.assign(source.mat[k],{opacity:.45,transparent:true,depthWrite:false,side:T.DoubleSide});
for(const g of source.groups)for(const m of [...g.children])if(m.isMesh&&['wall','door_head','win_low','win_head','beam'].some(k=>m.material===source.mat[k])){const edge=new T.LineSegments(new T.EdgesGeometry(m.geometry,30),new T.LineBasicMaterial({color:0x9bb8c9,transparent:true,opacity:.45}));edge.userData.cadOutline=true;g.add(edge);}
const asset=readLegacyBuildingSource({building:B,groups:source.groups,sourceHash:'a'.repeat(64)}),scene=new T.Scene();scene.background=new T.Color('#102331');scene.add(new T.HemisphereLight(0xffffff,0x666666,1.6));const R=new T.WebGLRenderer({antialias:true});R.setSize(1100,800);document.body.append(R.domElement);const C=new T.PerspectiveCamera(45,1100/800,.01,2000);C.up.set(0,0,1);
const layer=new BuildingLayer(T,{geometryFor:()=>asset});layer.mount(scene,{subscribe:()=>()=>{}});const frame={building:{source_hash:asset.source_hash},resultMeta:null,floor:{floor_id:'3F'},t_s:0};
const t=performance.now();layer.setData(frame);const elapsed=performance.now()-t;const box=new T.Box3().setFromObject(layer.floorGroups.get('3F')),sphere=box.getBoundingSphere(new T.Sphere());C.position.copy(sphere.center).addScaledVector(new T.Vector3(1,-1,1).normalize(),sphere.radius/Math.sin(T.MathUtils.degToRad(22.5))*1.05);C.lookAt(sphere.center);R.render(scene,C);
window.testScene={layer,scene,R,C,frame,asset};return {...layer.diagnostics(),elapsed_ms:elapsed,floors:B.floors.map(f=>({name:f.name,openings:f.openings.length}))};},{B,code});
await p.locator('canvas').screenshot({path:path.join(out,'after.png')});
await p.evaluate(()=>{const {layer,scene,R,C,frame,asset}=window.testScene;layer.geometryFor=()=>({...asset,floors:asset.floors.map(f=>({...f,floor:{}}))});layer.lastBuilding=undefined;layer.setData(frame);R.render(scene,C);});
await p.locator('canvas').screenshot({path:path.join(out,'before.png')});assert(stats.trimmedLines>0);assert.deepEqual(errors,[]);fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify({stats,errors},null,2));console.log(JSON.stringify({trimmedLines:stats.trimmedLines,elapsed_ms:stats.elapsed_ms}));
}finally{await browser.close();}
