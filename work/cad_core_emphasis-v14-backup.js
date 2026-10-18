// Draw vertical circulation after clearing the building depth buffer. The
// overlay retains its own depth tests, so stair treads still occlude correctly.
const coreOverlayScene=new THREE.Scene(),coreOverlayItems=[];
coreOverlayScene.add(new THREE.HemisphereLight(0xffffff,0x5e461e,2.0));
const coreKey=new THREE.DirectionalLight(0xffffff,1.6);coreKey.position.set(40,-60,90);coreOverlayScene.add(coreKey);
const coreSolid=new THREE.MeshLambertMaterial({color:0xffc62f,emissive:0x5e3900,emissiveIntensity:.25,side:THREE.DoubleSide});
const coreEdge=new THREE.LineBasicMaterial({color:0x926207});
function addCoreOverlay(source,kind){
 source.traverse(o=>{if(!(o.isMesh||o.isLine)||o.isSprite||!o.geometry)return;
  const obj=o.clone(false);obj.matrixAutoUpdate=false;
  obj.material=o.isMesh?coreSolid:new THREE.LineBasicMaterial({color:kind==='elev'?0xffdc62:0xd6a825});
  coreOverlayScene.add(obj);coreOverlayItems.push({source:o,obj,kind});
  if(o.isMesh&&o.name.endsWith('_step')){const edge=new THREE.LineSegments(new THREE.EdgesGeometry(o.geometry,25),coreEdge);edge.matrixAutoUpdate=false;coreOverlayScene.add(edge);coreOverlayItems.push({source:o,obj:edge,kind});}
 });
}
for(const root of transport.roots)if(['stair','elev'].includes(root.userData.transportKind))addCoreOverlay(root,root.userData.transportKind);
for(const {context}of incomingStairs)addCoreOverlay(context,'stair');
// A translucent shaft volume and solid frame, not a cabin repeated each floor.
B.floors.forEach((f,i)=>{const root=transport.roots.find(g=>g.userData.floorIndex===i&&g.userData.transportKind==='elev');
 for(const c of f.transport.filter(c=>c.kind==='elev')){
  const shaft=ext(c.region,0,f.h,new THREE.MeshBasicMaterial({color:0xffd447,transparent:true,opacity:.19,depthWrite:false,side:THREE.DoubleSide}));if(!shaft)continue;
  shaft.name='승강로_'+f.name+'_'+c.id;shaft.matrixAutoUpdate=false;coreOverlayScene.add(shaft);coreOverlayItems.push({source:root,obj:shaft,kind:'elev'});
  const frame=new THREE.LineSegments(new THREE.EdgesGeometry(shaft.geometry,25),new THREE.LineBasicMaterial({color:0xffdf62}));frame.matrixAutoUpdate=false;coreOverlayScene.add(frame);coreOverlayItems.push({source:root,obj:frame,kind:'elev'});
 }
});
const coreEmphasisOption=document.createElement('label');coreEmphasisOption.innerHTML='<input id="coreEmphasis" type="checkbox" checked> 계단·승강기 관통 강조';$ui('show_elev').closest('label').after(coreEmphasisOption);
coreEmphasisOption.title='벽 투명도와 무관하게 벽·바닥 너머 계단과 승강로를 강조합니다.';
const originalRender=R.render.bind(R);
R.render=function(scene,camera){
 originalRender(scene,camera);
 if(scene!==S||!$ui('coreEmphasis').checked)return;
 S.updateMatrixWorld(true);
 for(const item of coreOverlayItems){item.obj.visible=visibleByName(item.source);item.obj.matrix.copy(item.source.matrixWorld);}
 const auto=R.autoClear;R.autoClear=false;R.clearDepth();originalRender(coreOverlayScene,camera);R.autoClear=auto;
};
const previousCoreSnapshot=window.cadViewerSnapshot;
window.cadViewerSnapshot=()=>({...previousCoreSnapshot(),version:'cad-ui-v14',coreEmphasis:$ui('coreEmphasis').checked,coreOpacity:1,coreOverlayVisible:coreOverlayItems.filter(i=>i.obj.visible).length});
