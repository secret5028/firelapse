import {elevatorDoorEvidence} from './elevator_door_evidence.js';
export function nearElevator(opening,cores){
 const points=opening.display_span||opening.geometry_polys?.flatMap(p=>p.o)||opening.polys?.flat()||[];
 if(!points.length)return false;
 const p=[points.reduce((n,v)=>n+v[0],0)/points.length,points.reduce((n,v)=>n+v[1],0)/points.length];
 return cores.some(c=>c.kind==='elev'&&((c.door_ids||[]).includes(opening.id)||(c.region||c.anchor||[]).some(poly=>poly.o.some((a,i)=>{
  const b=poly.o[(i+1)%poly.o.length],dx=b[0]-a[0],dy=b[1]-a[1],t=Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy||1)));
  return Math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)<.8;
 }))));
}
// A shared display adapter. Existing CAD door_elev openings take precedence;
// source-DXF supplements are tied to the exact building hash, never guessed.
export function elevatorDisplayFloor(floor,sourceHash,evidence=elevatorDoorEvidence){
 const record=evidence.find(r=>r.building_sha256===sourceHash)?.floors.find(f=>f.floor===floor.name);
 if(!record?.doors.length)return floor;
 const existing=(floor.openings||[]).filter(o=>o.kind==='door_elev');
 const center=o=>{const p=o.display_span||o.geometry_polys?.flatMap(p=>p.o)||o.polys?.flat()||[];return p.length?[p.reduce((n,v)=>n+v[0],0)/p.length,p.reduce((n,v)=>n+v[1],0)/p.length]:null;};
 const added=record.doors.filter(o=>{const c=center(o);return c&&!existing.some(e=>{const p=center(e);return p&&Math.hypot(p[0]-c[0],p[1]-c[1])<.5;});});
 return added.length?{...floor,openings:[...(floor.openings||[]),...added]}:floor;
}
