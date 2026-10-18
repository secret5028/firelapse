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
    e.mesh.visible=s.enabled&&s.realView&&e.f.ignition_time!==null&&s.time>=e.f.ignition_time&&q>.01;
    if(!e.mesh.visible)continue;
    if(e.frame!==i){e.frame=i;const zone=e.r.series[i],factor=e.input.corner_factor,p={...e.input,q:q*1000*factor,area:e.input.area*factor,tu:zone[1]+273.15,tl:zone[2]+273.15,layer:zone[3]};
     const fh=CfastPlumeMath.flame(q*1000,e.input.area);e.mesh.material.uniforms.uFlame.value=fh;
     for(let z=0;z<N;z++)for(let x=0;x<N;x++){const zz=z/(N-1)*e.r.height,rr=x/(N-1)*e.radius,ambient=zz<=p.layer?p.tl:p.tu,a=CfastPlumeMath.plume(p,zz,rr),b=CfastPlumeMath.ceiling(p,zz,rr);e.pixels.set([Math.max(0,a.temperature-ambient),a.velocity,Math.max(0,b.temperature-ambient),b.velocity],(z*N+x)*4)}
     e.texture.needsUpdate=true;const top=CfastPlumeMath.plume(p,p.height,0),cj=CfastPlumeMath.ceiling(p,p.height,Math.min(1,e.radius));
     e.summary={id:e.f.id,room:e.r.key,flameHeight:fh,diameter:Math.sqrt(4*e.input.area/Math.PI),ceilingAxisC:top.temperature-273.15,upSpeed:top.velocity,ceilingThicknessAt1m:cj.thickness,ceilingSpeedAt1m:cj.velocity,cornerFactor:factor};
    }summaries.push(e.summary);
   }
   document.getElementById('cfPlumeNumbers').textContent=summaries.length?`평균 화염 높이 ${Math.min(...summaries.map(x=>x.flameHeight)).toFixed(2)}–${Math.max(...summaries.map(x=>x.flameHeight)).toFixed(2)}m · 천장 도달 중심 최고 ${Math.max(...summaries.map(x=>x.ceilingAxisC)).toFixed(0)}°C`:'연소 중인 계산 화원 없음';
  },
  animate(now){for(const e of objects)if(e.mesh.visible){const m=e.mesh,u=m.material.uniforms;m.updateWorldMatrix(true,false);u.uCamera.value.copy(C.position);m.worldToLocal(u.uCamera.value);u.uTime.value=now/1000;const c=u.uCamera.value;m.material.side=c.x>0&&c.x<1&&c.y>0&&c.y<1&&c.z>0&&c.z<1?THREE.BackSide:THREE.FrontSide;}},
  stats(){return {method:'CFAST-7.7.7-correlations-postprocess',gasVolumes:objects.filter(e=>e.mesh.visible).length,flameAndGasSeparate:true,samples:summaries,profileResolution:96,raySteps:48}}
 };
}
