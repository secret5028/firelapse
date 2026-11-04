// Display datum follows the recorded 1F floor, not the lowest basement z.
export function groundReferenceSpec(building){
 const floor=building.floors.find(f=>/^(1F|F1|1층)$/i.test(f.name));
 if(!floor||!Number.isFinite(floor.z))return null;
 const points=(floor.slab||[]).flatMap(p=>p.o||p);if(!points.length)return null;
 const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]);
 const x0=Math.min(...xs),x1=Math.max(...xs),y0=Math.min(...ys),y1=Math.max(...ys);
 const size=Math.ceil((Math.max(x1-x0,y1-y0)+20)*1.5/2)*2;
 return {floor:floor.name,x:(x0+x1)/2,y:(y0+y1)/2,z:floor.z,size,divisions:size/2};
}
export function createGroundReference(T,building){
 const spec=groundReferenceSpec(building);if(!spec)return null;
 const grid=new T.GridHelper(spec.size,spec.divisions,0x7296aa,0x486778);
 grid.name='ground_reference_1F';grid.rotation.x=Math.PI/2;grid.position.set(spec.x,spec.y,spec.z);
 for(const m of Array.isArray(grid.material)?grid.material:[grid.material]){m.transparent=true;m.opacity=.38;m.depthWrite=false;m.depthTest=true;}
 grid.userData.groundReference=spec;grid.raycast=()=>{};
 return grid;
}
