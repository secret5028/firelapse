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
 function update(e){clear();const {network:n,trace:inletTrace,visible}=e.detail;const supply=window.waterFlowSource==='tank'&&n.tankSupplyId?n.tankSupplyId:n.inlet;const visualNetwork={...n,inlet:supply,visualRootId:supply};const fd=hydraulicFlowDistances(visualNetwork);const t=supply===n.inlet?hydraulicInletFlow(visualNetwork,fd):{nodes:[...fd.keys()],pipes:n.pipes.filter(p=>p.state==='open'&&fd.has(p.from)&&fd.has(p.to)).map(p=>p.id)};group.visible=visible;const zoneNotice=document.getElementById('inlet-zone-status');if(zoneNotice)zoneNotice.hidden=!visible;scene.traverse(m=>{if(m.userData?.fireBackbone&&m.material){m.material.transparent=true;m.material.visible=!(visible&&n.geometryOwner==='reviewed-facilities');m.material.opacity=1;}});if(!visible)return;
  const nodes=new Map(n.nodes.filter(p=>[p.x,p.y,p.z].every(Number.isFinite)).map(p=>[p.id,p]));
  scene.traverse(m=>{const q=m.userData?.firePosition;if(!q||!m.material||m.userData.fireBackbone)return;let near=null,best=Infinity;for(const node of nodes.values()){if(m.userData.layer==='fireInlet'&&node.type!=='inlet')continue;const dist=Math.hypot(q[0]-node.x,q[1]-node.y,q[2]-node.z);if(dist<best){best=dist;near=node;}}const active=near&&(m.userData.layer==='fireInlet'?near.id===n.inlet:t.nodes.includes(near.id));m.material.transparent=true;m.material.opacity=active?1:.16;if(active&&m.userData.fireHead)flowHeads.push(m);});

  // Zones are explicit source metadata: overlapping geometry never implies connectivity.
  const zones=n.displayZones||[], chosen=zones.find(z=>z.inletId===n.inlet);
  if(zones.length){
   let note=document.getElementById('inlet-zone-status');
   if(!note){note=document.createElement('div');note.id='inlet-zone-status';note.style.cssText='position:fixed;bottom:54px;left:300px;max-width:440px;padding:9px 12px;background:#142c40ed;color:#ffe39a;font-size:13px;z-index:150;pointer-events:none';document.body.appendChild(note);}
   note.hidden=!visible;
   note.textContent=chosen?chosen.name+' · 스캔 판독 후보'+' · 현장 구역 번호 미확인':(n.readingAssessment?.blockedInletIds?.includes(n.inlet)?'선택한 송수구: 연결 판독 불가 · 선명한 도면 등록 후 재처리':'선택한 송수구: 담당 구역 미확정');
   const inside=(q,z)=>q[0]>=z.bounds[0]&&q[0]<=z.bounds[2]&&q[2]>=z.bounds[1]&&q[2]<=z.bounds[3];
   scene.traverse(m=>{if(m.userData?.layer!=='waterSpray'||!m.material)return;const q=m.userData.firePosition||m.position.toArray();m.material.transparent=true;m.material.opacity=chosen?(inside(q,chosen)?1:.14):.3;});
   for(const z of zones){const [x0,z0,x1,z1]=z.bounds,active=z===chosen;
    const mesh=new T.Mesh(new T.PlaneGeometry(x1-x0,z1-z0),new T.MeshBasicMaterial({color:active?0xff5266:0x965f67,transparent:true,opacity:active?.24:.035,depthWrite:false,side:T.DoubleSide}));
    mesh.rotation.x=-Math.PI/2;mesh.position.set((x0+x1)/2,.045,(z0+z1)/2);mesh.userData.layer='waterSpray';mesh.visible=window.reviewLayerVisibility?.waterSpray!==false;group.add(mesh);
   }
  }else{const note=document.getElementById('inlet-zone-status');if(note)note.hidden=true;}

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
  for(const b of pipeBatches.values()){const mesh=new T.InstancedMesh(new T.CylinderGeometry(1,1,1,window.SimpleGeometry?.enabled?4:12),new T.MeshBasicMaterial({color:b.color,transparent:true,depthWrite:false,depthTest:!b.outside,opacity:b.opacity}),b.items.length);b.items.forEach((matrix,i)=>mesh.setMatrixAt(i,matrix));mesh.instanceMatrix.needsUpdate=true;mesh.computeBoundingSphere();mesh.renderOrder=b.opacity>=.5?22:18;group.add(mesh);}
  for(const [key,items] of arrowSpecs){const outside=key==='outside',batch=new T.InstancedMesh(new T.ConeGeometry(1,1,10),new T.MeshBasicMaterial({color:0xffc9b7,transparent:true,opacity:outside?.45:.95,depthTest:!outside}),items.length);batch.instanceMatrix.setUsage(T.DynamicDrawUsage);batch.frustumCulled=false;batch.renderOrder=outside?21:1;items.forEach((f,i)=>{flowTransform.position.copy(f.a).lerp(f.b,f.phase);flowTransform.quaternion.copy(f.rotation);flowTransform.scale.copy(f.scale);flowTransform.updateMatrix();batch.setMatrixAt(i,flowTransform.matrix);flowArrows.push({...f,batch,index:i});});group.add(batch);arrowBatches.push(batch);}
  for(const h of flowHeads)h.material.emissive?.setHex(0xff3720);
  for(const p of nodes.values()){if(n.geometryOwner==='reviewed-facilities'&&(p.type!=='inlet'||window.reviewLayerVisibility?.fireInlet===false))continue;const color=p.id===n.inlet?0xff465c:n.active.includes(p.id)?0xff7889:0xba3a50;const m=new T.Mesh(new T.SphereGeometry(p.type==='inlet'?.38:.22,12,8),new T.MeshBasicMaterial({color,transparent:true,opacity:(p.type==='inlet'?p.id===n.inlet:t.nodes.includes(p.id))?1:.2}));m.position.set(p.x,p.y,p.z);m.userData.hydraulicId=p.id;group.add(m);if(p.type==='inlet')clickable.push(m);
   if(p.type!=='junction'){const c=document.createElement('canvas');c.width=512;c.height=64;const ctx=c.getContext('2d');ctx.fillStyle='#163d5fee';ctx.fillRect(0,0,512,64);ctx.fillStyle='white';ctx.font='25px sans-serif';ctx.textAlign='center';ctx.fillText(p.name+' · 연결 개략',256,42,490);const label=new T.Sprite(new T.SpriteMaterial({map:new T.CanvasTexture(c),depthTest:false,opacity:p.id===n.inlet?1:.3}));label.position.set(p.x,p.y+.7,p.z);label.scale.set(5,.625,1);group.add(label);}
  }
 }
 const updateWithElimination=e=>{update(e);window.PipeElimination?.update(scene,e.detail.network);};
 window.addEventListener('hydraulic-selection',updateWithElimination);
 canvas.addEventListener('click',e=>{if(!group.visible)return;const r=canvas.getBoundingClientRect(),ray=new T.Raycaster();ray.setFromCamera(new T.Vector2((e.clientX-r.left)/r.width*2-1,-(e.clientY-r.top)/r.height*2+1),camera);const hit=ray.intersectObjects(clickable)[0];if(hit)window.dispatchEvent(new CustomEvent('hydraulic-pick',{detail:{id:hit.object.userData.hydraulicId}}));});
 document.getElementById('viewFloor')?.addEventListener('change',()=>window.HydraulicUI?.refresh());window.HydraulicUI?.refresh();return group;
};


// PIPE_ELIMINATION_MODULE
// Source-backed branch membership. A crossing or a zone rectangle is never a connection.
(function(){
 const NS='http://www.w3.org/2000/svg';let scene,network,page,source,modal,svg,list,info,filter,raw,selected=new Set(),undo=[];
 const el=(tag,attrs={})=>{const e=document.createElementNS(NS,tag);for(const [k,v]of Object.entries(attrs))e.setAttribute(k,v);return e;};
 function data(){return page.pipeReview;}
 function persistReview(){window.HydraulicUI?.setPipeReview?.(data());if(typeof persist==='function')persist();}
 function snapshot(){undo.push(structuredClone(data().assignments));if(undo.length>30)undo.shift();}
 function chosen(){return list?.value||network.inlet;}
 function apply(){if(!scene||!page)return;const a=data().assignments;
  scene.traverse(m=>{const id=m.userData?.sourcePipeId;if(!id||!m.material)return;const assigned=a[id],active=assigned===network.inlet;m.material.transparent=true;m.material.opacity=assigned?(active?1:.13):.55;m.material.depthWrite=active;m.renderOrder=active?24:0;});
 }
 function redraw(){if(!svg)return;svg.replaceChildren();const p=page,dy=16.95/(176*87.45/921),coord=q=>[q[0],p.origin[1]+(q[1]-p.origin[1])/dy];
  const points=p.floorOutline.map(coord),xs=points.map(q=>q[0]),ys=points.map(q=>q[1]);svg.setAttribute('viewBox',[Math.min(...xs)-25,Math.min(...ys)-25,Math.max(...xs)-Math.min(...xs)+75,Math.max(...ys)-Math.min(...ys)+65].join(' '));
  if(raw.checked)svg.append(el('image',{href:source.image,x:0,y:0,width:source.width,height:source.height,opacity:.65}));
  let total=0,done=0;
  p.fireFacilities.pipes.forEach((b,i)=>{const id='P'+i,assigned=data().assignments[id];total++;if(assigned)done++;if(filter.checked&&assigned)return;
   const line=el('polyline',{points:b.points.map(coord).map(q=>q.join(',')).join(' '),fill:'none',stroke:selected.has(id)?'#00cfff':assigned===chosen()?'#ff2449':assigned?'#7c929f':'#ed8a00','stroke-width':selected.has(id)?4:2,'vector-effect':'non-scaling-stroke'});
   const hit=el('polyline',{points:line.getAttribute('points'),fill:'none',stroke:'transparent','stroke-width':14,'vector-effect':'non-scaling-stroke',tabindex:0,role:'button','aria-label':'배관 '+(i+1)+(assigned?' · '+assigned:' · 미확인')});
   const toggle=()=>{selected.has(id)?selected.delete(id):selected.add(id);redraw();};hit.onclick=toggle;hit.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();toggle();}};const title=el('title');title.textContent='배관 '+(i+1)+' · '+(assigned||'미확인');hit.append(title);svg.append(line,hit);
  });
  info.textContent='등록 가지배관 '+total+'개 중 소속 확인 '+done+'개 / 남음 '+(total-done)+'개 · 현재 선택 '+selected.size+'개. 원본 전체 주배관·헤드 판독 완료 수치가 아닙니다.';
 }
 function saveAssignment(){if(!selected.size)return;snapshot();for(const id of selected)data().assignments[id]=chosen();data().history.push({at:new Date().toISOString(),inletId:chosen(),pipeIds:[...selected],action:'user-confirmed'});selected.clear();persistReview();redraw();apply();}
 function open(){if(!modal){modal=document.createElement('dialog');modal.id='pipeEliminationDialog';modal.style.cssText='width:min(1400px,94vw);max-width:94vw;height:80vh;background:#142b3b;color:white;border:1px solid #6b8694;border-radius:10px;padding:16px';modal.innerHTML='<div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap"><strong>배관 소거 판독</strong><label>송수구 <select aria-label="소거 판독 송수구"></select></label><button data-action="confirm">선택 배관 연결 확인</button><button data-action="clear">선택 해제</button><button data-action="undo">되돌리기</button><button data-action="close">닫기</button></div><p>주황색 배관을 클릭해 선택한 뒤, 원본에서 연결을 확인한 경우에만 저장하세요. 겹치거나 교차하는 선은 자동 연결하지 않습니다.</p><label><input type="checkbox" data-option="exclude" checked> 확인한 배관 제외</label> <label><input type="checkbox" data-option="source" checked> 원본 도면 표시</label><p data-info></p><div style="height:55vh;overflow:auto;background:#f6f4ee"><svg aria-label="원본 위 배관 소거 판독" style="width:100%;height:100%;min-width:1000px"></svg></div><p>하늘색: 선택 · 주황색: 소속 미확인 · 적색: 선택 송수구에 연결 확인. 회색 원본은 접속부 대조를 위해 유지됩니다. 확인하지 않은 구역 후보는 소거하지 않습니다.</p>';
   document.body.append(modal);svg=modal.querySelector('svg');list=modal.querySelector('select');info=modal.querySelector('[data-info]');filter=modal.querySelector('[data-option=exclude]');raw=modal.querySelector('[data-option=source]');filter.onchange=raw.onchange=list.onchange=redraw;
   modal.querySelector('[data-action=confirm]').onclick=saveAssignment;modal.querySelector('[data-action=clear]').onclick=()=>{selected.clear();redraw();};modal.querySelector('[data-action=undo]').onclick=()=>{if(!undo.length)return;data().assignments=undo.pop();data().history.push({at:new Date().toISOString(),action:'undo'});persistReview();redraw();apply();};modal.querySelector('[data-action=close]').onclick=()=>modal.close();
  }
  list.replaceChildren();for(const n of network.nodes.filter(n=>n.type==='inlet')){const o=document.createElement('option');o.value=n.id;o.textContent=n.name;list.append(o);}list.value=network.inlet;redraw();modal.showModal();
 }
 window.PipeElimination={update(s,n){if(n.readingAssessment?.status==='partially-unreadable')return;if(!n.displayZones)return;scene=s;network=n;const pages=typeof state!=='undefined'?state.pages:[];page=pages.find(p=>p.fireFacilities?.system==='waterSpray');if(!page)return;source=window.REVIEW_DATA.pages[page.fireFacilities.sourcePage-1];
  const fingerprint=JSON.stringify(page.fireFacilities.pipes.map(b=>b.points));if(n.pipeReview?.fingerprint===fingerprint)page.pipeReview=structuredClone(n.pipeReview);if(!page.pipeReview||page.pipeReview.fingerprint!==fingerprint){if(page.pipeReview)page.previousPipeReview=page.pipeReview;page.pipeReview={fingerprint,assignments:{},history:[]};}
  if(!document.getElementById('openPipeElimination')){const b=document.createElement('button');b.id='openPipeElimination';b.textContent='배관 소거 판독';b.onclick=open;document.getElementById('fireFacilityPanel')?.append(b);}apply();
 }};
})();

// PARTIAL_READING_NOTICE

window.addEventListener('hydraulic-selection',e=>{
 const a=e.detail.network.readingAssessment;let box=document.getElementById('partialReadingNotice');
 if(!a){if(box)box.remove();return;}
 if(!box){box=document.createElement('section');box.id='partialReadingNotice';box.setAttribute('role','status');box.setAttribute('aria-live','polite');box.style.cssText='border:1px solid #d69c42;border-radius:7px;padding:12px;margin:12px 0;background:#49391f;color:#ffe1a0;font-size:12px;line-height:1.6';document.getElementById('fireFacilityPanel')?.prepend(box);}
 box.replaceChildren();const title=document.createElement('strong');title.textContent=a.title;box.append(title);
 for(const text of [a.message,a.remaining,a.nextAction]){const p=document.createElement('p');p.textContent=text;box.append(p);}
 const manual=document.getElementById('openPipeElimination');if(manual)manual.remove();const dialog=document.getElementById('pipeEliminationDialog');if(dialog?.open)dialog.close();
});
