const fs=require('fs'),assert=require('assert'),math=require('./cad_cfast_plume_math.js');
const out='outputs/CAD-공식플룸-v29/',data=JSON.parse(fs.readFileSync(out+'cfast-demo.json','utf8'));
const lines=fs.readFileSync('outputs/CAD-속도검증-v27/final/multifloor_devices.csv','utf8').trim().split(/\r?\n/),headers=lines[0].split(','),device=lines.slice(4).map(s=>Object.fromEntries(s.split(',').map((v,i)=>[headers[i],+v])));
const input=fs.readFileSync('outputs/CAD-속도검증-v27/final/multifloor.in','utf8');
const targets=[...input.matchAll(/&DEVC ID='([^']+)' COMP_ID='([^']+)' TYPE='PLATE' LOCATION=([\d.,-]+)/g)].map(m=>({id:m[1],room:m[2],pos:m[3].split(',').map(Number)}));
let maxFlameError=0,maxGasError=0,worst=null,count=0;
for(const f of data.fires){for(let i=0;i<f.hrr.length;i++){const err=Math.abs(math.flame(f.hrr[i]*1000,f.plume_inputs.area)-f.flame_height[i]);maxFlameError=Math.max(maxFlameError,err)}}
for(let i=0;i<device.length;i++)for(let j=0;j<targets.length;j++){
 const t=targets[j],r=data.rooms.find(r=>r.solver_key===t.room),zone=r.series[i],z=t.pos[2];let temp=(z>=zone[3]?zone[1]:zone[2])+273.15;
 for(const f of data.fires.filter(f=>(f.solver_key||f.room_key)===t.room)){
  const p={...f.plume_inputs,q:f.hrr[i]*1000*f.plume_inputs.corner_factor,area:f.plume_inputs.area*f.plume_inputs.corner_factor,tu:zone[1]+273.15,tl:zone[2]+273.15,layer:zone[3]},rr=Math.hypot(t.pos[0]-p.solver_location[0],t.pos[1]-p.solver_location[1]);
  temp=Math.max(temp,math.plume(p,z,rr).temperature,math.ceiling(p,z,rr).temperature);
 }
 const err=Math.abs(temp-273.15-device[i]['TRGGAST_'+(j+1)]);if(err>maxGasError){maxGasError=err;worst={time:device[i].Time,target:t.id,reconstructed:temp-273.15,native:device[i]['TRGGAST_'+(j+1)]}}count++;
}
const p={q:1000000,area:2,chi:.33,tu:400,tl:293.15,layer:2,base:0,height:5};
assert.equal(math.flame(0,2),0);assert.equal(math.plume({...p,q:0},3,0).velocity,0);
assert(math.plume(p,3,0).temperature>math.plume(p,3,3).temperature);
assert(math.plume(p,3,0).velocity>math.plume(p,3,3).velocity);
const c=math.ceiling(p,5,2);assert(c.thickness>0&&c.thickness<.112*5&&c.velocity>0);assert.equal(math.ceiling(p,4,2).velocity,0);
assert.equal(math.ceiling({...p,base:5},5,0).velocity,0);
const probes=JSON.parse(fs.readFileSync(out+'probe/cases.json','utf8'));let probeError=0,probeWorst=null;
for(const a of probes){const p={...a,area:2,chi:.33,base:0,height:5},predicted=Math.max(a.z>=a.layer?a.tu:a.tl,math.plume(p,a.z,a.r).temperature,math.ceiling(p,a.z,a.r).temperature)-273.15,err=Math.abs(predicted-a.native);if(err>probeError){probeError=err;probeWorst={...a,predicted}}}
const report={nativeGasChecks:count,maxFlameError_m:maxFlameError,maxGasError_C:maxGasError,worst,nativeProbeCases:probes.length,probeError_C:probeError,probeWorst,edgeTests:'passed',physicalValidation:false};
fs.writeFileSync(out+'공식식-출력대조.json',JSON.stringify(report,null,2));console.log(report);
assert(maxFlameError<.0001);assert(maxGasError<.1,'Native target gas temperature mismatch');
assert(probeError<.01,'Native plume/ceiling probe mismatch');
