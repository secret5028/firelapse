import {attachModern} from './controller.js';
const attached=new WeakMap();
export async function attach(viewer){
 if(attached.has(viewer.R.domElement))return attached.get(viewer.R.domElement);
 const loading=document.createElement('div');loading.id='firelapseLoading';loading.setAttribute('role','status');loading.style.cssText='position:fixed;inset:0;z-index:10000;background:color-mix(in srgb,var(--bg-scene) 92.941176%,transparent);color:var(--text);display:grid;place-content:center;text-align:center;font:16px system-ui';loading.textContent='건물·저장 결과 불러오는 중…';document.body.append(loading);
 const pending=(async()=>{
  try{
  const r=await fetch('/cfbt/lite/active.json'),data=r.ok?await r.json():null;
  if(data?.engine_kind!=='pyrocast_lite'&&!(data?.engine_kind==='cfast_native'&&['wando-c11-p1-v1','fixed-r8-native-v1'].includes(data.native_mapping)))throw Error('지원하지 않는 결과 형식입니다. 저장 사례를 확인하세요.');
  document.documentElement.dataset.pyrocastUi='modern';
  const app=await attachModern(viewer,data);loading.remove();return app;
  }catch(error){loading.textContent='불러오기 실패 · '+error.message;throw error;}
 })();attached.set(viewer.R.domElement,pending);return pending;
}
