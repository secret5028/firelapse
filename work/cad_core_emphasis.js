// Keep circulation inside the normal building depth buffer. Its transparency
// responds at one quarter of the wall slider, without an X-ray overlay pass.
const coreMaterials=[];
function styleCirculation(root){
 root.traverse(o=>{
  if(!(o.isMesh||o.isLine)||!o.material||o.isSprite)return;
  const original=o.material;
  o.material=original.clone();
  const baseOpacity=o.isLine?.85:(original.transparent?Math.min(original.opacity,.75):1);
  o.material.color.set(o.isLine?0xa78a49:0xcbb475);
  if(o.material.emissive)o.material.emissive.setHex(0x000000);
  o.material.depthTest=true;o.material.depthWrite=true;
  coreMaterials.push({material:o.material,baseOpacity});
 });
}
for(const root of transport.roots)if(['stair','elev'].includes(root.userData.transportKind))styleCirculation(root);
for(const {context}of incomingStairs)styleCirculation(context);
// A subdued translucent shaft stays at the extracted core coordinates and
// is occluded by walls/slabs like every other part of the building.
B.floors.forEach((f,i)=>{const root=transport.roots.find(g=>g.userData.floorIndex===i&&g.userData.transportKind==='elev');
 for(const c of f.transport.filter(c=>c.kind==='elev')){
  const material=new THREE.MeshLambertMaterial({color:0xcbb475,transparent:true,opacity:.22,depthTest:true,depthWrite:false,side:THREE.DoubleSide});
  const shaft=ext(c.region,0,f.h,material);if(!shaft)continue;
  shaft.name='승강로_'+f.name+'_'+c.id;root.add(shaft);coreMaterials.push({material,baseOpacity:.22,volume:true});
  const frameMat=new THREE.LineBasicMaterial({color:0xb29a5f,transparent:true,opacity:.85,depthTest:true});
  const frame=new THREE.LineSegments(new THREE.EdgesGeometry(shaft.geometry,25),frameMat);root.add(frame);coreMaterials.push({material:frameMat,baseOpacity:.85});
 }
});
const coreEmphasisOption=document.createElement('label');coreEmphasisOption.innerHTML='<input id="coreEmphasis" type="checkbox" checked> 계단·승강기 선명도 유지';$ui('show_elev').closest('label').after(coreEmphasisOption);
coreEmphasisOption.title='건물 안쪽 깊이를 유지하며 벽 투명도의 영향을 25%만 받습니다.';
function syncCoreOpacity(){
 const t=+$ui('wallTransparency').value/100,factor=$ui('coreEmphasis').checked?.25:1;
 for(const item of coreMaterials){const m=item.material;m.opacity=item.baseOpacity*(1-factor*t);m.transparent=m.opacity<1;m.depthTest=true;m.depthWrite=!item.volume&&m.opacity>.01;m.needsUpdate=true;}
 document.body.dataset.coreOpacity=String(1-factor*t);
}
const previousWallOpacity=$ui('wallTransparency').oninput;$ui('wallTransparency').oninput=e=>{previousWallOpacity(e);syncCoreOpacity()};
const previousLegacyOpacity=$ui('op').oninput;$ui('op').oninput=e=>{previousLegacyOpacity(e);syncCoreOpacity()};
$ui('coreEmphasis').onchange=syncCoreOpacity;syncCoreOpacity();
const previousCoreSnapshot=window.cadViewerSnapshot;
window.cadViewerSnapshot=()=>({...previousCoreSnapshot(),version:'cad-ui-v15',coreEmphasis:$ui('coreEmphasis').checked,coreOpacity:Number(document.body.dataset.coreOpacity),coreDepthTest:true,coreOverlay:false,wallTransparency:+$ui('wallTransparency').value});
