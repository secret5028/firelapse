import {attach as attachLegacy} from './panels/legacy_overlay.js';
import {attachModern} from './controller.js';
const attached=new WeakMap();
export async function attach(viewer){
 if(attached.has(viewer.R.domElement))return attached.get(viewer.R.domElement);
 const pending=(async()=>{
  if(new URL(location.href).searchParams.get('ui')==='legacy')return attachLegacy(viewer);
  const r=await fetch('/cfbt/lite/active.json'),data=r.ok?await r.json():null;
  if(data?.engine_kind!=='pyrocast_lite')return attachLegacy(viewer);
  document.documentElement.dataset.pyrocastUi='modern';
  return attachModern(viewer,data);
 })();attached.set(viewer.R.domElement,pending);return pending;
}
