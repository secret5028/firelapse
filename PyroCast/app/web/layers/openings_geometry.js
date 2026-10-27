// Exact display geometry helper from frozen lite_viewer.js; no shader or simulation code.
export function exteriorWindowFace(floor, opening) {
 if(opening.kind!=='window'||(opening.connection_status!=='exterior'&&!(opening.sides||[]).includes('out')))return null;
 const rooms=(floor.rooms||[]).filter(r=>(opening.sides||[]).includes(r.id));
 const labels=[opening.name,opening.label,...rooms.flatMap(r=>r.names||[])].join(' ');
 if(/테라스|난간|발코니|terrace|railing|balcony/i.test(labels))return null;
 const span=Number(opening.span),bottom=opening.sill??floor.sill??.9,top=opening.head??floor.head??2.4;
 if(!(span>=.4&&span<=3.01&&top>bottom&&top-bottom<=2.4))return null;
 // Use the opening footprint, not all decorative CAD line fragments.
 const rings=opening.polys?.length?opening.polys:(opening.geometry_polys||[]).map(p=>p.o);
 const points=(rings||[]).flat();if(points.length<3)return null;
 let box=null;
 for(const ring of rings)for(let i=0;i<ring.length;i++){
  const a=ring[i],b=ring[(i+1)%ring.length],len=Math.hypot(b[0]-a[0],b[1]-a[1]);if(len<1e-6)continue;
  const u=[(b[0]-a[0])/len,(b[1]-a[1])/len],v=[-u[1],u[0]];
  const us=points.map(p=>p[0]*u[0]+p[1]*u[1]),vs=points.map(p=>p[0]*v[0]+p[1]*v[1]);
  const lo=Math.min(...us),hi=Math.max(...us),near=Math.min(...vs),far=Math.max(...vs),area=(hi-lo)*(far-near);
  if(!box||area<box.area)box={u,v,lo,hi,near,far,area};
 }
 if(!box)return null;
 if(box.hi-box.lo<box.far-box.near){const {u,v,lo,hi,near,far,area}=box;box={u:v,v:u,lo:near,hi:far,near:lo,far:hi,area};}
 const {u,v,lo,hi,near,far}=box,width=hi-lo,depth=far-near;
 if(width<.4||width>3.6||depth>.65||depth<.01)return null;
 const middle=[u[0]*(lo+hi)/2+v[0]*(near+far)/2,u[1]*(lo+hi)/2+v[1]*(near+far)/2];
 function inRing(p,ring){let inside=false;for(let i=0,j=ring.length-1;i<ring.length;j=i++){
  const a=ring[i],b=ring[j];if((a[1]>p[1])!==(b[1]>p[1])&&p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0])inside=!inside;
 }return inside;}
 const inRoom=p=>rooms.some(r=>(r.polys||[]).some(poly=>inRing(p,poly.o)&&!(poly.h||[]).some(h=>inRing(p,h))));
 const offset=depth/2+.35,plus=inRoom([middle[0]+v[0]*offset,middle[1]+v[1]*offset]),minus=inRoom([middle[0]-v[0]*offset,middle[1]-v[1]*offset]);
 let outer;
 if(plus!==minus)outer=plus?near:far;
 else {const c=rooms.find(r=>r.c)?.c;if(!c)return null;outer=(c[0]-middle[0])*v[0]+(c[1]-middle[1])*v[1]>0?near:far;}
 const at=(t,z)=>[u[0]*t+v[0]*outer,u[1]*t+v[1]*outer,z];
 const sign=outer===near?-1:1;
 return {corners:[at(lo,bottom),at(hi,bottom),at(hi,top),at(lo,top)],normal:[v[0]*sign,v[1]*sign,0],center:at((lo+hi)/2,(bottom+top)/2)};
}
