import {contains} from '../route/graph.js';
// Reference truck footprint: 8m long, 2.6m wide, axis-aligned on ground.
export function vehicleFitsGround(p,bounds,slab){
 if(!bounds||!p.every(Number.isFinite))return false;
 for(let x=-4;x<=4;x+=.5)for(let y=-1.3;y<=1.3;y+=.26){const q=[p[0]+x,p[1]+y,p[2]];if(q[0]<bounds.min.x||q[0]>bounds.max.x||q[1]<bounds.min.y||q[1]>bounds.max.y||contains(q,slab))return false;}
 return true;
}
