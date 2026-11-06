import fs from 'node:fs';import assert from 'node:assert/strict';import {pathToFileURL} from 'node:url';
const T=await import(pathToFileURL('C:/Users/<user>/Desktop/소방 크로키 업-로컬웹앱/개발/work/three.module.js'));
const B=JSON.parse(fs.readFileSync('outputs/CAD-모델링-v10/building.json','utf8'));
const fn=fs.readFileSync('C:/Users/<user>/Documents/Codex/2026-09-07/2/CAD3D/transport_view.js','utf8');
const addTransportGeometry=new Function(fn+';return addTransportGeometry;')();
function shp(p){const s=new T.Shape(p.o.map(q=>new T.Vector2(...q)));for(const h of p.h)s.holes.push(new T.Path(h.map(q=>new T.Vector2(...q))));return s;}
function ext(polys,z0,z1,m){if(!polys.length||z1<=z0)return null;const g=new T.ExtrudeGeometry(polys.map(shp),{depth:z1-z0,bevelEnabled:false,curveSegments:1});g.translate(0,0,z0);return new T.Mesh(g,m);}
const groups=B.floors.map(f=>{const g=new T.Group();g.position.z=f.z;return g;});
const a=addTransportGeometry(T,B,groups,ext);assert.equal(a.roots.length,36);assert.equal(a.ramps.length,1);
let vertices=0,meshes=0;
for(let i=0;i<groups.length;i++){const g=groups[i];g.updateMatrixWorld(true);g.traverse(o=>{if(!o.geometry)return;meshes++;for(const key of ['position','normal']){const ar=o.geometry.attributes[key];if(ar){assert([...ar.array].every(Number.isFinite));if(key==='position')vertices+=ar.count;}}});for(const root of g.children)assert.equal(root.userData.floorIndex,i);}
const ramp=a.ramps[0];for(const percent of [0,10,25])for(const reverse of [false,true]){a.slope(percent,reverse);const ar=ramp.geo.attributes.position;const zs=Array.from({length:ar.count},(_,i)=>ar.getZ(i));assert(Math.abs(Math.min(...zs)-.035)<.0001);assert(Math.abs(Math.max(...zs)-(.035+ramp.data.length_m*percent/100))<.0001);}
const result={status:'passed',three_revision:T.REVISION,transport_objects:meshes,vertices,floor_parenting:'passed',finite_geometry:'passed',ramp_slope_and_reverse:'passed',scope:'CPU geometry construction; no WebGL/browser runtime test'};
fs.writeFileSync('outputs/CAD-모델링-v10/3D형상검사.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
