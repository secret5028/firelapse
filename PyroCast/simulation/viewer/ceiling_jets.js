// Native CFAST ceiling-jet samples; motion trails only, never a new smoke distribution.
export function jetSignal(speed){return Number.isFinite(speed)&&speed>1e-4?Math.min(8,speed):0;}
export function createCeilingJets(T,data,parent){
 const jets=data.ceiling_jets||[],N=4,positions=new Float32Array(jets.length*N*3),alpha=new Float32Array(jets.length*N);
 const geometry=new T.BufferGeometry();geometry.setAttribute('position',new T.BufferAttribute(positions,3));geometry.setAttribute('alpha',new T.BufferAttribute(alpha,1));
 const material=new T.ShaderMaterial({transparent:true,depthWrite:false,depthTest:false,
  vertexShader:`attribute float alpha;varying float a;void main(){a=alpha;vec4 p=modelViewMatrix*vec4(position,1.);gl_Position=projectionMatrix*p;gl_PointSize=clamp(90./max(1.,-p.z),2.,15.);}`,
  fragmentShader:`precision highp float;varying float a;void main(){float r=length(gl_PointCoord-vec2(.5))*2.;float v=a*exp(-5.*r*r);if(v<.005)discard;gl_FragColor=vec4(.75,.8,.83,v);}`});
 const points=new T.Points(geometry,material);points.name='천장 제트 · native 대표속도 표시';points.frustumCulled=false;points.raycast=()=>{};points.renderOrder=15;parent.add(points);
 let active=[],enabled=false;
 return {
  update({show,floor,sample}){enabled=show;active=jets.map(j=>({j,on:show&&(floor==='all'||data.rooms.some(r=>r.solver_id===j.room&&r.cad_floor===floor)),speed:jetSignal(sample(j.speed_m_s)),thickness:Math.max(.025,sample(j.thickness_m))}));points.visible=show&&active.some(p=>p.on&&p.speed>0);},
  animate(ms){if(!enabled)return;for(let i=0;i<active.length;i++){const p=active[i],j=p.j;for(let n=0;n<N;n++){const k=i*N+n;alpha[k]=0;if(!p.on||!p.speed)continue;const phase=(ms*.001*p.speed+n*.37)%j.display_length_m;positions[k*3]=j.position_m[0]+j.direction[0]*phase;positions[k*3+1]=j.position_m[1]+j.direction[1]*phase;positions[k*3+2]=j.position_m[2]-p.thickness*(.15+n*.14);alpha[k]=.25*Math.sin(Math.PI*phase/j.display_length_m);}}geometry.attributes.position.needsUpdate=true;geometry.attributes.alpha.needsUpdate=true;},
  count(){return active.filter(p=>p.on&&p.speed>0).length;},hasData:jets.length>0
 };
}
