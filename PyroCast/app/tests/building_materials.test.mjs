import assert from 'node:assert/strict';
import {pathToFileURL,fileURLToPath} from 'node:url';
import path from 'node:path';
import {BuildingLayer} from '../web/layers/building.js';
import {readLegacyBuildingSource} from '../web/adapters/legacy_building.js';
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
 // Exercise restoration on rebuild and final dispose, including transparent.
 shared.transparent=false;layer.build(asset);assert.equal(shared.transparent,true);
 shared.transparent=false;layer.dispose();layer.dispose();
 for(const {material,color,opacity,transparent} of original){assert.equal(material.color.getHex(),color);assert.equal(material.opacity,opacity);assert.equal(material.transparent,transparent);}
 assert.equal(layer.materialState.size,0);assert.equal(subscriptions,0);
}
assert.equal(disposedMaterials,0);assert.equal(disposedGeometry,0);
console.log(JSON.stringify({cycles:50,material_identity:true,restore_color_opacity_transparent:true,owned_resources:0,disposedMaterials,disposedGeometry,subscriptions}));
