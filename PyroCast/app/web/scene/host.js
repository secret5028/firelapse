import {createEmptyLayers} from '../layers/empty.js';
const mounted=new WeakMap();
export function createSceneHost({container,THREE,store,clock={now:()=>performance.now()},
 windowTarget=window,requestFrame=fn=>requestAnimationFrame(fn),cancelFrame=id=>cancelAnimationFrame(id),
 scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(45,1,.1,10000),
 rendererFactory=()=>new THREE.WebGLRenderer({antialias:true,alpha:true}),layers=createEmptyLayers(THREE),seriesAt=()=>null}){
 if(!container||mounted.has(container)||container.querySelector('canvas'))throw Error('Container already owns a canvas/host');
 const ids=layers.map(l=>l.constructor.id);if(new Set(ids).size!==ids.length)throw Error('Duplicate layer IDs');
 let disposed=false,running=false,raf=null,lastTime=null,renderer=null;const cleanups=[];
 const alive=()=>{if(disposed)throw Error('Host disposed');};
 const listen=(target,name,fn,options)=>{alive();target.addEventListener(name,fn,options);const off=()=>target.removeEventListener(name,fn,options);cleanups.push(off);return off;};
 function resize(){const w=Math.max(1,container.clientWidth),h=Math.max(1,container.clientHeight);renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();}
 function moveCamera(value){const p=value.pose;if(p?.position)camera.position.fromArray(p.position);if(p?.up)camera.up.fromArray(p.up);if(p?.quaternion)camera.quaternion.fromArray(p.quaternion);else if(Array.isArray(value.target))camera.lookAt(...value.target);camera.updateMatrixWorld();}
 function render(){alive();const now=clock.now();if(!Number.isFinite(now))throw Error('Clock must return finite milliseconds');
  const dt=lastTime===null?0:Math.max(0,(now-lastTime)/1000);lastTime=now;
  const playback=store.get('playback');if(running&&playback.playing){store.dispatch('playback/seek',{t_s:playback.t_s+dt*playback.speed});if(store.get('playback').t_s>=playback.t_end_s)store.dispatch('playback/play',{playing:false});}
  const t=store.get('playback').t_s,frame={building:store.get('building'),resultMeta:store.get('result'),series:seriesAt(t),t_s:t,selection:store.get('selection'),floor:store.get('floor'),risk:store.get('risk')};
  const visible=store.get('layers');for(const layer of layers){layer.setData(frame);layer.setVisible(visible[layer.constructor.id]!==false);layer.tick?.(dt,now/1000);}
  renderer.render(scene,camera);
 }
 function loop(){raf=null;if(!running||disposed)return;try{render();}catch(error){stop();throw error;}if(running&&!disposed)raf=requestFrame(loop);}
 function start(){alive();if(running)return;running=true;lastTime=null;raf=requestFrame(loop);}
 function stop(){running=false;lastTime=null;if(raf!==null)cancelFrame(raf);raf=null;}
 function dispose(){if(disposed)return;stop();disposed=true;const errors=[];
  for(const off of cleanups.splice(0))try{off();}catch(e){errors.push(e);}
  for(const layer of [...layers].reverse())try{layer.dispose();}catch(e){errors.push(e);}
  if(renderer){try{renderer.renderLists?.dispose();renderer.dispose();renderer.forceContextLoss?.();}catch(e){errors.push(e);}renderer.domElement.remove();}
  mounted.delete(container);if(errors.length)throw new AggregateError(errors,'Host cleanup failed');
 }
 try{mounted.set(container,true);renderer=rendererFactory();container.append(renderer.domElement);camera.up.set(0,0,1);
  for(const layer of layers)layer.mount(scene,store);
  cleanups.push(store.subscribe('camera',moveCamera));listen(windowTarget,'resize',resize);moveCamera(store.get('camera'));resize();
 }catch(e){dispose();throw e;}
 return Object.freeze({start,stop,dispose,render,listen,scene,camera,renderer,
  diagnostics:()=>({running,disposed,pendingFrame:raf!==null,canvasCount:container.querySelectorAll('canvas').length,sceneObjects:countObjects(scene)})});
}
function countObjects(scene){let n=0;scene.traverse(()=>n++);return n;}
