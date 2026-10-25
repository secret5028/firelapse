// Native directional soot flow drives this display. No risk gate or invented room smoke.
import {smokeLayerVisibility} from './smoke_visual.js';

export function transportSignal(flow){
 if(!Array.isArray(flow)||flow.length<7||!flow.every(Number.isFinite)||flow[0]<=1e-6||flow[3]<=1e-10)return {active:false,opacity:0,speed:0};
 return {active:true,opacity:Math.min(.32,.07+.035*Math.log1p(flow[3]*1e5)),speed:Math.min(8,Math.abs(flow[6]))};
}

export function smokePresent(solver,values){
 if(!solver)return false;
 const h=Math.max(0,Math.min(solver.height_m,values.h));
 return smokeLayerVisibility({enabled:true,smokeEnabled:true,opticalDensity:values.upper,
  thickness:solver.single_zone?solver.height_m:solver.height_m-h}).visible||
  (!solver.single_zone&&smokeLayerVisibility({enabled:true,smokeEnabled:true,opticalDensity:values.lower,thickness:h}).visible);
}

export function smokeTimeline(data){
 return data.rooms.map(room=>{const s=data.solvers[room.solver_id];let first=null;
  if(s)for(let i=0;i<data.time_s.length;i++)if(smokePresent(s,{h:s.single_zone?0:s.h?.[i]??s.height_m,upper:s.ODu?.[i]??0,lower:s.single_zone?0:s.ODl?.[i]??0})){first=data.time_s[i];break;}
  const connections=data.openings.filter(v=>v.b!=='OUTSIDE'&&(v.a===room.solver_id||v.b===room.solver_id));
  return {room,first_s:first,internal_openings:connections.length};
 });
}

export function createSmokeTransport(THREE,data,parent){
 const N=8,ports=[];
 for(const opening of data.openings){if(!opening.cad_geometry)continue;for(const direction of [0,1])ports.push({opening,direction,flow:null,signal:{active:false}});}
 const positions=new Float32Array(ports.length*N*3),alphas=new Float32Array(ports.length*N);
 const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.BufferAttribute(positions,3));geometry.setAttribute('alpha',new THREE.BufferAttribute(alphas,1));
 const material=new THREE.ShaderMaterial({transparent:true,depthWrite:false,depthTest:false,
  vertexShader:`attribute float alpha;varying float vAlpha;void main(){vAlpha=alpha;vec4 p=modelViewMatrix*vec4(position,1.);gl_Position=projectionMatrix*p;gl_PointSize=clamp(130.0/max(1.0,-p.z),3.0,42.0);}`,
  fragmentShader:`precision highp float;varying float vAlpha;void main(){float r=length(gl_PointCoord-vec2(.5))*2.;float a=vAlpha*exp(-3.5*r*r)*(1.-smoothstep(.65,1.,r));if(a<.002)discard;gl_FragColor=vec4(.38,.40,.42,a);}`});
 const points=new THREE.Points(geometry,material);points.name='계산된 문별 연기 이동 · 표시 효과';points.renderOrder=14;points.frustumCulled=false;points.raycast=()=>{};parent.add(points);
 let enabled=false,opacity=1,activeCount=0;
 return {
  update({show,floor,sample,smokeOpacity=1}){enabled=show;opacity=smokeOpacity;activeCount=0;points.visible=show;
   for(const p of ports){p.flow=sample(p.direction?p.opening.ba:p.opening.ab);p.signal=transportSignal(p.flow);
    const source=p.direction?p.opening.b:p.opening.a,dest=p.direction?p.opening.a:p.opening.b;
    p.onFloor=floor==='all'||p.opening.cad_floor===floor||data.rooms.some(r=>r.cad_floor===floor&&(r.solver_id===source||r.solver_id===dest));
    if(show&&p.onFloor&&p.signal.active)activeCount++;
   }
   points.visible=show&&activeCount>0;
  },
  animate(ms){if(!enabled||!activeCount)return;
   for(let pi=0;pi<ports.length;pi++){const p=ports[pi],f=p.opening.cad_geometry,active=p.onFloor&&p.signal.active;
    for(let j=0;j<N;j++){const k=pi*N+j;alphas[k]=0;if(!active)continue;
     const phase=((ms*.001*p.signal.speed+j*.31)%2.4)/2.4,along=-.35+phase*2.4;
     const sideways=Math.sin(j*2.4+ms*.0006)*Math.min(.3,p.opening.width_m*.22),sign=p.direction?-1:1;
     positions[k*3]=f.center_m[0]+f.normal_a_to_b[0]*sign*along+f.tangent[0]*sideways;
     positions[k*3+1]=f.center_m[1]+f.normal_a_to_b[1]*sign*along+f.tangent[1]*sideways;
     positions[k*3+2]=p.flow[4]+f.normal_a_to_b[2]*sign*along+.07*Math.sin(j+ms*.001);
     alphas[k]=p.signal.opacity*opacity*Math.sin(Math.PI*phase);
    }
   }
   geometry.attributes.position.needsUpdate=true;geometry.attributes.alpha.needsUpdate=true;
  },
  stats(){return {activeDirections:activeCount,drawCalls:1,basis:'native directional soot/mass/mean velocity; short visual trails, not a resolved smoke front'};}
 };
}
