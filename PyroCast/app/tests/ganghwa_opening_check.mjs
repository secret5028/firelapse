import fs from 'node:fs';import path from 'node:path';import {createRequire} from 'node:module';import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(process.env.PYROCAST_PLAYWRIGHT||'playwright'),out=path.resolve('reviews/ganghwa-opening-check-20261103');fs.mkdirSync(out,{recursive:true});
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
window.testScene={T,B,layer,scene,R,C,frame,asset};return {...layer.diagnostics(),elapsed_ms:elapsed,floors:B.floors.map(f=>({name:f.name,openings:f.openings.length}))};},{B,code});
await p.locator('canvas').screenshot({path:path.join(out,'after.png')});

const audit=await p.evaluate(async()=>{
 const {T,B,layer,asset}=window.testScene,{wallOpeningVolumes}=await import('/app/web/layers/wall_opening_lines.js'),rows=[];
 for(const floor of asset.floors){
  const cuts=wallOpeningVolumes(floor.floor),openingById=new Map((floor.floor.openings||[]).map(o=>[o.id,o]));
  for(const cut of cuts){
   const count=object=>{const pos=object.geometry?.attributes.position;if(!pos)return 0;object.updateWorldMatrix(true,false);
    const root=object.userData.__auditOriginal?floor.group:layer.floorGroups.get(floor.id);
    root.updateWorldMatrix(true,false);const m=new T.Matrix4().copy(root.matrixWorld).invert().multiply(object.matrixWorld),a=new T.Vector3(),b=new T.Vector3();let n=0;
    for(let i=0;i+1<pos.count;i+=2){a.fromBufferAttribute(pos,i).applyMatrix4(m);b.fromBufferAttribute(pos,i+1).applyMatrix4(m);
     if(Math.hypot(a.x-b.x,a.y-b.y)>1e-5)continue;
     const u=a.x*cut.u[0]+a.y*cut.u[1],v=a.x*cut.v[0]+a.y*cut.v[1];
     if(v<cut.min[1]||v>cut.max[1]||!(cut.seams||cut.jambs).some(j=>Math.abs(j-u)<=.02))continue;
     if(Math.max(a.z,b.z)>cut.top+.001&&Math.min(a.z,b.z)<Math.max(a.z,b.z)-.001)n++;
    }return n;
   };
   let before=0,after=0;for(const source of floor.objects){if(!source.isLineSegments||!(source.userData.cadOutline||/_(edge|wall)(_|$)/i.test(source.name)))continue;
    source.userData.__auditOriginal=true;before+=count(source);delete source.userData.__auditOriginal;after+=count(layer.sourceObjects.get(source));
   }
   const o=openingById.get(cut.id);rows.push({floor:floor.id,id:cut.id,kind:o.kind,before,after,cut});
  }
 }
 window.testScene.audit=rows;return rows;
});
assert(audit.some(x=>x.before>0));assert(audit.every(x=>x.after===0));
const chosen=['door','window'].map(kind=>audit.filter(x=>x.floor==='3F'&&x.kind===kind&&(kind==='door'?x.id==='D1':x.id==='W2')&&x.before>0&&x.cut.jambs[1]-x.cut.jambs[0]<5).sort((a,b)=>b.before-a.before)[0]);
assert(chosen.every(Boolean));
for(const item of chosen){
 await p.evaluate(item=>{const {T,layer,scene,R,C}=window.testScene,c=item.cut,u=(c.jambs[0]+c.jambs[1])/2,v=(c.min[1]+c.max[1])/2,width=c.jambs[1]-c.jambs[0];
  const target=new T.Vector3(u*c.u[0]+v*c.v[0],u*c.u[1]+v*c.v[1],c.top*.65);layer.floorGroups.get(item.floor).localToWorld(target);
  const distance=Math.max(6,width*3);C.position.copy(target).add(new T.Vector3(c.v[0]*distance+c.u[0]*distance*.25,c.v[1]*distance+c.u[1]*distance*.25,distance*.3));C.lookAt(target);C.updateMatrixWorld();R.render(scene,C);
 },item);
 await p.locator('canvas').screenshot({path:path.join(out,`${item.kind}-${item.id}-after.png`)});
 await p.evaluate(()=>{const {layer,scene,R,C,asset}=window.testScene;for(const floor of asset.floors)for(const source of floor.objects){const o=layer.sourceObjects.get(source);if(o?.isLineSegments||o?.isMesh){o.userData.savedClipped=o.geometry;o.geometry=source.geometry;}}R.render(scene,C);});
 await p.locator('canvas').screenshot({path:path.join(out,`${item.kind}-${item.id}-before.png`)});
 await p.evaluate(()=>{const {layer,scene,R,C}=window.testScene;for(const o of layer.sourceObjects.values())if(o.userData.savedClipped){o.geometry=o.userData.savedClipped;delete o.userData.savedClipped;}R.render(scene,C);});
}
fs.writeFileSync(path.join(out,'jamb-audit.json'),JSON.stringify({rows:audit,chosen},null,2));
console.log(JSON.stringify({total_before:audit.reduce((s,r)=>s+r.before,0),total_after:audit.reduce((s,r)=>s+r.after,0),chosen:chosen.map(({floor,id,kind,before,after})=>({floor,id,kind,before,after}))}));

await p.evaluate(()=>{const {layer,scene,R,C,frame,asset}=window.testScene;layer.geometryFor=()=>({...asset,floors:asset.floors.map(f=>({...f,floor:{}}))});layer.lastBuilding=undefined;layer.setData(frame);R.render(scene,C);});
await p.locator('canvas').screenshot({path:path.join(out,'before.png')});assert(stats.trimmedLines>0);assert.deepEqual(errors,[]);fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify({stats,errors},null,2));console.log(JSON.stringify({trimmedLines:stats.trimmedLines,elapsed_ms:stats.elapsed_ms}));
}finally{await browser.close();}
