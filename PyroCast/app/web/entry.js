import {attachModern} from './controller.js';
const attached=new WeakMap();
export async function attach(viewer){
 if(attached.has(viewer.R.domElement))return attached.get(viewer.R.domElement);
 const pending=(async()=>{
  const r=await fetch('/cfbt/lite/active.json'),data=r.ok?await r.json():null;
  if(data?.engine_kind!=='pyrocast_lite'&&!(data?.engine_kind==='cfast_native'&&data.native_mapping==='wando-c11-p1-v1'))throw Error('지원하지 않는 결과 형식입니다. 저장 사례를 확인하세요.');
  document.documentElement.dataset.pyrocastUi='modern';
  return attachModern(viewer,data);
 })();attached.set(viewer.R.domElement,pending);return pending;
}
