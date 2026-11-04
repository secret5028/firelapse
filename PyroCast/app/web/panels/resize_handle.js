// Pointer-captured splitters; listeners and cursor state are owned by the panel.
export function bindResizeHandle(handle,{axis,value,setValue,limits}){
 let drag=null;const previous={cursor:'',select:''};
 const update=v=>{const [min,max]=limits(),n=Math.max(min,Math.min(max,v));setValue(n);handle.setAttribute('aria-valuenow',String(Math.round(n)));};
 const end=()=>{if(!drag)return;const id=drag.id;drag=null;if(handle.hasPointerCapture(id))handle.releasePointerCapture(id);document.body.style.cursor=previous.cursor;document.body.style.userSelect=previous.select;};
 const down=e=>{if(e.button!==0)return;e.preventDefault();drag={id:e.pointerId,at:axis==='x'?e.clientX:e.clientY,size:value()};previous.cursor=document.body.style.cursor;previous.select=document.body.style.userSelect;document.body.style.cursor=axis==='x'?'col-resize':'row-resize';document.body.style.userSelect='none';handle.setPointerCapture(e.pointerId);};
 const move=e=>{if(drag&&drag.id===e.pointerId)update(drag.size+drag.at-(axis==='x'?e.clientX:e.clientY));};
 const key=e=>{const delta={ArrowLeft:20,ArrowUp:20,ArrowRight:-20,ArrowDown:-20}[e.key];if(delta!==undefined){e.preventDefault();update(value()+delta);}};
 const events=[['pointerdown',down],['pointermove',move],['pointerup',end],['pointercancel',end],['lostpointercapture',end],['keydown',key]];
 handle.tabIndex=0;handle.setAttribute('role','separator');handle.setAttribute('aria-orientation',axis==='x'?'vertical':'horizontal');handle.style.touchAction='none';for(const [event,fn] of events)handle.addEventListener(event,fn);
 return ()=>{end();for(const [event,fn] of events)handle.removeEventListener(event,fn);};
}
