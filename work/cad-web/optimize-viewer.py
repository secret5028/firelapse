from pathlib import Path
p=Path('work/hydraulic-view.js')
s=p.read_text('utf-8')
s=s.replace("let clickable=[],flowArrows=[],flowHeads=[];", "let clickable=[],flowArrows=[],flowHeads=[],arrowBatches=[];const flowTransform=new T.Object3D();")
start=s.index(' function animateFlow(')
end=s.index('\n function clear()',start)
s=s[:start]+''' let lastFlow=0;
 function animateFlow(ms){requestAnimationFrame(animateFlow);if(document.hidden||!group.visible||ms-lastFlow<32)return;lastFlow=ms;
  const glow=.3+.7*(.5+.5*Math.sin(ms*.004));for(const h of flowHeads)h.material.emissiveIntensity=glow;
  for(const f of flowArrows){const u=((ms*.0006/f.length)+f.phase)%1;flowTransform.position.copy(f.a).lerp(f.b,u);flowTransform.quaternion.copy(f.rotation);flowTransform.scale.copy(f.scale);flowTransform.updateMatrix();f.batch.setMatrixAt(f.index,flowTransform.matrix);}
  for(const batch of arrowBatches)batch.instanceMatrix.needsUpdate=true;
 }requestAnimationFrame(animateFlow);'''+s[end:]
s=s.replace('clickable=[];flowArrows=[];for(const h', 'clickable=[];flowArrows=[];arrowBatches=[];for(const h')
s=s.replace("m.material.opacity=visible&&n.geometryOwner==='reviewed-facilities'?0:1;", "m.material.visible=!(visible&&n.geometryOwner==='reviewed-facilities');m.material.opacity=1;")
s=s.replace('const flowDistances=hydraulicFlowDistances(visualNetwork);', 'const flowDistances=fd;const lineBatches=new Map(),pipeBatches=new Map(),arrowSpecs=new Map();')
start=s.index('   const centerline=')
end=s.index('\n   if(selected&&',start)
s=s[:start]+'''   const lineKey=selected?(outsideFloor?'outside':'inside'):'inactive';
   if(!lineBatches.has(lineKey))lineBatches.set(lineKey,{points:[],color:selected?0xff6679:0xbb7782,opacity:selected?(outsideFloor?.72:.55):.2});
   lineBatches.get(lineKey).points.push(av.x,av.y,av.z,bv.x,bv.y,bv.z);
   const pipeKey=[selected,size.known,!!outsideFloor].join(':');
   if(!pipeBatches.has(pipeKey))pipeBatches.set(pipeKey,{items:[],color:selected?(size.known?0xff375e:0xe46b7d):0xbb7782,opacity:selected?(outsideFloor?.55:1):.16,outside:!!outsideFloor});
   const tr=new T.Object3D();tr.position.copy(av).add(bv).multiplyScalar(.5);tr.scale.set(size.radius,d.length(),size.radius);tr.quaternion.setFromUnitVectors(new T.Vector3(0,1,0),d.normalize());tr.updateMatrix();pipeBatches.get(pipeKey).items.push(tr.matrix.clone());'''+s[end:]
start=s.index('     const arrow=new T.Mesh(')
end=s.index('\n    }',start)
s=s[:start]+'''     const key=outsideFloor?'outside':'inside';if(!arrowSpecs.has(key))arrowSpecs.set(key,[]);
     arrowSpecs.get(key).push({a:start,b:finish,length,phase:j/count,rotation:new T.Quaternion().setFromUnitVectors(new T.Vector3(0,1,0),direction),scale:new T.Vector3(Math.max(.055,size.radius*1.65),Math.max(.22,size.radius*4),Math.max(.055,size.radius*1.65))});'''+s[end:]
mark='  for(const p of nodes.values())'
pos=s.index(mark)
s=s[:pos]+'''  for(const b of lineBatches.values()){const geo=new T.BufferGeometry();geo.setAttribute('position',new T.Float32BufferAttribute(b.points,3));const line=new T.LineSegments(geo,new T.LineBasicMaterial({color:b.color,transparent:true,opacity:b.opacity,depthTest:false,depthWrite:false}));line.renderOrder=19;group.add(line);}
  for(const b of pipeBatches.values()){const mesh=new T.InstancedMesh(new T.CylinderGeometry(1,1,1,12),new T.MeshBasicMaterial({color:b.color,transparent:true,depthWrite:false,depthTest:!b.outside,opacity:b.opacity}),b.items.length);b.items.forEach((matrix,i)=>mesh.setMatrixAt(i,matrix));mesh.instanceMatrix.needsUpdate=true;mesh.computeBoundingSphere();mesh.renderOrder=b.outside?20:0;group.add(mesh);}
  for(const [key,items] of arrowSpecs){const outside=key==='outside',batch=new T.InstancedMesh(new T.ConeGeometry(1,1,10),new T.MeshBasicMaterial({color:0xffc9b7,transparent:true,opacity:outside?.45:.95,depthTest:!outside}),items.length);batch.instanceMatrix.setUsage(T.DynamicDrawUsage);batch.frustumCulled=false;batch.renderOrder=outside?21:1;items.forEach((f,i)=>{flowTransform.position.copy(f.a).lerp(f.b,f.phase);flowTransform.quaternion.copy(f.rotation);flowTransform.scale.copy(f.scale);flowTransform.updateMatrix();batch.setMatrixAt(i,flowTransform.matrix);flowArrows.push({...f,batch,index:i});});group.add(batch);arrowBatches.push(batch);}
  for(const h of flowHeads)h.material.emissive?.setHex(0xff3720);
'''+s[pos:]
p.write_text(s,'utf-8')
p=Path('work/folder_review.html');s=p.read_text('utf-8')
s=s.replace('Math.min(devicePixelRatio,2)', 'Math.min(devicePixelRatio,1.25)')
s=s.replace("const o=group.children.pop();o.geometry?.dispose();o.material?.dispose()", "const o=group.children[0];group.remove(o);o.traverse(m=>{m.geometry?.dispose();for(const mat of (Array.isArray(m.material)?m.material:[m.material])){mat?.map?.dispose();mat?.dispose();}})")
s=s.replace("if(mode==='3d')renderer.render(scene,camera)", "if(mode==='3d'&&!document.hidden)renderer.render(scene,camera)")
p.write_text(s,'utf-8')
