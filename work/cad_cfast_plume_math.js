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
