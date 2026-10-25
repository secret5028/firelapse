// Display contract only. No combustion, temperature, soot, or propagation is calculated here.
export function gasVisualState({time,times,power,assumption,room}){
 if(!power?.length||!times?.length)return {q:0,active:false};
 let lo=0,hi=times.length-1;
 while(hi-lo>1){const m=(lo+hi)>>1;if(times[m]<=time)lo=m;else hi=m;}
 const a=Number(power[lo])||0,b=Number(power[hi])||0;
 const f=Math.max(0,Math.min(1,(time-times[lo])/(times[hi]-times[lo]||1)));
 let q=Math.max(0,a+(b-a)*f);
 // Never interpolate a future ignition into earlier frames. For the intervention
 // only its known start time can resolve the onset inside a saved output interval.
 if(a<=.001&&b>.001&&time<times[hi]){
  const known=assumption?.room===room?assumption.time_s:null;
  if(known===null||known<times[lo]-.01||known>=times[hi]||time<=known)q=0;
  else q=b*Math.max(0,Math.min(1,(time-known)/(times[hi]-known)));
 }
 return {q,active:q>.001,intensity:Math.min(1,Math.log1p(q)/Math.log(2001)),displayOnly:true};
}
