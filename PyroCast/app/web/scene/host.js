import {createEmptyLayers} from '../layers/empty.js';
import {ROOM_PICK_LAYER} from './picking.js';
import {fixedOpeningsFor} from '../state/fixed_openings.js';
const mounted=new WeakMap();
export function createSceneHost({container,THREE,store,clock={now:()=>performance.now()},
 windowTarget=window,requestFrame=fn=>requestAnimationFrame(fn),cancelFrame=id=>cancelAnimationFrame(id),
 scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(45,1,.1,10000),
 rendererFactory=()=>new THREE.WebGLRenderer({antialias:true,alpha:true}),layers=createEmptyLayers(THREE),seriesAt=()=>null,
 adoptedRenderer=null,legendContainer=null,groundPick=null}){
 if(!container||mounted.has(container)||(container.querySelector('canvas')&&container.querySelector('canvas')!==adoptedRenderer?.domElement))throw Error('Container already owns a canvas/host');
 const ids=layers.map(l=>l.constructor.id);if(new Set(ids).size!==ids.length)throw Error('Duplicate layer IDs');
 let disposed=false,running=false,raf=null,lastTime=null,renderer=null,legendAnchor=null;const cleanups=[];
 const alive=()=>{if(disposed)throw Error('Host disposed');};
 const listen=(target,name,fn,options)=>{alive();target.addEventListener(name,fn,options);const off=()=>target.removeEventListener(name,fn,options);cleanups.push(off);return off;};
 function providePlumeLegend(){alive();if(legendAnchor)return legendAnchor;
  const doc=container.ownerDocument;
  if(legendContainer){if(legendContainer.id!=='cfMeaning'||doc.getElementById('cfMeaning')!==legendContainer||doc.getElementById('cfPlumeLegend'))throw Error('Invalid borrowed legend');legendAnchor=legendContainer;cleanups.push(()=>{doc.getElementById('cfPlumeLegend')?.remove();legendAnchor=null;});return legendAnchor;}
  if(doc.getElementById('cfMeaning')||doc.getElementById('cfPlumeLegend'))throw Error('Legacy plume legend already owned by another viewer');
  legendAnchor=doc.createElement('span');legendAnchor.id='cfMeaning';legendAnchor.hidden=true;container.append(legendAnchor);
  cleanups.push(()=>{doc.getElementById('cfPlumeLegend')?.remove();legendAnchor.remove();legendAnchor=null;});return legendAnchor;
 }
 function resize(){const w=Math.max(1,container.clientWidth),h=Math.max(1,container.clientHeight);renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();}
 function moveCamera(value){const p=value.pose;if(p?.position)camera.position.fromArray(p.position);if(p?.up)camera.up.fromArray(p.up);if(p?.quaternion)camera.quaternion.fromArray(p.quaternion);else if(Array.isArray(value.target))camera.lookAt(...value.target);camera.updateMatrixWorld();}
 function bindPicking(){
  const ray=new THREE.Raycaster(),mouse=new THREE.Vector2(),pointers=new Set();let down=null;
  ray.layers.set(ROOM_PICK_LAYER);
  const canvas=renderer.domElement;
  listen(canvas,'pointerdown',e=>{pointers.add(e.pointerId);down=pointers.size===1&&e.button===0?{id:e.pointerId,x:e.clientX,y:e.clientY,tolerance:e.pointerType==='touch'?10:5,source:e.pointerType==='touch'?'touch':'click'}:null;});
  listen(canvas,'pointermove',e=>{if(down&&Math.hypot(e.clientX-down.x,e.clientY-down.y)>down.tolerance)down=null;});
  listen(canvas,'pointercancel',e=>{pointers.delete(e.pointerId);down=null;});
  listen(canvas,'pointerup',e=>{pointers.delete(e.pointerId);const start=down;down=null;
   if(!start||start.id!==e.pointerId||pointers.size||Math.hypot(e.clientX-start.x,e.clientY-start.y)>start.tolerance)return;
   const b=canvas.getBoundingClientRect();if(!b.width||!b.height)return;
   mouse.set((e.clientX-b.x)/b.width*2-1,-(e.clientY-b.y)/b.height*2+1);scene.updateMatrixWorld(true);camera.updateMatrixWorld();ray.setFromCamera(mouse,camera);
   if(groundPick?.active()){const hit=ray.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0,0,1),-groundPick.z),new THREE.Vector3());if(hit)groundPick.place(hit.toArray());return;}
   const floorId=store.get('floor').floor_id,planes=(layers.find(l=>l.constructor.id==='selection')?.getPickPlanes?.()||[]).filter(p=>{
    if(floorId!==null&&p.userData.floorId!==floorId)return false;for(let node=p;node;node=node.parent)if(!node.visible)return false;return true;
   });
   const hit=ray.intersectObjects(planes,false)[0];if(hit)store.dispatch('selection/set',{room_id:hit.object.userData.roomId,cell_id:hit.object.userData.liteRoom,source:start.source});
  });
  cleanups.push(()=>{pointers.clear();down=null;});
 }
 function render(){alive();const now=clock.now();if(!Number.isFinite(now))throw Error('Clock must return finite milliseconds');
  const dt=lastTime===null?0:Math.max(0,(now-lastTime)/1000);lastTime=now;
  const playback=store.get('playback');if(running&&playback.playing){store.dispatch('playback/seek',{t_s:playback.t_s+dt*playback.speed});if(store.get('playback').t_s>=playback.t_end_s)store.dispatch('playback/play',{playing:false});}
  const t=store.get('playback').t_s,frame={building:store.get('building'),resultMeta:store.get('result'),series:seriesAt(t),t_s:t,selection:store.get('selection'),floor:store.get('floor'),route:store.get('route'),risk:store.get('risk'),layers:store.get('layers'),realView:store.get('realView'),reducedMotion:windowTarget.matchMedia?.('(prefers-reduced-motion: reduce)').matches??false};
  frame.fuelSettings=store.get('fuelSettings');
  frame.fixedOpenings=store.get('openings').fixed?fixedOpeningsFor(frame.building,store.get('buildingReview')):null;
  const visible=store.get('layers');for(const layer of layers){layer.setData(frame);layer.setVisible(visible[layer.constructor.id]!==false);layer.tick?.(dt,now/1000);}
  renderer.render(scene,camera);
 }
 function loop(){raf=null;if(!running||disposed)return;try{render();}catch(error){stop();throw error;}if(running&&!disposed)raf=requestFrame(loop);}
 function start(){alive();if(running)return;running=true;lastTime=null;raf=requestFrame(loop);}
 function stop(){running=false;lastTime=null;if(raf!==null)cancelFrame(raf);raf=null;}
 function dispose(){if(disposed)return;stop();disposed=true;const errors=[];
  for(const off of cleanups.splice(0))try{off();}catch(e){errors.push(e);}
  for(const layer of [...layers].reverse())try{layer.dispose();}catch(e){errors.push(e);}
  if(renderer&&!adoptedRenderer){try{renderer.renderLists?.dispose();renderer.dispose();renderer.forceContextLoss?.();}catch(e){errors.push(e);}renderer.domElement.remove();}
  mounted.delete(container);if(errors.length)throw new AggregateError(errors,'Host cleanup failed');
 }
 try{mounted.set(container,true);renderer=adoptedRenderer||rendererFactory();if(!adoptedRenderer)container.append(renderer.domElement);camera.up.set(0,0,1);
  if(layers.some(l=>l.needsPlumeLegend))providePlumeLegend();
  for(const layer of layers)layer.mount(scene,store);
  bindPicking();
  cleanups.push(store.subscribe('camera',moveCamera));listen(windowTarget,'resize',resize);moveCamera(store.get('camera'));resize();
 }catch(e){dispose();throw e;}
 return Object.freeze({start,stop,dispose,render,listen,providePlumeLegend,scene,camera,renderer,
  diagnostics:()=>({running,disposed,pendingFrame:raf!==null,canvasCount:container.querySelectorAll('canvas').length,sceneObjects:countObjects(scene)})});
}
function countObjects(scene){let n=0;scene.traverse(()=>n++);return n;}
