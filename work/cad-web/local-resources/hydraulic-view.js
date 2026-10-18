// Nearby inlets share a clickable display marker; model coordinates remain unchanged.
function hydraulicInletMarkers(nodes,selected){
 const remaining=new Set(nodes.filter(p=>p.type==='inlet')),result=new Map();
 while(remaining.size){const first=remaining.values().next().value;remaining.delete(first);const cluster=[first];
  for(let i=0;i<cluster.length;i++)for(const p of [...remaining])if(Math.hypot(p.x-cluster[i].x,p.y-cluster[i].y,p.z-cluster[i].z)<.9){remaining.delete(p);cluster.push(p);}
  const representative=cluster.find(p=>p.id===selected)||first;result.set(representative.id,cluster.length);
 }return result;
}
// Diameter affects size; selection only affects color/opacity. Display scale is 1.5x.
function hydraulicPipeRadius(p){
 const size=Number(p.outerDiameterMm)>0?Number(p.outerDiameterMm):Number(p.nominalMm)>0?Number(p.nominalMm):Number(p.diameterMm)>0?Number(p.diameterMm):null;
 return {radius:size?size/2000*1.5:.015,known:size!==null,size};
}
// Shared overlay for reviewed building viewers; positions are world metres.
// Preserve only the supply path to the selected floor, not every lower-floor branch.
function hydraulicFloorPipeIds(network,floorValue){
 const result=new Set(),nodes=new Map(network.nodes.map(n=>[n.id,n]));
 const root=network.nodes.find(n=>n.id===network.visualRootId)||network.nodes.find(n=>n.id===network.inlet&&n.type==='inlet')||network.nodes.find(n=>n.type==='inlet');
 const floor=floorValue&&floorValue!=='all'?Number(floorValue.split('|').pop()):null;
 const allowed=network.pipes.filter(p=>p.state==='open'&&nodes.has(p.from)&&nodes.has(p.to));
 for(const p of network.pipes.filter(p=>nodes.has(p.from)&&nodes.has(p.to)))if(floor===null||(nodes.get(p.from).floor===floor&&nodes.get(p.to).floor===floor))result.add(p.id);
 if(!root||floor===null)return result;
 const distances=new Map([[root.id,0]]),parents=new Map(),pending=new Set([root.id]);
 while(pending.size){const u=[...pending].reduce((a,b)=>distances.get(a)<=distances.get(b)?a:b);pending.delete(u);
  for(const p of allowed){const v=p.from===u?p.to:(p.to===u&&p.direction==='both'?p.from:null);if(!v)continue;const a=nodes.get(u),b=nodes.get(v);const length=Math.hypot(b.x-a.x,b.y-a.y,b.z-a.z);if(!Number.isFinite(length))continue;const d=distances.get(u)+Math.max(.001,length);
   if(d<(distances.get(v)??Infinity)){distances.set(v,d);parents.set(v,{node:u,pipe:p.id});pending.add(v);}
  }
 }
 for(const target of network.nodes.filter(n=>n.floor===floor||n.equipmentType==='pump'||n.equipmentType==='tank')){let id=target.id;const visited=new Set();while(parents.has(id)&&!visited.has(id)){visited.add(id);const p=parents.get(id);result.add(p.pipe);id=p.node;}}
 if(network.tankSupplyId&&root.id!==network.tankSupplyId){for(const id of hydraulicFloorPipeIds({...network,visualRootId:network.tankSupplyId,tankSupplyId:null},floorValue))result.add(id);}
 return result;
}
// Direction follows reachable open connections from the selected inlet.
function hydraulicFlowDistances(n){
 const distances=new Map([[n.inlet,0]]),nodes=new Map(n.nodes.map(v=>[v.id,v])),queue=[n.inlet];
 while(queue.length){const id=queue.shift(),a=nodes.get(id);if(!a)continue;
  for(const p of n.pipes){if(p.state!=='open')continue;const next=p.from===id?p.to:(p.to===id&&p.direction==='both'?p.from:null),b=nodes.get(next);if(!b||(b.type==='inlet'&&next!==n.inlet))continue;
   const d=distances.get(id)+Math.hypot(a.x-b.x,a.y-b.y,a.z-b.z);
   if(d<(distances.get(next)??Infinity)-1e-8){distances.set(next,d);queue.push(next);}
  }
 }return distances;
}
// Merge only degree-two collinear junctions for display. The hydraulic graph stays intact.
function hydraulicDisplayPipes(n,selectedIds,floorIds){
 const nodes=new Map(n.nodes.map(v=>[v.id,v])),selected=new Set(selectedIds),incident=new Map();
 const pipes=n.pipes.map(p=>({...p,sourcePipeIds:[p.id]})),alive=new Set(pipes);
 const add=(id,p)=>{if(!incident.has(id))incident.set(id,new Set());incident.get(id).add(p);};
 for(const p of pipes){add(p.from,p);add(p.to,p);}
 const fields=['system','state','direction','nominalMm','outerDiameterMm','diameterMm','geometryType','sourcePage'];
 for(const node of n.nodes){
  const edges=[...(incident.get(node.id)||[])].filter(p=>alive.has(p));
  if(edges.length!==2||node.type!=='junction'||node.equipmentType||node.valve||node.name?.includes('밸브'))continue;
  const [p,q]=edges;if(fields.some(k=>p[k]!==q[k])||selected.has(p.id)!==selected.has(q.id)||floorIds.has(p.id)!==floorIds.has(q.id))continue;
  // Preserve directed connectivity and do not merge across floors or a bend.
  if(p.direction!=='both'&&!(p.to===node.id&&q.from===node.id||q.to===node.id&&p.from===node.id))continue;
  const a=nodes.get(p.from===node.id?p.to:p.from),b=nodes.get(q.from===node.id?q.to:q.from);
  if(!a||!b||a.floor!==node.floor||b.floor!==node.floor)continue;
  const keys=['x','y','z'],axis=keys.filter(k=>Math.abs(a[k]-node[k])>.0002);
  if(axis.length!==1||keys.some(k=>k!==axis[0]&&(Math.abs(b[k]-node[k])>.0002||a[k]!==b[k]||a[k]!==node[k]))||(a[axis[0]]-node[axis[0]])*(b[axis[0]]-node[axis[0]])>=0)continue;
  const first=p.to===node.id?p:q,second=first===p?q:p;
  const joined={...p,from:p.direction==='both'?a.id:first.from,to:p.direction==='both'?b.id:second.to,sourcePipeIds:[...p.sourcePipeIds,...q.sourcePipeIds]};
  alive.delete(p);alive.delete(q);alive.add(joined);for(const e of [p,q]){incident.get(e.from)?.delete(e);incident.get(e.to)?.delete(e);}add(joined.from,joined);add(joined.to,joined);
 }
 return [...alive];
}
function hydraulicInletFlow(n,distances){
 const nodes=new Map(n.nodes.filter(v=>distances.has(v.id)).map(v=>[v.id,v])),edges=new Map(),adj=new Map();
 for(const p of n.pipes){if(p.state!=='open'||!nodes.has(p.from)||!nodes.has(p.to))continue;edges.set(p.id,p);for(const id of [p.from,p.to]){if(!adj.has(id))adj.set(id,new Set());adj.get(id).add(p.id);}}
 // Supply-only dead ends (pump discharge branches) are not a destination of FDC flow.
 const removable=id=>id!==n.inlet&&nodes.get(id)?.type!=='outlet'&&(adj.get(id)?.size||0)<=1;
 const queue=[...nodes.keys()].filter(removable);
 while(queue.length){const id=queue.pop();if(!nodes.has(id)||!removable(id))continue;for(const eid of adj.get(id)||[]){const p=edges.get(eid);if(!p)continue;const next=p.from===id?p.to:p.from;edges.delete(eid);adj.get(next)?.delete(eid);if(removable(next))queue.push(next);}nodes.delete(id);adj.delete(id);}
 return {nodes:[...nodes.keys()],pipes:[...edges.keys()]};
}
window.installHydraulicView=function(T,scene,camera,canvas){
 const group=new T.Group();group.name='소방 계통 연결 개략';scene.add(group);let clickable=[],flowArrows=[],flowHeads=[],arrowBatches=[];const flowTransform=new T.Object3D();
 let lastFlow=0;
 function animateFlow(ms){requestAnimationFrame(animateFlow);if(document.hidden||!group.visible||ms-lastFlow<32)return;lastFlow=ms;
  const glow=.3+.7*(.5+.5*Math.sin(ms*.004));for(const h of flowHeads)h.material.emissiveIntensity=glow;
  for(const f of flowArrows){const u=((ms*.0006/f.length)+f.phase)%1;flowTransform.position.copy(f.a).lerp(f.b,u);flowTransform.quaternion.copy(f.rotation);flowTransform.scale.copy(f.scale);flowTransform.updateMatrix();f.batch.setMatrixAt(f.index,flowTransform.matrix);}
  for(const batch of arrowBatches)batch.instanceMatrix.needsUpdate=true;
 }requestAnimationFrame(animateFlow);
 function clear(){for(const o of [...group.children]){o.traverse(m=>{if(m.isInstancedMesh)m.dispose();m.geometry?.dispose();if(m.material){m.material.map?.dispose();m.material.dispose();}});group.remove(o);}clickable=[];flowArrows=[];arrowBatches=[];for(const h of flowHeads)if(h.material)h.material.emissiveIntensity=0;flowHeads=[];}
 function update(e){clear();const {network:n,trace:inletTrace,visible}=e.detail;const supply=window.waterFlowSource==='tank'&&n.tankSupplyId?n.tankSupplyId:n.inlet;const visualNetwork={...n,inlet:supply,visualRootId:supply};const fd=hydraulicFlowDistances(visualNetwork);const t=supply===n.inlet?hydraulicInletFlow(visualNetwork,fd):{nodes:[...fd.keys()],pipes:n.pipes.filter(p=>p.state==='open'&&fd.has(p.from)&&fd.has(p.to)).map(p=>p.id)};group.visible=visible;scene.traverse(m=>{if(m.userData?.fireBackbone&&m.material){m.material.transparent=true;m.material.visible=!(visible&&n.geometryOwner==='reviewed-facilities');m.material.opacity=1;}});if(!visible)return;
  const nodes=new Map(n.nodes.filter(p=>[p.x,p.y,p.z].every(Number.isFinite)).map(p=>[p.id,p]));
  scene.traverse(m=>{const q=m.userData?.firePosition;if(!q||!m.material||m.userData.fireBackbone)return;let near=null,best=Infinity;for(const node of nodes.values()){if(m.userData.layer==='fireInlet'&&node.type!=='inlet')continue;const dist=Math.hypot(q[0]-node.x,q[1]-node.y,q[2]-node.z);if(dist<best){best=dist;near=node;}}const active=near&&(m.userData.layer==='fireInlet'?near.id===n.inlet:t.nodes.includes(near.id));m.material.transparent=true;m.material.opacity=active?1:.16;if(active&&m.userData.fireHead)flowHeads.push(m);});
  const flowDistances=fd;const lineBatches=new Map(),pipeBatches=new Map(),arrowSpecs=new Map();const floor=document.getElementById('viewFloor')?.value;const floorPipes=hydraulicFloorPipeIds(visualNetwork,floor);
  for(const p of hydraulicDisplayPipes(n,t.pipes,floorPipes)){const a=nodes.get(p.from),b=nodes.get(p.to);if(!a||!b)continue;const av=new T.Vector3(a.x,a.y,a.z),bv=new T.Vector3(b.x,b.y,b.z),d=bv.clone().sub(av);if(d.length()<.001)continue;
   const owned=n.geometryOwner==='reviewed-facilities',selected=t.pipes.includes(p.id);if(owned&&(!floorPipes.has(p.id)||window.reviewLayerVisibility?.[p.system||n.system||'sprinkler']===false||window.reviewLayerVisibility?.waterPipe===false))continue;
   const outsideFloor=owned&&floor&&floor!=='all'&&(!floor.endsWith('|'+a.floor)||!floor.endsWith('|'+b.floor));
   const size=hydraulicPipeRadius(p);
   // A one-pixel continuous centerline survives subpixel pipe diameters and occlusion.
   const lineKey=selected?(outsideFloor?'outside':'inside'):'inactive';
   if(!lineBatches.has(lineKey))lineBatches.set(lineKey,{points:[],color:selected?0xff6679:0xbb7782,opacity:selected?(outsideFloor?.72:.55):.2});
   lineBatches.get(lineKey).points.push(av.x,av.y,av.z,bv.x,bv.y,bv.z);
   const pipeKey=[selected,size.known,!!outsideFloor].join(':');
   if(!pipeBatches.has(pipeKey))pipeBatches.set(pipeKey,{items:[],color:selected?(size.known?0xff375e:0xe46b7d):0xbb7782,opacity:selected?(outsideFloor?.55:1):.16,outside:!!outsideFloor});
   const tr=new T.Object3D();tr.position.copy(av).add(bv).multiplyScalar(.5);tr.scale.set(size.radius,d.length(),size.radius);tr.quaternion.setFromUnitVectors(new T.Vector3(0,1,0),d.normalize());tr.updateMatrix();pipeBatches.get(pipeKey).items.push(tr.matrix.clone());
   if(selected&&p.state==='open'&&av.distanceTo(bv)>.45&&flowDistances.has(p.from)&&flowDistances.has(p.to)){
    const forward=flowDistances.get(p.from)<=flowDistances.get(p.to),start=forward?av:bv,finish=forward?bv:av;
    const direction=finish.clone().sub(start).normalize(),length=start.distanceTo(finish),count=Math.max(1,Math.floor(length/4));
    for(let j=0;j<count;j++){
     const key=outsideFloor?'outside':'inside';if(!arrowSpecs.has(key))arrowSpecs.set(key,[]);
     arrowSpecs.get(key).push({a:start,b:finish,length,phase:j/count,rotation:new T.Quaternion().setFromUnitVectors(new T.Vector3(0,1,0),direction),scale:new T.Vector3(Math.max(.055,size.radius*1.65),Math.max(.22,size.radius*4),Math.max(.055,size.radius*1.65))});
    }
   }

  }
  for(const b of lineBatches.values()){const geo=new T.BufferGeometry();geo.setAttribute('position',new T.Float32BufferAttribute(b.points,3));const line=new T.LineSegments(geo,new T.LineBasicMaterial({color:b.color,transparent:true,opacity:b.opacity,depthTest:false,depthWrite:false}));line.renderOrder=19;group.add(line);}
  for(const b of pipeBatches.values()){const mesh=new T.InstancedMesh(new T.CylinderGeometry(1,1,1,window.SimpleGeometry?.enabled?4:12),new T.MeshBasicMaterial({color:b.color,transparent:true,depthWrite:false,depthTest:!b.outside,opacity:b.opacity}),b.items.length);b.items.forEach((matrix,i)=>mesh.setMatrixAt(i,matrix));mesh.instanceMatrix.needsUpdate=true;mesh.computeBoundingSphere();mesh.renderOrder=b.outside?20:0;group.add(mesh);}
  for(const [key,items] of arrowSpecs){const outside=key==='outside',batch=new T.InstancedMesh(new T.ConeGeometry(1,1,10),new T.MeshBasicMaterial({color:0xffc9b7,transparent:true,opacity:outside?.45:.95,depthTest:!outside}),items.length);batch.instanceMatrix.setUsage(T.DynamicDrawUsage);batch.frustumCulled=false;batch.renderOrder=outside?21:1;items.forEach((f,i)=>{flowTransform.position.copy(f.a).lerp(f.b,f.phase);flowTransform.quaternion.copy(f.rotation);flowTransform.scale.copy(f.scale);flowTransform.updateMatrix();batch.setMatrixAt(i,flowTransform.matrix);flowArrows.push({...f,batch,index:i});});group.add(batch);arrowBatches.push(batch);}
  for(const h of flowHeads)h.material.emissive?.setHex(0xff3720);
  const inletMarkers=hydraulicInletMarkers([...nodes.values()],n.inlet);
  for(const p of nodes.values()){if(p.type==='inlet'&&!inletMarkers.has(p.id))continue;if(n.geometryOwner==='reviewed-facilities'&&(p.type!=='inlet'||window.reviewLayerVisibility?.fireInlet===false))continue;const color=p.id===n.inlet?0xff465c:n.active.includes(p.id)?0xff7889:0xba3a50;const m=new T.Mesh(new T.SphereGeometry(p.type==='inlet'?.38:.22,12,8),new T.MeshBasicMaterial({color,transparent:true,opacity:(p.type==='inlet'?p.id===n.inlet:t.nodes.includes(p.id))?1:.2}));m.position.set(p.x,p.y,p.z);m.userData.hydraulicId=p.id;group.add(m);if(p.type==='inlet')clickable.push(m);
   if(p.id===n.inlet){const c=document.createElement('canvas'),ctx=c.getContext('2d');const count=inletMarkers.get(p.id)||1;const caption=p.name+(count>1?' · '+count+'개 중 선택':'');ctx.font='25px sans-serif';c.width=Math.ceil(ctx.measureText(caption).width)+32;c.height=56;ctx.fillStyle='#163d5f';ctx.fillRect(0,0,c.width,c.height);ctx.fillStyle='white';ctx.font='25px sans-serif';ctx.textAlign='center';ctx.fillText(caption,c.width/2,37);const label=new T.Sprite(new T.SpriteMaterial({map:new T.CanvasTexture(c),depthTest:false,depthWrite:false}));label.position.set(p.x,p.y+.85,p.z);label.scale.set(c.width/100,.56,1);group.add(label);}

  }
 }
 window.addEventListener('hydraulic-selection',update);
 canvas.addEventListener('click',e=>{if(!group.visible)return;const r=canvas.getBoundingClientRect(),ray=new T.Raycaster();ray.setFromCamera(new T.Vector2((e.clientX-r.left)/r.width*2-1,-(e.clientY-r.top)/r.height*2+1),camera);const hit=ray.intersectObjects(clickable)[0];if(hit)window.dispatchEvent(new CustomEvent('hydraulic-pick',{detail:{id:hit.object.userData.hydraulicId}}));});
 document.getElementById('viewFloor')?.addEventListener('change',()=>window.HydraulicUI?.refresh());window.HydraulicUI?.refresh();return group;
};
