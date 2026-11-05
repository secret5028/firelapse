// Display-only completion: registered doors have a lintel up to floor height.
// Subtract existing wall bands exactly in XY; do not change CAD or solver input.
const cross=(a,b,p)=>(b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]);
const area=p=>p.reduce((s,a,i)=>{const b=p[(i+1)%p.length];return s+a[0]*b[1]-b[0]*a[1];},0)/2;
const orient=p=>area(p)<0?[...p].reverse():p;
function half(poly,a,b,inside){const out=[];for(let i=0;i<poly.length;i++){const p=poly[i],q=poly[(i+1)%poly.length],x=cross(a,b,p),y=cross(a,b,q),ip=inside?x>=-1e-9:x<=1e-9,iq=inside?y>=-1e-9:y<=1e-9;if(ip)out.push(p);if(ip!==iq){const t=x/(x-y);out.push(p.map((v,k)=>v+(q[k]-v)*t));}}return out;}
function subtract(poly,triangle){let rest=poly;const out=[];for(let i=0;i<3&&rest.length>=3;i++){const a=triangle[i],b=triangle[(i+1)%3],outside=half(rest,a,b,false);if(outside.length>=3&&Math.abs(area(outside))>1e-8)out.push(outside);rest=half(rest,a,b,true);}return out;}
const bounds=p=>[Math.min(...p.map(v=>v[0])),Math.min(...p.map(v=>v[1])),Math.max(...p.map(v=>v[0])),Math.max(...p.map(v=>v[1]))];
const overlaps=(a,b)=>a[0]<b[2]-1e-8&&a[2]>b[0]+1e-8&&a[1]<b[3]-1e-8&&a[3]>b[1]+1e-8;
function triangles(T,poly){const p=poly.o||poly,holes=poly.h||[],points=[...p,...holes.flat()],faces=T.ShapeUtils.triangulateShape(p.map(v=>new T.Vector2(...v)),holes.map(h=>h.map(v=>new T.Vector2(...v))));return faces.map(f=>orient(f.map(i=>points[i])));}
export function missingDoorHeaders(T,floor){
 // Without explicit wall bands the original wall renderer already spans full height.
 if(!floor.bands?.length)return [];
 const height=floor.h;if(!Number.isFinite(height))return [];
 const covering=floor.bands.filter(b=>['wall','door_head','win_low','win_head'].includes(b.kind)).map(b=>({...b,triangles:b.polys.flatMap(p=>triangles(T,p))})),added=[];
 for(const o of floor.openings||[]){if(!['door','door_elev'].includes(o.kind)||o.superseded_by||String(o.connection_status).startsWith('superseded'))continue;
  const head=o.door_h??floor.door_h??2.1;if(!(head<height))continue;const footprints=o.polys?.length?o.polys:o.geometry_polys||[];if(!footprints.length)continue;
  const source=footprints.flatMap(p=>triangles(T,p));if(!source.length)continue;const levels=[head,height,...covering.flatMap(b=>[b.z0,b.z1]).filter(z=>z>head&&z<height)].sort((a,b)=>a-b);
  for(let i=1;i<levels.length;i++){const z0=levels[i-1],z1=levels[i];if(z1-z0<1e-7)continue;let parts=source;const cover=covering.filter(b=>b.z0<z1-1e-7&&b.z1>z0+1e-7).flatMap(b=>b.triangles);
   for(const tri of cover){const box=bounds(tri);parts=parts.flatMap(p=>overlaps(bounds(p),box)?subtract(p,tri):[p]);if(!parts.length)break;}
   if(!parts.length)continue;const band={kind:'door_head',opening_id:o.id,z0,z1,polys:parts.map(o=>({o,h:[]})),display_inferred:true};added.push(band);covering.push({...band,triangles:parts.flatMap(p=>triangles(T,p))});
  }
 }
 return added;
}
