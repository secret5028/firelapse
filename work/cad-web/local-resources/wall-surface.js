// Build only the exposed surface of a wall; adjacent opening bands share no caps.
function wallSurfaceData(length, height, cuts, thickness = .16) {
  const holes = cuts.map(([u,v,type]) => [Math.max(0,u*length),Math.min(length,v*length),type==='window'?Math.min(.9,height):0,Math.min(2.1,height)])
    .filter(([a,b,c,d]) => b-a>1e-6 && d-c>1e-6);
  const unique = values => [...new Set(values)].sort((a,b)=>a-b);
  const xs=unique([0,length,...holes.flatMap(h=>h.slice(0,2))]);
  const ys=unique([0,height,...holes.flatMap(h=>h.slice(2))]);
  const filled=(i,j)=>i>=0&&j>=0&&i<xs.length-1&&j<ys.length-1&&!holes.some(([a,b,c,d])=>
    (xs[i]+xs[i+1])/2>a&&(xs[i]+xs[i+1])/2<b&&(ys[j]+ys[j+1])/2>c&&(ys[j]+ys[j+1])/2<d);
  const positions=[], normals=[], z=thickness/2;
  function quad(a,b,c,d,n){for(const p of [a,b,c,a,c,d]){positions.push(...p);normals.push(...n);}}
  for(let i=0;i<xs.length-1;i++)for(let j=0;j<ys.length-1;j++){
    if(!filled(i,j))continue;
    const a=xs[i],b=xs[i+1],c=ys[j],d=ys[j+1];
    quad([a,c,z],[b,c,z],[b,d,z],[a,d,z],[0,0,1]);
    quad([b,c,-z],[a,c,-z],[a,d,-z],[b,d,-z],[0,0,-1]);
    if(!filled(i-1,j))quad([a,c,-z],[a,c,z],[a,d,z],[a,d,-z],[-1,0,0]);
    if(!filled(i+1,j))quad([b,c,z],[b,c,-z],[b,d,-z],[b,d,z],[1,0,0]);
    if(!filled(i,j-1))quad([a,c,-z],[b,c,-z],[b,c,z],[a,c,z],[0,-1,0]);
    if(!filled(i,j+1))quad([a,d,z],[b,d,z],[b,d,-z],[a,d,-z],[0,1,0]);
  }
  return {positions,normals};
}
function addContinuousWall(T,group,a,b,y,height,cuts,opacity){
  if(window.SimpleGeometry?.enabled){window.SimpleGeometry.wall(a,b,y,height,cuts);return;}
  const dx=b[0]-a[0],dz=b[1]-a[1];
  const data=wallSurfaceData(Math.hypot(dx,dz),height,cuts);
  const geometry=new T.BufferGeometry();
  geometry.setAttribute('position',new T.Float32BufferAttribute(data.positions,3));
  geometry.setAttribute('normal',new T.Float32BufferAttribute(data.normals,3));
  const wall=new T.Mesh(geometry,new T.MeshStandardMaterial({color:'#abc8d6',transparent:true,opacity,side:T.DoubleSide}));
  wall.position.set(a[0],y,a[1]);wall.rotation.y=-Math.atan2(dz,dx);
  wall.userData.layer='wall';group.add(wall);
}


// One batched outline for the visible building geometry, including opening edges.
function addWallOutlines(T,group){
 const positions=[];group.updateMatrixWorld(true);
 const inverse=new T.Matrix4().copy(group.matrixWorld).invert();
 group.traverse(wall=>{
  if(!wall.isMesh||wall.userData.layer!=='wall')return;
  const edges=new T.EdgesGeometry(wall.geometry,30);
  edges.applyMatrix4(new T.Matrix4().multiplyMatrices(inverse,wall.matrixWorld));
  const a=edges.getAttribute('position').array;for(let i=0;i<a.length;i++)positions.push(a[i]);edges.dispose();
 });
 if(!positions.length)return;
 const geometry=new T.BufferGeometry();geometry.setAttribute('position',new T.Float32BufferAttribute(positions,3));
 const lines=new T.LineSegments(geometry,new T.LineBasicMaterial({color:0x476273,transparent:true,opacity:.8,depthWrite:false}));
 lines.userData.layer='wallOutline';lines.userData.supplySystem='wall';lines.renderOrder=2;group.add(lines);
}
