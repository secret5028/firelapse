import fs from 'node:fs';import {performance} from 'node:perf_hooks';import {pathToFileURL} from 'node:url';
import {wallCornerSegments} from '../web/layers/wall_corners.js';import {wallOpeningVolumes} from '../web/layers/wall_opening_lines.js';
const T=await import(pathToFileURL(process.cwd()+'/cad-project/work/cad-web/local-resources/cad-assets/three.module.js'));
const shape=p=>{const s=new T.Shape(p.o.map(v=>new T.Vector2(...v)));for(const h of p.h||[])s.holes.push(new T.Path(h.map(v=>new T.Vector2(...v))));return s;};
const result=[];
for(const [name,path] of [['hotel','data/parkmarine-hotel/building.json'],['ganghwa','cad-project/building.json'],['wando','data/wando-coldstore/operating-building.json']]){
 const b=JSON.parse(fs.readFileSync(path,'utf8')),rows=[];const started=performance.now();
 for(const f of b.floors){const group=new T.Group(),objects=[];group.name=f.name;const add=(geo,z=0)=>{const m=new T.Mesh(geo);m.position.z=z;m.name=f.name+'_wall';objects.push(m);group.add(m);};
  if(f.bands?.length){for(const band of f.bands)if((name==='hotel'?['wall']:['wall','door_head','win_low','win_head']).includes(band.kind)&&band.z1>band.z0&&band.polys.length)add(new T.ExtrudeGeometry(band.polys.map(shape),{depth:band.z1-band.z0,bevelEnabled:false,curveSegments:1}),band.z0);}
  else for(const r of f.rooms)for(const p of r.polys)for(let i=0;i<p.o.length;i++){const a=p.o[i],c=p.o[(i+1)%p.o.length],length=Math.hypot(c[0]-a[0],c[1]-a[1]),thickness=r.id==='CAVITY'?.012:.1;add(new T.BoxGeometry(length,thickness,f.h),f.h/2);const m=objects.at(-1);m.position.x=(a[0]+c[0])/2;m.position.y=(a[1]+c[1])/2;m.rotation.z=Math.atan2(c[1]-a[1],c[0]-a[0]);}
  const positions=wallCornerSegments(T,{group,objects},wallOpeningVolumes(f,2100));if(positions.some(x=>!Number.isFinite(x)))throw Error('Nonfinite edge');rows.push({floor:f.name,segments:positions.length/6});for(const m of objects){m.geometry.dispose();m.material.dispose();}
 }
 result.push({building:name,build_ms:Math.round(performance.now()-started),floors:rows});
}
fs.mkdirSync('reviews/wall-corners-20261104',{recursive:true});fs.writeFileSync('reviews/wall-corners-20261104/geometry.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result.map(r=>({building:r.building,floors:r.floors.length,build_ms:r.build_ms,segments:r.floors.reduce((n,f)=>n+f.segments,0)}))));
