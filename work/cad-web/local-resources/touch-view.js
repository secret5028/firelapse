// Pointer Events keep mouse controls intact and handle tablet gestures independently.
function installTabletGestures(canvas,{pan,rotate,zoom}){
 const fingers=new Map();let multi=false,moved=false,start=null,suppressUntil=0;
 const pair=()=>{const [a,b]=[...fingers.values()];return {x:(a.x+b.x)/2,y:(a.y+b.y)/2,d:Math.hypot(a.x-b.x,a.y-b.y)};};
 canvas.style.touchAction='none';
 canvas.addEventListener('pointerdown',e=>{
  if(e.pointerType!=='touch')return;e.preventDefault();e.stopImmediatePropagation();
  if(!fingers.size){multi=false;moved=false;start={x:e.clientX,y:e.clientY};}
  fingers.set(e.pointerId,{x:e.clientX,y:e.clientY});canvas.setPointerCapture(e.pointerId);
  if(fingers.size>1){multi=true;suppressUntil=Date.now()+700;}
 },true);
 canvas.addEventListener('pointermove',e=>{
  if(e.pointerType!=='touch'||!fingers.has(e.pointerId))return;e.preventDefault();e.stopImmediatePropagation();
  const old=fingers.get(e.pointerId),before=fingers.size===2?pair():null;
  fingers.set(e.pointerId,{x:e.clientX,y:e.clientY});
  if(Math.hypot(e.clientX-start.x,e.clientY-start.y)>4)moved=true;
  if(before){const after=pair();pan(after.x-before.x,after.y-before.y);if(before.d>8&&after.d>8)zoom(before.d/after.d);}
  else if(fingers.size===1&&!multi)rotate(e.clientX-old.x,e.clientY-old.y);
 },true);
 function end(e){
  if(e.pointerType!=='touch'||!fingers.has(e.pointerId))return;e.preventDefault();e.stopImmediatePropagation();
  const tap=e.type==='pointerup'&&!multi&&!moved;
  fingers.delete(e.pointerId);if(canvas.hasPointerCapture?.(e.pointerId))canvas.releasePointerCapture(e.pointerId);
  if(multi||moved)suppressUntil=Date.now()+700;
  // Existing model pickers use pointerup; only deliberate single-finger taps reach them.
  if(tap){canvas.onpointerdown?.(e);canvas.onpointerup?.(e);if(canvas.hasPointerCapture?.(e.pointerId))canvas.releasePointerCapture(e.pointerId);}
 }
 for(const name of ['pointerup','pointercancel','lostpointercapture'])canvas.addEventListener(name,end,true);
 canvas.addEventListener('click',e=>{if(Date.now()<suppressUntil){e.preventDefault();e.stopImmediatePropagation();}},true);
}
