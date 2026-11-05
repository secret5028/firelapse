import {contains} from '../route/graph.js';
// Reference truck footprint: 8m long, 2.6m wide, rotated around the ground normal.
export function vehicleFitsGround(p,bounds,slab,yaw=0){
 if(!bounds||!p.every(Number.isFinite)||!Number.isFinite(yaw))return false;
 for(let x=-4;x<=4;x+=.5)for(let y=-1.3;y<=1.3;y+=.26){const q=[p[0]+x*Math.cos(yaw)-y*Math.sin(yaw),p[1]+x*Math.sin(yaw)+y*Math.cos(yaw),p[2]];if(q[0]<bounds.min.x||q[0]>bounds.max.x||q[1]<bounds.min.y||q[1]>bounds.max.y||contains(q,slab))return false;}
 return true;
}
