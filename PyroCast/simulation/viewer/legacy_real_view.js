// Restored legacy v35 renderer, bound to the current scene and CFBT playback.
import {smokeLayerVisibility} from './smoke_visual.js';
export function flameDisplayDimensions(height,diameter,mode='compact'){
 // Compact flames are location symbols for positive native HRR, not measured dimensions.
 return mode==='native'?{height,diameter}:{height:Math.max(.45,Math.min(height,1.2)),diameter:Math.max(.35,Math.min(diameter,.8))};
}
// Illustrative stages relative to this source's saved actual-HRR peak, not
// physical flame temperature or a flashover diagnosis. No extra particles.
export function flameGrowthStyle(q,peak,time,peakTime){
 const ratio=peak>0?Math.max(0,Math.min(1,q/peak)):0;
 const stage=q<=0?'꺼짐':time>peakTime&&ratio<.8?'쇠퇴기':ratio<.25?'초기':ratio<.8?'성장기':'최성기';
 const tint={'꺼짐':[1,.5,.2],'초기':[1,.48,.08],'성장기':[1,.66,.14],'최성기':[1,.94,.55],'쇠퇴기':[1,.23,.035]}[stage];
 return {stage,ratio,tint,height:.4+1.35*Math.sqrt(ratio),diameter:.3+.9*Math.sqrt(ratio)};
}
export function flameFootprint(polygons,ratio){
 const area=ring=>Math.abs(ring.reduce((sum,a,i)=>{const b=ring[(i+1)%ring.length];return sum+a[0]*b[1]-b[0]*a[1];},0))/2;
 const floorArea=Math.max(0,polygons.reduce((sum,p)=>sum+area(p.o)-(p.h||[]).reduce((n,h)=>n+area(h),0),0));
 // Display convention: up to 65% equivalent room/cell area before CAD clipping.
 // HRR controls extent; this is neither a spread-front calculation nor new fires.
 const maximum=Math.max(.6,2*Math.sqrt(.65*floorArea/Math.PI));
 return .6+(maximum-.6)*Math.sqrt(Math.max(0,Math.min(1,ratio)));
}
export function flameRoomMapping(bounds,position,width){
 return {offset:[(position[0]-bounds.x)/bounds.w,(position[1]-bounds.y)/bounds.d],scale:[width/bounds.w,width/bounds.d]};
}
export function flameBoundaryClearance(point,polygons){
 let distance=Infinity;
 for(const polygon of polygons)for(const ring of [polygon.o,...(polygon.h||[])])for(let i=0;i<ring.length;i++){
  const a=ring[i],b=ring[(i+1)%ring.length],dx=b[0]-a[0],dy=b[1]-a[1],t=Math.max(0,Math.min(1,((point[0]-a[0])*dx+(point[1]-a[1])*dy)/(dx*dx+dy*dy||1)));
  distance=Math.min(distance,Math.hypot(point[0]-a[0]-t*dx,point[1]-a[1]-t*dy));
 }
 return Math.max(0,distance-.03);
}
// CFAST-7.7.7 fire.f90: flame_height, get_plume_temp_and_velocity,
// get_ceiling_jet_temp_and_velocity. SI, Kelvin, HRR in W.
// Pure postprocessing correlations; never feeds heat back into CFAST.
const CfastPlumeMath=(()=>{
 const g=9.80665,gs=Math.sqrt(g),cp=1.012;
 function flame(q,area){return q<=0?0:Math.max(.01,-1.02*Math.sqrt(4*area/Math.PI)+.235*(q/1000)**.4)}
 function plume(p,z,r){
  const {q,chi,area,tu,tl,base,layer}=p;let temperature=z<=layer?tl:tu,velocity=0;
  if(!(q>0&&area>0&&tu>=tl&&z>=base))return {temperature,velocity};
  const qc=q*(1-chi)/1000,d=Math.sqrt(4*area/Math.PI),inf=base<=layer?tl:tu;
  let rho=352.981915/inf;
  const qs=(q/1000)/(rho*cp*inf*gs*d**2.5),z0=d*(-1.02+1.4*qs**.4),zf=Math.max(.1,d*(-1.02+3.7*qs**.4));
  let dz,excess;
  if(base<=layer&&z>layer){const zp=layer-(tu/tl)**.6*(layer-z0);rho=352.981915/tu;dz=Math.max(.1,z-base-zp);excess=Math.min(900,9.1*(tu/(g*cp**2*rho**2))**(1/3)*qc**(2/3)*dz**(-5/3));}
  else{dz=Math.max(.1,z-base-z0);excess=Math.min(900,9.1*(inf/(g*cp**2*rho**2))**(1/3)*qc**(2/3)*dz**(-5/3));}
  const umax=2.2*(g**.4/(inf**.4*(cp*rho)**.2))*(650*qc)**.2;
  velocity=Math.min(umax,3.4*(g/(cp*rho*inf))**(1/3)*qc**(1/3)*dz**(-1/3));
  const sigma=.14*Math.sqrt(1+excess/inf)*dz;
  if(r>d*(1-(z-base)/zf)/2)excess*=Math.exp(-((r/sigma)**2));
  temperature=inf+excess;
  if(r>0)velocity*=Math.exp(-((r/(1.1*sigma))**2));
  return {temperature,velocity};
 }
 function ceiling(p,z,r,xin=r,w=0){
  const {q,tu,tl,base,layer,height}=p,ambient=z<=layer?tl:tu,h=height-base;
  let temperature=ambient,velocity=0,thickness=0;
  if(!(q>0&&tu>=tl&&h>0))return {temperature,velocity,thickness};
  const inf=base<=layer?tl:tu,rho=352.981915/inf;
  thickness=h*.112*(1-Math.exp(-2.24*Math.max(.26,r/h)));
  if(z>=height-thickness){
   const top=plume(p,height,0).temperature;
   temperature=r/h<=.2?top:ambient+(top-ambient)/(.225+.27*.2)**(-4/3)*(.225+.27*r/h)**(-4/3);
   if(w>0&&xin>w/2)temperature=Math.max(temperature,ambient+(top-ambient)*.37*(h/w)**(1/3)*Math.exp(-.16*xin/h*(w/h)**(1/3)));
   const qs=(q/1000)/(rho*cp*inf*gs*h**2.5);
   velocity=r/h<=.17?gs*Math.sqrt(h)*qs**(1/3)*3.61:gs*Math.sqrt(h)*qs**(1/3)*1.06*(r/h)**(-.69);
   if(w>0&&xin>w/2)velocity=Math.max(velocity,.114*Math.sqrt(Math.max(0,h*(temperature-ambient)))*(h/w)**(1/6));
  }
  return {temperature,velocity,thickness};
 }
 return {flame,plume,ceiling};
})();
if(typeof module!=='undefined')module.exports=CfastPlumeMath;
export function flameHrrDimensions(q,hrrpua,cellArea,maxHeight){
 const area=Math.min(Math.max(0,cellArea),Math.max(0,q)/(hrrpua>0?hrrpua:500));
 return {area,diameter:2*Math.sqrt(area/Math.PI),height:Math.min(maxHeight,Math.max(.1,CfastPlumeMath.flame(q*1000,area)))};
}
export function flameIdPhase(id){let h=2166136261;for(const c of String(id)){h^=c.codePointAt(0);h=Math.imul(h,16777619);}return (h>>>0)/4294967296*6.2831853;}

// Display-only area query, built once from the same CAD mask used by the shader.
export function flameMaskAreaProfile(bounds,origin,image,step=2){
 const radii=[];for(let y=0;y<image.height;y+=step)for(let x=0;x<image.width;x+=step){
  if(image.data[(y*image.width+x)*4]<=254)continue;
  radii.push(Math.hypot(bounds.x+(x+.5)*bounds.w/image.width-origin[0],bounds.y+(y+.5)*bounds.d/image.height-origin[1]));
 }
 radii.sort((a,b)=>a-b);
 const pixelArea=bounds.w*bounds.d*step*step/(image.width*image.height),maxRadius=Math.max(0,...bounds.ps.flatMap(p=>p.o.map(v=>Math.hypot(v[0]-origin[0],v[1]-origin[1]))));
 return {radii,pixelArea,maxRadius,availableArea:radii.length*pixelArea};
}
export function flameMaskedFootprint(profile,requestedArea,cellArea){
 const target=Math.min(Math.max(0,requestedArea),cellArea,profile.availableArea);
 const areaAt=r=>{let lo=0,hi=profile.radii.length;while(lo<hi){const m=(lo+hi)>>>1;if(profile.radii[m]<=r)lo=m+1;else hi=m;}return lo*profile.pixelArea;};
 if(!(target>0))return {diameter:0,targetArea:target,insideArea:0,iterations:0,fullCell:false};
 if(requestedArea>=cellArea||target>=profile.availableArea)return {diameter:2*(profile.maxRadius+.3),targetArea:target,insideArea:profile.availableArea,iterations:0,fullCell:true};
 let lo=Math.sqrt(target/Math.PI),hi=Math.min(profile.maxRadius,lo*2);
 while(areaAt(hi)<target&&hi<profile.maxRadius)hi=Math.min(profile.maxRadius,hi*2);
 for(let i=0;i<4;i++){const mid=(lo+hi)/2;if(areaAt(mid)<target)lo=mid;else hi=mid;}
 const a=areaAt(lo),b=areaAt(hi),radius=b>a?lo+(hi-lo)*Math.max(0,Math.min(1,(target-a)/(b-a))):hi;
 return {diameter:2*radius,targetArea:target,insideArea:areaAt(radius),iterations:4,fullCell:false};
}

export function createLegacyRealistic(viewer, configuration){
 const {THREE,C,groups}=viewer;

// Correlation-derived diagnostic gas volumes, separate from visible flame and soot.
function createCfastPlumeDisplay({rows,roots,geometry,fires,volumes}){
 const objects=[],N=96;
 const box=new THREE.BoxGeometry(1,1,1);box.translate(.5,.5,.5);
 const vertex='varying vec3 vLocal;void main(){vLocal=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}';
 const fragment=`precision highp float;varying vec3 vLocal;
 uniform sampler2D uProfile,uMask;uniform vec3 uCamera,uSize,uOrigin,uFire;
 uniform float uRadius,uHeight,uBase,uFlame,uDiameter,uTime;
 vec4 profile(vec2 uv){vec2 p=clamp(uv,0.,1.)*95.,i=floor(p),f=fract(p);vec2 a=(i+.5)/96.,b=(min(i+1.,95.)+.5)/96.;return mix(mix(texture2D(uProfile,a),texture2D(uProfile,vec2(b.x,a.y)),f.x),mix(texture2D(uProfile,vec2(a.x,b.y)),texture2D(uProfile,b),f.x),f.y);}
 void main(){vec3 ray=normalize(vLocal-uCamera),safeRay=vec3(ray.x<0.?-max(-ray.x,.00001):max(ray.x,.00001),ray.y<0.?-max(-ray.y,.00001):max(ray.y,.00001),ray.z<0.?-max(-ray.z,.00001):max(ray.z,.00001));
 vec3 ta=(vec3(0.)-uCamera)/safeRay,tb=(vec3(1.)-uCamera)/safeRay,mn=min(ta,tb),mx=max(ta,tb);
 float start=max(0.,max(mn.x,max(mn.y,mn.z))),end=min(mx.x,min(mx.y,mx.z));if(end<=start)discard;
 float ds=(end-start)/48.,stepM=length(ray*uSize)*ds;vec4 sum=vec4(0.);
 for(int i=0;i<48;i++){vec3 p=uCamera+ray*(start+(float(i)+.5)*ds),world=uOrigin+p*uSize;
 if(texture2D(uMask,p.xy).r<.5||world.z<uBase)continue;
 float r=length(world.xy-uFire.xy);vec4 v=profile(vec2(r/uRadius,world.z/uHeight));
 // Values are temperature excess over the local zone, not soot concentration.
 float pv=max(0.,v.r),cv=max(0.,v.b);
 float cone=max(0.,uDiameter*.5*(1.-(world.z-uBase)/max(.01,uFlame)));
 if(world.z<uBase+uFlame&&r<cone)pv=0.;
 float strength=clamp(log(1.+max(pv,cv)/15.)/3.,0.,1.);
 float flow=cv>pv?r:world.z-uBase,vel=cv>pv?v.a:v.g;
 float pattern=.90+.10*sin(flow*7.-uTime*min(vel,8.)*2.);
 float a=(1.-exp(-strength*stepM*.65))*pattern;
 vec3 color=cv>pv?vec3(.20,.83,.91):vec3(.70,.48,.90);
 sum.rgb+=(1.-sum.a)*color*a;sum.a+=(1.-sum.a)*a;
 }if(sum.a<.005)discard;gl_FragColor=vec4(sum.rgb/max(.001,sum.a),min(.65,sum.a));}`;
 for(const f of fires){const r=rows.find(r=>r.key===f.room_key),input=f.plume_inputs;
  // No guessed physics inputs: an older result keeps its existing flame/smoke only.
  if(!r||!input||input.hall)continue;
  const v=volumes.find(v=>v.r.key===r.key&&!v.lower);if(!v)continue;
  const pixels=new Float32Array(N*N*4),texture=new THREE.DataTexture(pixels,N,N,THREE.RGBAFormat,THREE.FloatType);texture.minFilter=texture.magFilter=THREE.NearestFilter;
  const radius=Math.max(...[[v.x,v.y],[v.x+v.w,v.y],[v.x,v.y+v.d],[v.x+v.w,v.y+v.d]].map(p=>Math.hypot(p[0]-f.position[0],p[1]-f.position[1])));
  const uniforms={uProfile:{value:texture},uMask:{value:v.mesh.material.uniforms.uMask.value},uCamera:{value:new THREE.Vector3()},uSize:{value:new THREE.Vector3(v.w,v.d,r.height)},uOrigin:{value:new THREE.Vector3(v.x,v.y,0)},uFire:{value:new THREE.Vector3(...f.position,0)},uRadius:{value:radius},uHeight:{value:r.height},uBase:{value:input.base},uFlame:{value:0},uDiameter:{value:Math.sqrt(4*input.area/Math.PI)},uTime:{value:0}};
  const mesh=new THREE.Mesh(box,new THREE.ShaderMaterial({uniforms,vertexShader:vertex,fragmentShader:fragment,transparent:true,depthWrite:false,depthTest:false,side:THREE.FrontSide}));mesh.position.set(v.x,v.y,0);mesh.scale.set(v.w,v.d,r.height);mesh.renderOrder=15;mesh.raycast=()=>{};mesh.visible=false;roots.get(r.floor).add(mesh);
  objects.push({f,r,input,mesh,pixels,texture,radius,frame:-1,summary:null});
 }
 const legend=document.createElement('div');legend.id='cfPlumeLegend';legend.style.cssText='line-height:1.7;padding:7px 0';
 legend.innerHTML='<span style="color:#ffb34d">■ 화염</span> · <span style="color:#b38ae6">■ 상승 플룸</span><br><span style="color:#33d4e8">■ 천장 아래 고온 가스</span><br><small>가스 색은 구분용이며 불꽃이 아닙니다. 공식 상관식의 온도·속도를 표시하며, 흐르는 무늬는 시각 효과입니다.</small><div id="cfPlumeNumbers"></div>';
 document.getElementById('cfMeaning').after(legend);
 let summaries=[];
 return {
  update(s){summaries=[];legend.hidden=!s.realView||!s.enabled;
   for(const e of objects){const i=Math.min(e.f.hrr.length-1,Math.floor(s.time/s.step)),q=e.f.hrr[i];
    e.mesh.visible=s.enabled&&s.realView&&e.f.ignition_time!==null&&s.time>=e.f.ignition_time&&q>(s.positiveHrrOnly?0:1.0);
    if(!e.mesh.visible)continue;
    if(e.frame!==i){e.frame=i;const zone=e.r.series[i],factor=e.input.corner_factor,p={...e.input,q:q*1000*factor,area:e.input.area*factor,tu:zone[1]+273.15,tl:zone[2]+273.15,layer:zone[3]};
     const fh=CfastPlumeMath.flame(q*1000,e.input.area);e.mesh.material.uniforms.uFlame.value=fh;e.mesh.material.uniforms.uDiameter.value=Math.sqrt(4*e.input.area/Math.PI);
     for(let z=0;z<N;z++)for(let x=0;x<N;x++){const zz=z/(N-1)*e.r.height,rr=x/(N-1)*e.radius,ambient=zz<=p.layer?p.tl:p.tu,a=CfastPlumeMath.plume(p,zz,rr),b=CfastPlumeMath.ceiling(p,zz,rr);e.pixels.set([Math.max(0,a.temperature-ambient),a.velocity,Math.max(0,b.temperature-ambient),b.velocity],(z*N+x)*4)}
     e.texture.needsUpdate=true;const top=CfastPlumeMath.plume(p,p.height,0),cj=CfastPlumeMath.ceiling(p,p.height,Math.min(1,e.radius));
     e.summary={id:e.f.id,room:e.r.key,flameHeight:fh,diameter:Math.sqrt(4*e.input.area/Math.PI),ceilingAxisC:top.temperature-273.15,upSpeed:top.velocity,ceilingThicknessAt1m:cj.thickness,ceilingSpeedAt1m:cj.velocity,cornerFactor:factor};
    }summaries.push(e.summary);
   }
   document.getElementById('cfPlumeNumbers').textContent=summaries.length?`상관식 화염 높이 ${Math.min(...summaries.map(x=>x.flameHeight)).toFixed(2)}–${Math.max(...summaries.map(x=>x.flameHeight)).toFixed(2)}m · 천장 도달 중심 최고 ${Math.max(...summaries.map(x=>x.ceilingAxisC)).toFixed(0)}°C`:'연소 중인 계산 화원 없음';
  },
  animate(now){for(const e of objects)if(e.mesh.visible){const m=e.mesh,u=m.material.uniforms;m.updateWorldMatrix(true,false);u.uCamera.value.copy(C.position);m.worldToLocal(u.uCamera.value);u.uTime.value=now/1000;const c=u.uCamera.value;m.material.side=c.x>0&&c.x<1&&c.y>0&&c.y<1&&c.z>0&&c.z<1?THREE.BackSide:THREE.FrontSide;}},
  stats(){return {method:'CFAST-7.7.7-correlations-postprocess',gasVolumes:objects.filter(e=>e.mesh.visible).length,flameAndGasSeparate:true,samples:summaries,profileResolution:96,raySteps:48}}
 };
}

// Procedural volume rendering. The two-zone heights and extinction come from CFAST;
// the small-scale billows and flame flicker are illustrative, not a CFD velocity field.
function createCfastRealistic({rows,roots,geometry,fire,centre,floorIndex,fires}){
 const volumes=[],roomMasks=new Map(),box=new THREE.BoxGeometry(1,1,1);box.translate(.5,.5,.5);
 const noise=`
 float hash(vec3 p){p=fract(p*.3183099+vec3(.11,.23,.37));p*=17.;return fract(p.x*p.y*p.z*(p.x+p.y+p.z));}
 float noise3(vec3 p){vec3 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);
 return mix(mix(mix(hash(i),hash(i+vec3(1,0,0)),f.x),mix(hash(i+vec3(0,1,0)),hash(i+vec3(1,1,0)),f.x),f.y),mix(mix(hash(i+vec3(0,0,1)),hash(i+vec3(1,0,1)),f.x),mix(hash(i+vec3(0,1,1)),hash(i+vec3(1,1,1)),f.x),f.y),f.z);}
 float billow(vec3 p){return .68*noise3(p)+.32*noise3(p*2.07+7.);}
 `;
 const vertex=`varying vec3 vLocal;void main(){vLocal=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`;
 const fragment=`precision highp float;
 varying vec3 vLocal;uniform vec3 uCamera,uSize;uniform sampler2D uMask;uniform vec2 uMaskOffset,uMaskScale;uniform float uJitterSeed;
 uniform float uTime,uOD,uFire,uGas,uPower,uStyle,uPhase,uOpacity,uFlameGain,uRiskMix,uGrowth,uDarkSmoke,uCluster,uTemperatureSmoke,uLayerTemp,uNoiseAmp,uNoiseScale,uRampMode;uniform vec3 uRiskColor,uStageColor;${noise}
 void main(){
 vec3 ray=normalize(vLocal-uCamera),safeRay=vec3(ray.x<0.?-max(-ray.x,.00001):max(ray.x,.00001),ray.y<0.?-max(-ray.y,.00001):max(ray.y,.00001),ray.z<0.?-max(-ray.z,.00001):max(ray.z,.00001));
 vec3 ta=(vec3(0.)-uCamera)/safeRay,tb=(vec3(1.)-uCamera)/safeRay;
 vec3 mn=min(ta,tb),mx=max(ta,tb);float start=max(0.,max(mn.x,max(mn.y,mn.z))),end=min(mx.x,min(mx.y,mx.z));
 if(end<=start)discard;float ds=(end-start)/32.,worldStep=length(ray*uSize)*ds;
 vec4 sum=vec4(0.);float jitter=fract(gl_FragCoord.x*.06711056+gl_FragCoord.y*.00583715);
 for(int i=0;i<32;i++){
 vec3 p=uCamera+ray*(start+(float(i)+jitter)*ds);vec2 maskUV=uMaskOffset+p.xy*uMaskScale;float mask=0.;
 if(all(greaterThanEqual(maskUV,vec2(0.)))&&all(lessThanEqual(maskUV,vec2(1.))))mask=texture2D(uMask,maskUV).r;
 if(mask>(uFire>.5?.999:.5)){
 if(uGas>.5){
 // Illustrative upper-layer flame ribbons, clipped by the same CAD polygon mask.
 // Native bulk HRR gates the effect; this texture supplies no physical flame front.
 vec3 wp=p*uSize;
 float n=billow(vec3(wp.xy*.95,wp.z*1.6-uTime*1.15));
 float ribbon=sin(wp.x*1.8+sin(wp.y*2.1+uTime*1.6)+uTime*2.2);
 float d=smoothstep(.47,.83,n+.15*ribbon)*smoothstep(0.,.2,p.z)*(.45+.55*p.z)*uPower;
 float a=1.-exp(-d*worldStep*2.1);
 vec3 col=mix(vec3(1.,.12,.015),vec3(1.,.84,.28),smoothstep(.1,.7,d));
 sum.rgb+=(1.-sum.a)*col*a;sum.a+=(1.-sum.a)*a;
 }else if(uFire>.5){
 // Three variations of the original compact flame; no detached ribbons.
 float variant=mod(floor(uPhase/2.17+.1),mix(3.,5.,uGrowth));
 float speed=mix(2.8,2.3+variant*.55,uStyle);
 float z=p.z;vec2 noiseXY=mix(p.xy*(5.+uStyle*variant*.6),(p.xy-.5)*uSize.xy*2.8,clamp(uCluster,0.,1.));
 vec3 npos=vec3(noiseXY,z*5.-uTime*speed+uPhase);float n=billow(npos);
 vec2 drift=vec2(sin(z*8.-uTime*(2.+variant*.15)+uPhase),cos(z*9.-uTime*2.3+uPhase))*.07*z;
 float radius=length((p.xy-.5+drift)*2.);float width=pow(max(.001,1.-z),1.+uStyle*(variant-1.)*.06);
 float body=1.-radius/max(.01,width)+(n-.5)*(1.1+uStyle*variant*.12);
 if(uCluster>.5){
  // An expanding field reveals spatially anchored tongues, with no fixed count.
  // One noise sample and one volume draw remain; CAD clipping is applied above.
  vec2 local=(p.xy-.5)*uSize.xy;
  float spacing=min(1.35,max(.45,uSize.x*.7));
  vec2 tile=floor(local/spacing+.5),within=local-tile*spacing;
  float seed=hash(vec3(tile,uPhase));
  vec2 jitter=vec2(sin(seed*37.),cos(seed*53.))*spacing*.10;
   if(uCluster>1.5){float jitterSeed=hash(vec3(tile,uJitterSeed));jitter=vec2(sin(jitterSeed*37.),cos(jitterSeed*53.))*spacing*.4;}
  float zz=z/(.65+.35*seed),ww=pow(max(.001,1.-zz),1.05);
  vec2 sway=vec2(sin(uTime*(2.+seed)+seed*9.),cos(uTime*2.3+seed*7.))*.08*z;
  float rr=length(within-jitter+sway)/(spacing*.42);
  float envelope=1.-smoothstep(.72,1.,length((p.xy-.5)*2.));
   if(uCluster>1.5)envelope=1.-smoothstep(max(0.,uSize.x*.5-.3),uSize.x*.5,length(local));
  body=zz<1.?(1.-rr/max(.01,ww)+(n-.5)*1.2)*envelope:-1.;
  if(envelope<=0.)body=-1.;
 }
 float d=max(0.,body)*smoothstep(0.,.04,z)*(1.-smoothstep(.91,1.,z));
 float a=(1.-exp(-d*worldStep*5.));vec3 col=mix(vec3(1.,.12,.012),vec3(1.,.83,.22),clamp(d*1.6-z*.3,0.,1.));
 col=mix(col,vec3(1.,.97,.76),smoothstep(.85,1.35,d)*(1.-z));
 col=mix(col,mix(uStageColor*.55,uStageColor,clamp(d*1.4,0.,1.)),uGrowth*.8);sum.rgb+=(1.-sum.a)*col*a;sum.a+=(1.-sum.a)*a;
 }else{
 vec3 wp=p*uSize,drift=wp*.65+vec3(uTime*.09,-uTime*.06,-uTime*.035);
 float coarse=noise3(drift),fine=noise3(drift*2.07+7.);
 float n=.68*coarse+.32*fine;
 float edge=smoothstep(0.,mix(.08,.025,uDarkSmoke),p.z)*smoothstep(0.,.025,1.-p.z);
 float d=uOD*2.302585*mix(.25,1.75,smoothstep(.12,.88,n))*edge;
 float a=1.-exp(-d*worldStep);vec3 col=mix(vec3(.13,.15,.17),vec3(.48,.50,.51),n*.65+p.z*.25);
 vec3 dark=mix(vec3(.012,.015,.019),vec3(.19,.20,.21),smoothstep(.25,.72,n)*.85+p.z*.1);
 col=mix(col,dark,uDarkSmoke);
 if(uTemperatureSmoke>.5){
  // Reuse both billow octaves for scattered temperature highlights.
  // These are display texture, not resolved local temperature or flow paths.
  float bands=.55*smoothstep(.22,.46,n)+.45*smoothstep(.53,.72,n);
  vec3 neutral=mix(vec3(.10,.11,.125),vec3(.30,.32,.34),bands);
  float warmth=smoothstep(80.,200.,uLayerTemp);
  vec3 heat=mix(vec3(1.,.80,.22),vec3(.96,.19,.07),clamp((uLayerTemp-200.)/400.,0.,1.));
  float patternFine=fine,patternN=n;
  if(uNoiseScale!=1.){
   vec3 patternDrift=drift*uNoiseScale;
   patternFine=noise3(patternDrift*2.07+7.);
   patternN=.68*noise3(patternDrift)+.32*patternFine;
  }
  float highlight=smoothstep(.52,.78,patternFine)*smoothstep(.18,.48,patternN);
  // Keep the default expression exactly; amplitude affects RGB highlights only.
  if(uNoiseAmp==1.)col=mix(neutral,heat,highlight*.40*warmth);
  else col=mix(neutral,heat,highlight*.40*warmth*uNoiseAmp);
 }
 if(uRampMode>.5){
  // Display-only grayscale ramp: 20 C light gray -> 600 C near black.
  float gray=mix(.70,.035,clamp((uLayerTemp-20.)/580.,0.,1.));
  float variation=mix(1.,mix(.75,1.,n),uTemperatureSmoke*uNoiseAmp);
  col=vec3(gray*variation);
 }
 sum.rgb+=(1.-sum.a)*col*a;sum.a+=(1.-sum.a)*a;
 }
 }if(sum.a>.985)break;
 }if(sum.a<.003)discard;
 // Optional temperature highlights change only RGB. Risk condition colours
 // remain on the separate room outline; temperature does not imply ignition.
 gl_FragColor=vec4(sum.rgb/max(sum.a,.001),sum.a*(uFire>.5||uGas>.5?1.:uOpacity));
 if((uFire>.5||uGas>.5)&&uFlameGain!=1.)gl_FragColor.rgb*=uFlameGain;
 }`;
 // Diagnostic overlay: smoke is drawn over geometry, then flames over all smoke.
 // This changes visibility only, not extinction, temperature, HRR or ignition.
 function make(mask,root){const mat=new THREE.ShaderMaterial({uniforms:{uCamera:{value:new THREE.Vector3()},uSize:{value:new THREE.Vector3()},uMask:{value:mask},uMaskOffset:{value:new THREE.Vector2(0,0)},uMaskScale:{value:new THREE.Vector2(1,1)},uTime:{value:0},uOD:{value:0},uFire:{value:0},uGas:{value:0},uPower:{value:0},uStyle:{value:0},uPhase:{value:0},uOpacity:{value:1},uFlameGain:{value:1},uRiskMix:{value:0},uDarkSmoke:{value:0},uTemperatureSmoke:{value:0},uLayerTemp:{value:20},uNoiseAmp:{value:1},uNoiseScale:{value:1},uRampMode:{value:0},uRiskColor:{value:new THREE.Color('#b16cff')}},vertexShader:vertex,fragmentShader:fragment,transparent:true,depthWrite:false,depthTest:false,side:THREE.FrontSide});const m=new THREE.Mesh(box,mat);m.renderOrder=10;m.raycast=()=>{};m.visible=false;root.add(m);return m}
 for(const r of rows){const ps=geometry(r),pts=ps.flatMap(p=>p.o),xs=pts.map(p=>p[0]),ys=pts.map(p=>p[1]),x=Math.min(...xs),y=Math.min(...ys),w=Math.max(...xs)-x,d=Math.max(...ys)-y;
  const canvas=document.createElement('canvas');canvas.width=canvas.height=256;const ctx=canvas.getContext('2d');ctx.fillStyle='black';ctx.fillRect(0,0,256,256);ctx.fillStyle='white';ctx.beginPath();
  for(const p of ps)for(const ring of [p.o,...p.h]){ring.forEach((v,i)=>{const px=(v[0]-x)/w*256,py=(v[1]-y)/d*256;i?ctx.lineTo(px,py):ctx.moveTo(px,py)});ctx.closePath()}ctx.fill('evenodd');
  const mask=new THREE.CanvasTexture(canvas);mask.flipY=false;mask.minFilter=mask.magFilter=THREE.NearestFilter;
  roomMasks.set(r.key,{x,y,w,d,ps,canvas,flameMask:null});
  for(const lower of [false,true]){const mesh=make(mask,roots.get(r.floor));let boundary=null;
   if(!lower){const points=[];for(const p of ps)for(const ring of [p.o,...p.h])for(let i=0;i<ring.length;i++){const a=ring[i],b=ring[(i+1)%ring.length];for(const z of [0,1])points.push(a[0],a[1],z,b[0],b[1],z);}
    const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(points,3));
    boundary=new THREE.LineSegments(geo,new THREE.LineBasicMaterial({color:'#b16cff',transparent:true,opacity:.72,depthTest:false,depthWrite:false}));boundary.visible=false;boundary.renderOrder=23;boundary.raycast=()=>{};roots.get(r.floor).add(boundary);}
   volumes.push({r,mesh,boundary,lower,x,y,w,d});}

 }
 const gasFlames=volumes.filter(v=>!v.lower).map(v=>{const mesh=make(v.mesh.material.uniforms.uMask.value,roots.get(v.r.floor));mesh.material.uniforms.uGas.value=1;mesh.renderOrder=22;return {v,mesh,q:0};});
 function flameMask(bounds){
  if(bounds.flameMask)return bounds.flameMask;
  const canvas=document.createElement('canvas');canvas.width=canvas.height=512;const ctx=canvas.getContext('2d');
  ctx.imageSmoothingEnabled=false;ctx.drawImage(bounds.canvas,0,0,512,512);
  // Remove the raster boundary band conservatively, including holes and concave corners.
  ctx.strokeStyle='black';ctx.lineWidth=4;ctx.lineJoin='round';ctx.beginPath();
  for(const p of bounds.ps)for(const ring of [p.o,...(p.h||[])]){ring.forEach((v,i)=>{const x=(v[0]-bounds.x)/bounds.w*512,y=(v[1]-bounds.y)/bounds.d*512;i?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.closePath();}ctx.stroke();
  const mask=new THREE.CanvasTexture(canvas);mask.flipY=false;mask.minFilter=mask.magFilter=THREE.NearestFilter;bounds.flameMask=mask;return mask;
 }
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
 for(const f of definitions){const root=roots.get(f.floor),bounds=roomMasks.get(f.room_key)||roomMasks.get(fire?.key);if(!bounds)continue;const flame=make(flameMask(bounds),root);flame.material.uniforms.uFire.value=1;flame.renderOrder=20;flame.userData.fireId=f.id;flame.userData.hrrpua=f.hrrpua_kW_m2;flame.userData.cellArea=f.cell_area_m2;
  // Keep a bounded light count; hundreds of zero-intensity lights still expand GPU shaders.
  const light=flames.length<3?new THREE.PointLight(0xff8c28,0,10,2):null;if(light)root.add(light);let fuel=null,ring=null;
  if(f.fuel_units||f.id!=='ExampleFire')fuel=furniture(f,root);
  ring=new THREE.Mesh(new THREE.RingGeometry(.62,.76,32),new THREE.MeshBasicMaterial({color:0xff9c32,transparent:true,opacity:.85,side:THREE.DoubleSide,depthWrite:false}));ring.position.set(f.position[0],f.position[1],(f.base_height||0)+.025);ring.raycast=()=>{};ring.visible=false;root.add(ring);
  ring.scale.setScalar(Math.min(1,flameBoundaryClearance(f.position,bounds.ps)/.76));
  flame.material.uniforms.uPhase.value=flames.length*2.17;
  flame.material.uniforms.uGrowth={value:0};flame.material.uniforms.uCluster={value:0};flame.material.uniforms.uStageColor={value:new THREE.Color(1,.66,.14)};flame.material.uniforms.uJitterSeed={value:flameIdPhase(f.id)};
  const peak=Math.max(0,...(f.hrr||[])),peakIndex=(f.hrr||[]).indexOf(peak);
  flames.push({f,flame,light,fuel,ring,bounds,q:0,peak,peakIndex,legacyPhase:flames.length*2.17,idPhase:flameIdPhase(f.id),maximumFootprint:flameFootprint(bounds.ps,1)});
 }
 let active=false,state=null;
 const plumeDisplay=createCfastPlumeDisplay({rows,roots,geometry,fires:definitions,volumes});
 function sizeFlame(e,now=0){
  const {f,flame}=e;
  // Native mean height and equivalent source diameter. Small flicker is visual;
  // tiny flames retain their location ring instead of camera-dependent enlargement.
  const hrr=state?.flameDisplay==='hrr';
   const phase=e.legacyPhase;flame.material.uniforms.uPhase.value=phase;
   const pulse=state?.realView?1+.04*Math.sin(now*.003+phase)+.02*Math.sin(now*.007+phase*2):1;
   const growth=state?.flameDisplay==='growth',style=flameGrowthStyle(e.q,e.peak,state?.time||0,e.peakIndex*(state?.step||1));
   const dimensions=hrr?flameHrrDimensions(e.q,f.hrrpua_kW_m2,f.cell_area_m2,e.maxHeight):growth?{height:style.height*pulse,diameter:style.diameter}:flameDisplayDimensions(Math.min(e.maxHeight,e.physicalHeight*pulse),Math.sqrt(4*(f.plume_inputs?.area||f.area||.64)/Math.PI),state?.flameDisplay);
   if(hrr){
    if(!e.maskProfile){const canvas=flame.material.uniforms.uMask.value.image;e.maskProfile=flameMaskAreaProfile(e.bounds,f.position,canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height));}
    if(e.maskArea!==dimensions.area){e.maskArea=dimensions.area;e.maskFootprint=flameMaskedFootprint(e.maskProfile,dimensions.area,f.cell_area_m2);}
    flame.userData.maskFootprint=e.maskFootprint;dimensions.diameter=e.maskFootprint.diameter;
   }
   flame.material.uniforms.uGrowth.value=growth||hrr?1:0;flame.material.uniforms.uCluster.value=hrr?2:growth?1:0;flame.material.uniforms.uStageColor.value.setRGB(...style.tint);e.stage=growth||hrr?style.stage:null;
   const h=Math.min(e.maxHeight,Math.max(hrr?.1:0,dimensions.height*(hrr?pulse:1))),width=growth ? .6+(e.maximumFootprint-.6)*Math.sqrt(style.ratio) : dimensions.diameter;
  flame.userData.q=e.q;flame.userData.stage=e.stage;
  e.displayHeight=h;e.enlarged=h>e.physicalHeight+.001;
  flame.position.set(f.position[0]-width/2,f.position[1]-width/2,(f.base_height||0));
  flame.scale.set(width,width,Math.max(.001,h));
  const mapping=flameRoomMapping(e.bounds,[flame.position.x,flame.position.y],width);
  flame.material.uniforms.uMaskOffset.value.set(...mapping.offset);flame.material.uniforms.uMaskScale.value.set(...mapping.scale);
  flame.material.uniforms.uStyle.value=state?.realView?1:0;
 }
 function updateMesh(m,now){m.updateWorldMatrix(true,false);const u=m.material.uniforms;u.uCamera.value.copy(C.position);m.worldToLocal(u.uCamera.value);u.uSize.value.copy(m.scale);u.uTime.value=now/1000;const p=u.uCamera.value,inside=p.x>0&&p.x<1&&p.y>0&&p.y<1&&p.z>0&&p.z<1;m.material.side=inside?THREE.BackSide:THREE.FrontSide}
 return {
  setState(s){state=s;active=s.enabled;plumeDisplay.update({...s,enabled:s.enabled&&s.plumesEnabled!==false});for(const v of volumes){const a=s.cached.get(v.r.key),z=v.r.core_kind?0:Math.max(0,Math.min(v.r.height,a[3])),lo=v.lower?0:z,hi=v.lower?z:v.r.height,od=Math.max(0,a[v.lower?5:4]),risk=!v.lower&&s.riskColors?.get(v.r.key),visibility=smokeLayerVisibility({enabled:active,smokeEnabled:s.smokeEnabled,opticalDensity:od,thickness:hi-lo,riskColor:risk});v.mesh.visible=visibility.visible;v.mesh.position.set(v.x,v.y,lo+.01);v.mesh.scale.set(v.w,v.d,Math.max(.001,hi-lo-.01));v.mesh.material.uniforms.uOD.value=od;v.mesh.material.uniforms.uDarkSmoke.value=s.darkSmoke?1:0;v.mesh.material.uniforms.uTemperatureSmoke.value=s.temperatureSmoke?1:0;v.mesh.material.uniforms.uLayerTemp.value=a[v.lower?2:1];v.mesh.material.uniforms.uNoiseAmp.value=s.noiseAmp??1;v.mesh.material.uniforms.uNoiseScale.value=s.noiseScale??1;v.mesh.material.uniforms.uRampMode.value=s.rampMode??0;v.mesh.material.uniforms.uOpacity.value=(s.smokeOpacity??1)*(s.smokeGain??1);v.mesh.material.uniforms.uRiskMix.value=0;if(risk)v.mesh.material.uniforms.uRiskColor.value.set(risk);if(v.boundary){v.boundary.visible=visibility.outlineVisible;v.boundary.position.z=lo+.01;v.boundary.scale.z=Math.max(.001,hi-lo-.01);if(risk)v.boundary.material.color.set(risk)}}
   for(const e of gasFlames){const {v,mesh}=e,a=s.cached.get(v.r.key),g=s.gasStates?.get(v.r.key);const z=v.r.core_kind?0:Math.max(0,Math.min(v.r.height,a[3]));e.q=g?.q||0;mesh.material.uniforms.uFlameGain.value=s.flameGain??1;mesh.visible=active&&s.gasFlamesEnabled===true&&!!g?.active&&v.r.height-z>.01;mesh.position.set(v.x,v.y,z+.01);mesh.scale.set(v.w,v.d,Math.max(.001,v.r.height-z-.01));mesh.material.uniforms.uPower.value=g?.intensity||0;}
   for(const e of flames){const {f,flame,light,fuel,ring}=e,j=Math.min((f.hrr?.length||1)-1,Math.floor(s.time/s.step)),u=s.time/s.step-j,interp=a=>a?THREE.MathUtils.lerp(a[j],a[Math.min(j+1,a.length-1)],u):0,ign=f.ignition_time!==null&&s.time>=f.ignition_time,q=ign?(f.hrr?interp(f.hrr):s.q):0,r=rows.find(r=>r.key===f.room_key)||fire,h=Math.max(0,Math.min(r.height-f.base_height-.1,f.flame_height?interp(f.flame_height):s.h)),c=f.position,width=Math.max(.3,Math.min(2,h*.62));e.q=q;flame.material.uniforms.uFlameGain.value=s.flameGain??1;e.physicalHeight=h;e.maxHeight=Math.max(.05,r.height-f.base_height-.1);flame.visible=active&&s.flamesEnabled&&q>(s.positiveHrrOnly?0:1.0);flame.position.set(c[0]-width/2,c[1]-width/2,f.base_height);flame.scale.set(width,width,Math.max(.001,h));if(flame.visible)sizeFlame(e);if(light){light.position.set(c[0],c[1],f.base_height+Math.max(.2,h*.3));light.intensity=flame.visible?1.2*Math.min(1,q/1000):0;}ring.visible=active&&q>(s.positiveHrrOnly?0:1.0);if(fuel){fuel.visible=active;fuel.traverse(m=>{if(m.userData.fuelColor!==undefined)m.material.color.setHex(m.userData.fuelColor)})}}
  },
  animate(now){if(!active)return;plumeDisplay.animate(now);for(const e of gasFlames)if(e.mesh.visible&&groups[floorIndex.get(e.v.r.floor)].visible)updateMesh(e.mesh,now);for(const v of volumes)if(v.mesh.visible&&groups[floorIndex.get(v.r.floor)].visible)updateMesh(v.mesh,now);for(const e of flames){if(e.flame.visible){sizeFlame(e,now);updateMesh(e.flame,now);}if(e.light)e.light.intensity=e.flame.visible?1.2*Math.min(1,e.q/1000)*(.9+.1*Math.sin(now*.011)):0;}if(state?.flameDisplay==='hrr'){const lights=flames.map(e=>e.light).filter(Boolean),top=flames.filter(e=>e.flame.visible&&e.q>0).sort((a,b)=>b.q-a.q||String(a.f.id).localeCompare(String(b.f.id))).slice(0,3);lights.forEach((light,i)=>{const e=top[i];light.userData.fireId=e?.f.id??null;light.intensity=e?1.2*Math.min(1,e.q/1000)*(.9+.1*Math.sin(now*.011)):0;if(e){roots.get(e.f.floor).add(light);light.position.set(e.f.position[0],e.f.position[1],(e.f.base_height||0)+Math.max(.2,e.physicalHeight*.3));}});}else{for(const e of flames)if(e.light&&e.light.parent!==roots.get(e.f.floor))roots.get(e.f.floor).add(e.light);}},
  stats(){return {gasFlames:gasFlames.filter(e=>e.mesh.visible).map(e=>({room:e.v.r.key,q_kW:e.q,displayOnly:true})),smokeColor:'original_gray_with_risk_layer_boundary',fuelUnitCount:definitions.reduce((n,f)=>n+(f.fuel_units?.length||0),0),fuelHeights:[...new Set(definitions.flatMap(f=>(f.fuel_units||[]).map(u=>u.height_m)))],plume:plumeDisplay.stats(),volumeCount:volumes.filter(v=>v.mesh.visible).length,flames:flames.filter(e=>e.flame.visible).map(e=>e.f.id),method:'polygon-masked-volume-raymarch',steps:32,visibility:'geometry < smoke < flames',flameDimensions:state?.flameDisplay==='hrr'?'display-only Q/HRRPUA area capped by cell area; shared Heskestad height; CAD clipped':state?.flameDisplay==='growth'?'display-only HRR-scaled footprint from room/cell area, CAD clipped; no new fires':state?.flameDisplay==='native'?'native dimensions clipped at room ceiling':'display-only compact location symbols; native HRR unchanged',flameSizes:flames.filter(e=>e.flame.visible).map(e=>({id:e.f.id,physicalHeight:e.physicalHeight,displayHeight:e.displayHeight,enlarged:e.enlarged})),smokeRenderOrder:10,flameRenderOrder:20,depthTest:false}}
 };
}

 return createCfastRealistic(configuration);
}
