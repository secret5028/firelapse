import assert from 'node:assert/strict';
import {pathToFileURL,fileURLToPath} from 'node:url';
import path from 'node:path';
import {BuildingLayer} from '../web/layers/building.js';
import {readLegacyBuildingSource} from '../web/adapters/legacy_building.js';
import {createStore} from '../web/state/store.js';
const root=fileURLToPath(new URL('../../',import.meta.url));
const T=await import(pathToFileURL(process.env.PYROCAST_THREE||path.join(root,'simulation/results/github-publish-20261026/PyroCast/cad-project/work/cad-web/local-resources/cad-assets/three.module.js')));
const floor=new T.Group();floor.name='3F';
const shared=new T.MeshBasicMaterial({color:0x7fc8ff,transparent:true,opacity:.35});
const fallback=new T.MeshBasicMaterial({color:0x8a8a8a,opacity:.8});
const outline=new T.LineBasicMaterial({color:0xffffff,transparent:true,opacity:.7});
const geometry=new T.BoxGeometry();
for(const [name,material] of [['3F_W1',shared],['3F_W2',shared],['wall',fallback]]){const o=new T.Mesh(geometry,material);o.name=name;floor.add(o);}
const line=new T.LineSegments(geometry,outline);line.userData.cadOutline=true;floor.add(line);
const original=[shared,fallback,outline].map(material=>({material,color:material.color.getHex(),opacity:material.opacity,transparent:material.transparent}));
let disposedMaterials=0,disposedGeometry=0,subscriptions=0;
for(const m of original)m.material.addEventListener('dispose',()=>disposedMaterials++);
geometry.addEventListener('dispose',()=>disposedGeometry++);
const store={subscribe(){subscriptions++;return ()=>subscriptions--;}};
const building={source_hash:'a'.repeat(64),floors:[{name:'3F'}]};
const asset=readLegacyBuildingSource({building,groups:[floor],sourceHash:building.source_hash});
for(let cycle=0;cycle<50;cycle++){
 const layer=new BuildingLayer(T,{geometryFor:()=>asset});layer.mount(new T.Scene(),store);
 layer.setData({building,resultMeta:null,floor:{floor_id:'3F'}});
 assert.equal(layer.resources.size,0);assert.equal(layer.materialState.size,3);
 for(const [source,clone] of layer.sourceObjects){assert.equal(clone.material,source.material);assert.equal(clone.geometry,source.geometry);}
 assert.equal(shared.color.getHexString(),'aab7c0');assert.equal(fallback.color.getHexString(),'b8c3cb');
 assert.equal(outline.color.getHexString(),'bdcbd5');assert.equal(outline.opacity,.42);
 const builds=layer.buildCount;
 for(const t of [1,0,.9,.9,.7]){
  layer.setData({building,resultMeta:null,floor:{floor_id:'3F'},realView:{buildingTransparency:t}});
  assert.equal(layer.buildCount,builds);
  if(t===1){assert.equal(shared.opacity,0);assert.equal(shared.depthWrite,false);}
  if(t===0)assert.equal(shared.opacity,1);
  if(t===.9)assert(Math.abs(shared.opacity-.35/3)<1e-12);
 }
 assert.equal(shared.opacity,.35);assert.equal(outline.opacity,.42);assert.equal(shared.depthWrite,true);
 // Exercise restoration on rebuild and final dispose, including transparent.
 shared.transparent=false;layer.build(asset);assert.equal(shared.transparent,true);
 shared.transparent=false;layer.dispose();layer.dispose();
 for(const {material,color,opacity,transparent} of original){assert.equal(material.color.getHex(),color);assert.equal(material.opacity,opacity);assert.equal(material.transparent,transparent);}
 assert.equal(layer.materialState.size,0);assert.equal(subscriptions,0);
}
assert.equal(disposedMaterials,0);assert.equal(disposedGeometry,0);
const settings=createStore();assert.equal(settings.get('realView').buildingTransparency,.7);
for(const x of [-1,1.1,NaN,'0.5'])assert.throws(()=>settings.dispatch('realView/set',{buildingTransparency:x}));
settings.dispatch('realView/set',{buildingTransparency:.9});assert.equal(settings.get('realView').buildingTransparency,.9);
console.log(JSON.stringify({cycles:50,material_identity:true,restore_color_opacity_transparent:true,owned_resources:0,disposedMaterials,disposedGeometry,subscriptions}));

// Basement opacity must not bleed into the above-ground floor's shared material.
const underground=new T.Group();underground.name='B1';
const basementMesh=new T.Mesh(geometry,shared);basementMesh.name='B1_W1';underground.add(basementMesh);
const both={source_hash:'b'.repeat(64),floors:[{name:'3F'},{name:'B1'}]};
const bothAsset=readLegacyBuildingSource({building:both,groups:[floor,underground],sourceHash:both.source_hash});
let released=0;
for(let i=0;i<50;i++){
 const layer=new BuildingLayer(T,{geometryFor:()=>bothAsset});layer.mount(new T.Scene(),store);
 layer.setData({building:both,floor:{floor_id:null}});
 const material=layer.sourceObjects.get(basementMesh).material;material.addEventListener('dispose',()=>released++);
 assert.notEqual(material,shared);assert.equal(shared.opacity,.35);assert.equal(material.opacity,.35*.8);
 layer.setData({building:both,floor:{floor_id:'B1'}});assert.equal(material.opacity,shared.opacity);
 layer.setData({building:both,floor:{floor_id:null},realView:{buildingTransparency:1}});assert.equal(material.opacity,0);
 layer.dispose();assert.equal(layer.basementMaterials.size,0);assert.equal(shared.opacity,.35);
}
assert.equal(released,50);assert.equal(disposedMaterials,0);assert.equal(disposedGeometry,0);assert.equal(subscriptions,0);
console.log('basement: shared-material isolation, floor restoration and 50 disposal cycles PASS');
