// Procedural volume rendering. The two-zone heights and extinction come from CFAST;
// the small-scale billows and flame flicker are illustrative, not a CFD velocity field.
function createCfastRealistic({rows,roots,geometry,fire,centre,floorIndex,fires}){
 const volumes=[],box=new THREE.BoxGeometry(1,1,1);box.translate(.5,.5,.5);
 const noise=`
 float hash(vec3 p){p=fract(p*.3183099+vec3(.11,.23,.37));p*=17.;return fract(p.x*p.y*p.z*(p.x+p.y+p.z));}
 float noise3(vec3 p){vec3 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);
 return mix(mix(mix(hash(i),hash(i+vec3(1,0,0)),f.x),mix(hash(i+vec3(0,1,0)),hash(i+vec3(1,1,0)),f.x),f.y),mix(mix(hash(i+vec3(0,0,1)),hash(i+vec3(1,0,1)),f.x),mix(hash(i+vec3(0,1,1)),hash(i+vec3(1,1,1)),f.x),f.y),f.z);}
 float billow(vec3 p){return .68*noise3(p)+.32*noise3(p*2.07+7.);}
 `;
 const vertex=`varying vec3 vLocal;void main(){vLocal=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`;
 const fragment=`precision highp float;
 varying vec3 vLocal;uniform vec3 uCamera,uSize;uniform sampler2D uMask;
 uniform float uTime,uOD,uFire,uStyle,uPhase;${noise}
 void main(){
 vec3 ray=normalize(vLocal-uCamera),safeRay=sign(ray)*max(abs(ray),vec3(.00001));
 vec3 ta=(vec3(0.)-uCamera)/safeRay,tb=(vec3(1.)-uCamera)/safeRay;
 vec3 mn=min(ta,tb),mx=max(ta,tb);float start=max(0.,max(mn.x,max(mn.y,mn.z))),end=min(mx.x,min(mx.y,mx.z));
 if(end<=start)discard;float ds=(end-start)/32.,worldStep=length(ray*uSize)*ds;
 vec4 sum=vec4(0.);float jitter=fract(gl_FragCoord.x*.06711056+gl_FragCoord.y*.00583715);
 for(int i=0;i<32;i++){
 vec3 p=uCamera+ray*(start+(float(i)+jitter)*ds);float mask=texture2D(uMask,p.xy).r;
 if(mask>.5){
 if(uFire>.5){
 // Three variations of the original compact flame; no detached ribbons.
 float variant=mod(floor(uPhase/2.17+.1),3.);
 float speed=mix(2.8,2.3+variant*.55,uStyle);
 float z=p.z;vec3 npos=vec3(p.xy*(5.+uStyle*variant*.6),z*5.-uTime*speed+uPhase);float n=billow(npos);
 vec2 drift=vec2(sin(z*8.-uTime*(2.+variant*.15)+uPhase),cos(z*9.-uTime*2.3+uPhase))*.07*z;
 float radius=length((p.xy-.5+drift)*2.);float width=pow(max(.001,1.-z),1.+uStyle*(variant-1.)*.06);
 float body=1.-radius/max(.01,width)+(n-.5)*(1.1+uStyle*variant*.12);
 float d=max(0.,body)*smoothstep(0.,.04,z)*(1.-smoothstep(.91,1.,z));
 float a=(1.-exp(-d*worldStep*5.));vec3 col=mix(vec3(1.,.12,.012),vec3(1.,.83,.22),clamp(d*1.6-z*.3,0.,1.));
 col=mix(col,vec3(1.,.97,.76),smoothstep(.85,1.35,d)*(1.-z));sum.rgb+=(1.-sum.a)*col*a;sum.a+=(1.-sum.a)*a;
 }else{
 vec3 wp=p*uSize;float n=billow(wp*.65+vec3(uTime*.09,-uTime*.06,-uTime*.035));
 float edge=smoothstep(0.,.08,p.z)*smoothstep(0.,.025,1.-p.z);
 float d=uOD*2.302585*mix(.25,1.75,smoothstep(.12,.88,n))*edge;
 float a=1.-exp(-d*worldStep);vec3 col=mix(vec3(.13,.15,.17),vec3(.48,.50,.51),n*.65+p.z*.25);
 sum.rgb+=(1.-sum.a)*col*a;sum.a+=(1.-sum.a)*a;
 }
 }if(sum.a>.985)break;
 }if(sum.a<.003)discard;gl_FragColor=vec4(sum.rgb/max(sum.a,.001),sum.a);
 }`;
 // Diagnostic overlay: smoke is drawn over geometry, then flames over all smoke.
 // This changes visibility only, not extinction, temperature, HRR or ignition.
 function make(mask,root){const mat=new THREE.ShaderMaterial({uniforms:{uCamera:{value:new THREE.Vector3()},uSize:{value:new THREE.Vector3()},uMask:{value:mask},uTime:{value:0},uOD:{value:0},uFire:{value:0},uStyle:{value:0},uPhase:{value:0}},vertexShader:vertex,fragmentShader:fragment,transparent:true,depthWrite:false,depthTest:false,side:THREE.FrontSide});const m=new THREE.Mesh(box,mat);m.renderOrder=10;m.raycast=()=>{};m.visible=false;root.add(m);return m}
 for(const r of rows){const ps=geometry(r),pts=ps.flatMap(p=>p.o),xs=pts.map(p=>p[0]),ys=pts.map(p=>p[1]),x=Math.min(...xs),y=Math.min(...ys),w=Math.max(...xs)-x,d=Math.max(...ys)-y;
  const canvas=document.createElement('canvas');canvas.width=canvas.height=256;const ctx=canvas.getContext('2d');ctx.fillStyle='black';ctx.fillRect(0,0,256,256);ctx.fillStyle='white';ctx.beginPath();
  for(const p of ps)for(const ring of [p.o,...p.h]){ring.forEach((v,i)=>{const px=(v[0]-x)/w*256,py=(v[1]-y)/d*256;i?ctx.lineTo(px,py):ctx.moveTo(px,py)});ctx.closePath()}ctx.fill('evenodd');
  const mask=new THREE.CanvasTexture(canvas);mask.flipY=false;mask.minFilter=mask.magFilter=THREE.NearestFilter;
  for(const lower of [false,true]){const mesh=make(mask,roots.get(r.floor));volumes.push({r,mesh,lower,x,y,w,d})}
 }
 const white=document.createElement('canvas');white.width=white.height=2;const ctx=white.getContext('2d');ctx.fillStyle='white';ctx.fillRect(0,0,2,2);
 function furniture(f,root){
  const group=new THREE.Group();group.name='fuel_inventory_'+f.id;root.add(group);
  const units=f.fuel_units||[{id:f.id,position:f.position,width_m:f.width_m||Math.sqrt(f.area||.64),depth_m:f.depth_m||Math.sqrt(f.area||.64),height_m:.75,shape:'desk'}];
  for(const unit of units){
   const cell=new THREE.Group();cell.name=unit.id;cell.position.set(...unit.position,0);cell.userData.fuelUnit=unit;group.add(cell);
   const w=unit.width_m,d=unit.depth_m,h=unit.height_m;
   function part(x,y,z,ww,dd,hh,color){const mesh=new THREE.Mesh(new THREE.BoxGeometry(ww,dd,hh),new THREE.MeshLambertMaterial({color}));mesh.position.set(x,y,z);mesh.userData.fuelColor=color;mesh.renderOrder=4;mesh.raycast=()=>{};cell.add(mesh)}
   if(unit.shape==='desk'){
    part(0,0,h-.035,w,d,.07,0xc9a46c);
    for(const x of [-1,1])for(const y of [-1,1])part(x*w*.4,y*d*.36,(h-.07)/2,.055,.055,h-.07,0x706d65);
    part(w*.25,0,h*.45,w*.24,d*.8,h*.75,0xa68b65);
   }else{
    part(0,0,h/2,w,d,h,unit.shape==='tall_cabinet'?0xa88a63:0xb69b76);
    for(let z=.4;z<h;z+=.4)part(0,-d/2-.006,z,w*.86,.012,.015,0x655b4a);
    part(0,-d/2-.015,h*.55,.035,.025,h*.3,0x655b4a);
   }
   const outline=new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(w+.08,d+.08,.012)),new THREE.LineBasicMaterial({color:0xc8b794,transparent:true,opacity:.5}));outline.position.z=.025;outline.raycast=()=>{};cell.add(outline);
  }
  return group;
 }
 const definitions=fires||[{id:'ExampleFire',floor:fire.floor,position:centre(fire),base_height:0,ignition_time:0}],flames=[];
 for(const f of definitions){const root=roots.get(f.floor),flame=make(new THREE.CanvasTexture(white),root);flame.material.uniforms.uFire.value=1;flame.renderOrder=20;
  // Keep a bounded light count; hundreds of zero-intensity lights still expand GPU shaders.
  const light=flames.length<3?new THREE.PointLight(0xff8c28,0,10,2):null;if(light)root.add(light);let fuel=null,ring=null;
  if(f.fuel_units||f.id!=='ExampleFire')fuel=furniture(f,root);
  ring=new THREE.Mesh(new THREE.RingGeometry(.62,.76,32),new THREE.MeshBasicMaterial({color:0xff9c32,transparent:true,opacity:.85,side:THREE.DoubleSide,depthWrite:false}));ring.position.set(f.position[0],f.position[1],.04);ring.raycast=()=>{};ring.visible=false;root.add(ring);
  flame.material.uniforms.uPhase.value=flames.length*2.17;
  flames.push({f,flame,light,fuel,ring,q:0});
 }
 let active=false,state=null;
 const plumeDisplay=createCfastPlumeDisplay({rows,roots,geometry,fires:definitions,volumes});
 function sizeFlame(e,now=0){
  const {f,flame}=e;
  // Native mean height and equivalent source diameter. Small flicker is visual;
  // tiny flames retain their location ring instead of camera-dependent enlargement.
  const phase=flame.material.uniforms.uPhase.value;
   const pulse=state?.realView?1+.04*Math.sin(now*.003+phase)+.02*Math.sin(now*.007+phase*2):1;
   const h=Math.min(e.maxHeight,e.physicalHeight*pulse);
  const width=Math.sqrt(4*(f.plume_inputs?.area||f.area||.64)/Math.PI);
  e.displayHeight=h;e.enlarged=h>e.physicalHeight+.001;
  flame.position.set(f.position[0]-width/2,f.position[1]-width/2,(f.base_height||0)+.06);
  flame.scale.set(width,width,Math.max(.001,h));
  flame.material.uniforms.uStyle.value=state?.realView?1:0;
 }
 function updateMesh(m,now){m.updateWorldMatrix(true,false);const u=m.material.uniforms;u.uCamera.value.copy(C.position);m.worldToLocal(u.uCamera.value);u.uSize.value.copy(m.scale);u.uTime.value=now/1000;const p=u.uCamera.value,inside=p.x>0&&p.x<1&&p.y>0&&p.y<1&&p.z>0&&p.z<1;m.material.side=inside?THREE.BackSide:THREE.FrontSide}
 return {
  setState(s){state=s;active=s.enabled;plumeDisplay.update(s);for(const v of volumes){const a=s.cached.get(v.r.key),z=v.r.core_kind?0:Math.max(0,Math.min(v.r.height,a[3])),lo=v.lower?0:z,hi=v.lower?z:v.r.height,od=Math.max(0,a[v.lower?5:4]);v.mesh.visible=active&&s.smokeEnabled&&od>.00001&&hi-lo>.01;v.mesh.position.set(v.x,v.y,lo+.01);v.mesh.scale.set(v.w,v.d,Math.max(.001,hi-lo-.01));v.mesh.material.uniforms.uOD.value=od}
   for(const e of flames){const {f,flame,light,fuel,ring}=e,j=Math.min((f.hrr?.length||1)-1,Math.floor(s.time/s.step)),u=s.time/s.step-j,interp=a=>a?THREE.MathUtils.lerp(a[j],a[Math.min(j+1,a.length-1)],u):0,ign=f.ignition_time!==null&&s.time>=f.ignition_time,q=ign?(f.hrr?interp(f.hrr):s.q):0,r=rows.find(r=>r.key===f.room_key)||fire,h=Math.max(0,Math.min(r.height-f.base_height-.1,f.flame_height?interp(f.flame_height):s.h)),c=f.position,width=Math.max(.3,Math.min(2,h*.62));e.q=q;e.physicalHeight=h;e.maxHeight=Math.max(.05,r.height-f.base_height-.1);flame.visible=active&&s.flamesEnabled&&q>.01;flame.position.set(c[0]-width/2,c[1]-width/2,f.base_height+.06);flame.scale.set(width,width,Math.max(.001,h));if(flame.visible)sizeFlame(e);if(light){light.position.set(c[0],c[1],f.base_height+Math.max(.2,h*.3));light.intensity=flame.visible?1.2*Math.min(1,q/1000):0;}ring.visible=active&&q>.01;if(fuel){fuel.visible=active;fuel.traverse(m=>{if(m.userData.fuelColor!==undefined)m.material.color.setHex(m.userData.fuelColor)})}}
  },
  animate(now){if(!active)return;plumeDisplay.animate(now);for(const v of volumes)if(v.mesh.visible&&groups[floorIndex.get(v.r.floor)].visible)updateMesh(v.mesh,now);for(const e of flames){if(e.flame.visible){sizeFlame(e,now);updateMesh(e.flame,now);}if(e.light)e.light.intensity=e.flame.visible?1.2*Math.min(1,e.q/1000)*(.9+.1*Math.sin(now*.011)):0;}},
  stats(){return {fuelUnitCount:definitions.reduce((n,f)=>n+(f.fuel_units?.length||0),0),fuelHeights:[...new Set(definitions.flatMap(f=>(f.fuel_units||[]).map(u=>u.height_m)))],plume:plumeDisplay.stats(),volumeCount:volumes.filter(v=>v.mesh.visible).length,flames:flames.filter(e=>e.flame.visible).map(e=>e.f.id),method:'polygon-masked-volume-raymarch',steps:32,visibility:'geometry < smoke < flames',flameDimensions:'native mean height and equivalent source diameter; real-view flicker ±6%',flameSizes:flames.filter(e=>e.flame.visible).map(e=>({id:e.f.id,physicalHeight:e.physicalHeight,displayHeight:e.displayHeight,enlarged:e.enlarged})),smokeRenderOrder:10,flameRenderOrder:20,depthTest:false}}
 };
}
