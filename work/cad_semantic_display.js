// Legacy semantic palette: structure blue-grey, openings yellow/cyan,
// vertical circulation gold, fire facilities red, routes yellow.
for(const key of XR)mat[key].color.set('#abc8d6');
mat.slab.color.set('#d4d0b7');leafMat.color.set('#ffd343');
for(const leaf of leaves)leaf.guide.material.color.set('#e8bd49');
for(const G of groups)for(const mesh of G.children)if(/^.+_R\d+$/.test(mesh.name))mesh.material.color.set('#d4d0b7');
const coreLabels=[],coreHUD=[];
B.floors.forEach((f,i)=>{
 for(const core of f.transport){
  const g=transport.roots.find(g=>g.userData.floorIndex===i&&g.userData.transportKind===core.kind);
  const points=core.anchor.flatMap(p=>p.o),x=(Math.min(...points.map(p=>p[0]))+Math.max(...points.map(p=>p[0])))/2,y=(Math.min(...points.map(p=>p[1]))+Math.max(...points.map(p=>p[1])))/2;
  const markerRoot=new THREE.Group();markerRoot.rotation.x=Math.PI/2;g.add(markerRoot);
  const marker=addElevatorMarker(THREE,markerRoot,x,0,-y,core.kind==='elev'?'승강기':'계단');
  marker.children.find(o=>o.isSprite).visible=false;
  coreLabels.push(marker);
 }
});
// Group nearby same-kind markers to keep labels readable at building scale.
B.floors.forEach((f,i)=>{for(const kind of ['stair','elev']){const remaining=f.transport.filter(c=>c.kind===kind).map(c=>{const q=c.anchor.flatMap(p=>p.o);return {x:q.reduce((n,p)=>n+p[0],0)/q.length,y:q.reduce((n,p)=>n+p[1],0)/q.length}});
 while(remaining.length){const first=remaining.shift(),cluster=[first];for(let j=remaining.length-1;j>=0;j--)if(Math.hypot(remaining[j].x-first.x,remaining[j].y-first.y)<5)cluster.push(...remaining.splice(j,1));
 const div=document.createElement('div');div.className='lb';div.style.cssText='background:#f5d66b;color:#463708;font-weight:700;border:1px solid #84661b;font-size:12px;padding:2px 5px;display:none';div.textContent=(kind==='stair'?'계단':'↕ 승강기')+(cluster.length>1?' ×'+cluster.length:'');const label=new CSS2DObject(div);label.position.set(cluster.reduce((n,p)=>n+p.x,0)/cluster.length,cluster.reduce((n,p)=>n+p.y,0)/cluster.length,1.35);transport.roots.find(g=>g.userData.floorIndex===i&&g.userData.transportKind===kind).add(label);coreHUD.push({label,i,kind});
 }}});
// Roof terrace pieces supplement the upper-floor slab. The shared slab is not
// duplicated as a second ceiling, and suspended ceilings stay independent.
const structuralRoofs=[];
for(const top of B.structural_tops||[]){const material=new THREE.MeshLambertMaterial({color:'#93acb5',side:THREE.DoubleSide});const mesh=ext(top.roof_polys,top.z-.2,top.z,material);const ceiling=ext(top.ceiling_polys||[],top.z-.2,top.z,material);if(mesh){mesh.name='구조슬래브_'+top.from_floor;S.add(mesh)}if(ceiling){ceiling.name='구조천장_'+top.from_floor;S.add(ceiling)}structuralRoofs.push({mesh,ceiling,top})}
const roofOption=document.createElement('label');roofOption.innerHTML='<input id="structuralCeiling" type="checkbox"> 선택 층 구조 슬래브 천장';$ui('layer_floor').closest('label').after(roofOption);
window.cadAdditionalBounds=()=>{const box=new THREE.Box3();for(const {mesh,ceiling}of structuralRoofs)for(const obj of [mesh,ceiling])if(obj?.visible)box.union(new THREE.Box3().setFromObject(obj));return box};
function syncRoof(){for(const {mesh,ceiling,top}of structuralRoofs){const full=$ui('structuralCeiling').checked&&top.from_floor===selFloor;const aboveGround=B.floors.find(f=>f.name===top.from_floor).z>=groundZ;if(mesh)mesh.visible=$ui('layer_floor').checked&&!full&&aboveGround&&(selFloor==='all'||top.to_floor===selFloor);if(ceiling)ceiling.visible=$ui('layer_floor').checked&&full}}
const oldApply=applyFloor;applyFloor=function(){oldApply();syncRoof()};
$ui('structuralCeiling').onchange=syncRoof;
for(const button of $ui('fbtn').children)button.addEventListener('click',syncRoof);
for(const id of ['layer_floor','above'])$ui(id).onchange=applyFloor;
// Connected ramps use the real storey rise, not the old arbitrary 10% preview.
function connectedRampHeights(){
 for(const ramp of transport.ramps){if(!Number.isFinite(ramp.data.rise_m))continue;const a=ramp.geo.attributes.position;let k=0;const rise=ramp.data.rise_m;
  for(let j=0;j<ramp.N-1;j++)for(const index of [j,j,j+1,j,j+1,j+1])a.setZ(k++,rise*index/(ramp.N-1));
  a.needsUpdate=true;ramp.geo.computeVertexNormals();ramp.geo.computeBoundingSphere();
  ramp.edges.forEach(edge=>{const p=edge.geometry.attributes.position;for(let j=0;j<ramp.N;j++)p.setZ(j,.02+rise*j/(ramp.N-1));p.needsUpdate=true;edge.geometry.computeBoundingSphere()});
 }
}
connectedRampHeights();
const incomingStairs=[];
for(const link of B.vertical_connections.filter(l=>l.kind==='stair')){const fi=B.floors.findIndex(f=>f.name===link.from_floor),source=transport.roots.find(g=>g.userData.floorIndex===fi&&g.userData.transportKind==='stair');const context=new THREE.Group();context.position.z=B.floors[fi].z;context.name='아래층 연결계단_'+link.from_floor+'_'+link.from_core;for(const child of source.children)if(child.name===link.from_floor+'_'+link.from_core+'_step')context.add(child.clone());S.add(context);incomingStairs.push({context,link})}
const connected=transport.ramps.filter(r=>Number.isFinite(r.data.rise_m));
if(connected.length){$ui('ramp_slope').disabled=true;$ui('ramp_reverse').disabled=true;$ui('ramp_value').textContent=connected[0].data.slope_percent.toFixed(1)+'%';
 const note=$ui('ramp_reverse').closest('label').nextElementSibling;note.textContent=connected.map(r=>`${r.data.from_floor} ↔ ${r.data.to_floor} · ${r.data.span_degrees}° 반원 · 높이차 ${r.data.rise_m.toFixed(2)}m · 중심선 경사 ${r.data.slope_percent.toFixed(1)}%`).join(' / ');}
// Show a connected ramp from either endpoint floor without showing the entire basement.
for(const root of transport.roots.filter(g=>g.userData.transportKind==='ramp')){const i=root.userData.floorIndex;root.removeFromParent();S.add(root);root.position.z=B.floors[i].z;}
const priorTransport=syncTransport;syncTransport=function(){priorTransport();for(const root of transport.roots.filter(g=>g.userData.transportKind==='ramp')){const f=B.floors[root.userData.floorIndex];root.visible=$ui('sh').checked&&$ui('show_ramp').checked&&(selFloor==='all'||f.name===selFloor||f.model_ramps.some(r=>r.to_floor===selFloor))}for(const {label,i,kind}of coreHUD){label.visible=selFloor===B.floors[i].name&&groups[i].visible&&$ui('sh').checked&&$ui('show_'+kind).checked;label.element.style.display=label.visible?'':'none'}for(const {context,link}of incomingStairs)context.visible=selFloor===link.to_floor&&$ui('sh').checked&&$ui('show_stair').checked};
for(const id of ['sh','show_stair','show_elev','show_ramp','show_anchor'])$ui(id).onchange=syncTransport;
const legend=document.createElement('p');legend.className='small';legend.innerHTML='<span style="color:#abc8d6">■ 구조</span> · <span style="color:#ffd343">■ 문·수직이동</span><br><span style="color:#7fc8ff">■ 창</span> · <span style="color:#ff6679">■ 소방 설비</span>';panel.insertBefore(legend,advanced);
syncRoof();syncTransport();
