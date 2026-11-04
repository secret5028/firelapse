import {joinedSelectionRibbons} from './risk_geometry.js';

// Both bands share the same adaptive joins, including narrow and concave rooms.
export function selectionOutlineVertices(polygons,z){
 const backing=[],foreground=[];
 for(const p of polygons)for(const r of joinedSelectionRibbons(p,.24,.08)){
  const mix=(a,b,t)=>a.map((v,i)=>v+(b[i]-v)*t);
  const outer=r.outer.map((p,i)=>mix(p,r.inner[i],.1875));
  const inner=r.outer.map((p,i)=>mix(p,r.inner[i],.8125));
  for(let i=0;i<outer.length;i++){
   const j=(i+1)%outer.length;
   for(const [target,o,n] of [[backing,r.outer,r.inner],[foreground,outer,inner]]){
    const quad=[o[i],o[j],n[j],n[i]];
    for(const k of [0,1,2,0,2,3])target.push(...quad[k],z+.08);
   }
  }
 }
 return {backing,foreground};
}
export function selectionOutlineMaterials(T,own){
 return ['#10212d','#ffffff'].map(color=>own(new T.MeshBasicMaterial({color,side:T.DoubleSide,transparent:true,opacity:.95,depthTest:false,depthWrite:false})));
}
export function selectionOutlineGeometry(T,own,polygons,z){
 const vertices=selectionOutlineVertices(polygons,z);
 return [vertices.backing,vertices.foreground].map(pts=>{const g=own(new T.BufferGeometry());g.setAttribute('position',new T.Float32BufferAttribute(pts,3));return g;});
}
export function selectionOutlineMesh(T,geometries,materials){
 const group=new T.Group();
 geometries.forEach((g,i)=>{const mesh=new T.Mesh(g,materials[i]);mesh.renderOrder=39+i;mesh.raycast=()=>{};group.add(mesh);});
 return group;
}
