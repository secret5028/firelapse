// Presentation-only switches, applied by the panel boundary after layer.tick().
// Layer geometry, saved values, materials and risk gates remain unchanged.
export function createDisplayPolicy(store){
 const masks=new WeakMap(),labels=new Map();let currentViews=[],labelObjects=[],labelScene=null,labelKey=null;
 const mask=(object,on)=>{if(!masks.has(object))masks.set(object,object.layers.mask);object.layers.mask=on?masks.get(object):0;};
 const inside=(p,ring)=>{let yes=false;for(let i=0,j=ring.length-1;i<ring.length;j=i++){const a=ring[i],b=ring[j];if((a[1]>p[1])!==(b[1]>p[1])&&p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0])yes=!yes;}return yes;};
 function apply({risk,scene}){
  const detail=store.get('displayDetails');currentViews=risk.views;
  for(const v of currentViews){
   mask(v.tint,detail.floorTint);mask(v.interfaceLine,detail.smokeInterface);mask(v.interfacePlane,detail.smokeInterface);
   const caution=store.get('risk').show.smoke&&v.line.material.color.getHexString()==='9ca3af';
   mask(v.line,caution||(v.line.material.gapSize>0?detail.boundaryDots:detail.cellOutline));
  }
  const all=store.get('floor').floor_id===null,selected=store.get('selection').room_id,building=store.get('building');
  const key=[all,selected,building];if(labelScene===scene&&labelKey&&key.every((v,i)=>v===labelKey[i]))return;labelKey=key;
  if(labelScene!==scene){labelScene=scene;labelObjects=[];scene.traverse(o=>{if(o.element&&/(계단|승강기)/.test(o.element.textContent)&&o.element.classList.contains('lb'))labelObjects.push(o);});}
  const room=building?.floors.flatMap(f=>f.rooms).find(r=>r.room_id===selected);
  for(const o of labelObjects){const el=o.element;
   if(!labels.has(el))labels.set(el,[el.style.getPropertyValue('visibility'),el.style.getPropertyPriority('visibility')]);
   const p=o.getWorldPosition(o.position.clone()),inRoom=room?.polygons_m.some(poly=>inside([p.x,p.y],poly.polygon_m)&&!(poly.holes_m||[]).some(h=>inside([p.x,p.y],h)));
   // !important survives the retained CAD label loop's display updates.
   el.style.setProperty('visibility',all||inRoom?'visible':'hidden','important');
  }
  for(const hint of document.querySelectorAll('.viewHint'))hint.hidden=!all;
 }
 return {apply,dispose(){for(const v of currentViews)for(const o of [v.tint,v.line,v.interfaceLine,v.interfacePlane])if(masks.has(o))o.layers.mask=masks.get(o);for(const [el,[value,priority]] of labels)el.style.setProperty('visibility',value,priority);for(const hint of document.querySelectorAll('.viewHint'))hint.hidden=false;labels.clear();currentViews=[];labelObjects=[];labelScene=null;labelKey=null;}};
}
