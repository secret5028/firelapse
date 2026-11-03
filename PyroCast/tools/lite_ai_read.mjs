// Server-side read bridge: reuse viewer ranking and route functions, no engine.
import fs from 'node:fs';
import {readRouteGraph,findRoute} from '../app/web/route/graph.js';
import {routeRiskRows} from '../app/web/route/risk.js';
import {adaptBuilding,adaptResult} from '../app/web/adapters/read.js';
import {attentionRanking} from '../app/web/adapters/attention.js';
const a=JSON.parse(fs.readFileSync(0,'utf8'));
if(a.kind==='ranking')console.log(JSON.stringify(attentionRanking(a.payload.comparison,a.payload.attention||{records:[]})));
else {
 const B=a.building,p=a.playback,byRoom=new Map();
 for(const c of p.rooms){const key=c.original_room||c.key;if(byRoom.has(key))continue;
  const f=B.floors.find(f=>f.name===c.cad_floor),r=f?.rooms.find(r=>`CAD_${f.name}_${r.id}`===key);
  if(!r)throw Error('CAD room missing: '+key);
  byRoom.set(key,{id:key,name:r.names?.join(' / ')||key,cad_floor:c.cad_floor,cad_polys:r.polys,z_m:c.z_m,height_m:c.height_m});
 }
 const scenario={rooms:[...byRoom.values()],openings:[],cad:{building_sha256:p.building_sha256}};
 const building=adaptBuilding({scenario,playback:p,sourceHash:p.building_sha256});
 const result=await adaptResult({playback:p,scenario,building,resultId:a.case});
 const graph=readRouteGraph(B),route=findRoute(graph,a.origin,a.vehicle||graph.defaultVehicle,a.settings||{});
 const risk=route.error?null:routeRiskRows(route,{building,resultMeta:result,t_s:a.time_s||0,risk:{history:a.history===true},route:{hose_m:a.settings?.hose_m||15}});
 console.log(JSON.stringify({route,risk}));
}
